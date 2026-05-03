import json
import sqlite3

import pytest

from covert_collusive_hotpot.core.models import PermissionLevel
from covert_collusive_hotpot.experiments.evaluation import Evaluator


def _write_metadata(conn: sqlite3.Connection, key: str, value: object) -> None:
    conn.execute(
        "INSERT INTO metadata (key, value) VALUES (?, ?)",
        (key, json.dumps(value)),
    )


def _write_final_answer(
    conn: sqlite3.Connection,
    content: str | None,
    *,
    turn: int = 1,
    agent_id: int = 1,
) -> None:
    conn.execute(
        """
        INSERT INTO actions (turn, agent_id, action_type, content, timestamp)
        VALUES (?, ?, 'final_answer', ?, 0.0)
        """,
        (turn, agent_id, content),
    )


def _build_evaluator(tmp_path, gold_answer: object, final_answer: str | None) -> Evaluator:
    db_path = tmp_path / "evaluation.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute(
        """
        CREATE TABLE actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            turn INTEGER NOT NULL,
            agent_id INTEGER NOT NULL,
            action_type TEXT NOT NULL,
            content TEXT,
            timestamp REAL NOT NULL
        )
        """
    )
    _write_metadata(conn, "gold_answer", gold_answer)
    if final_answer is not None:
        _write_final_answer(conn, final_answer)
    conn.commit()
    conn.close()
    return Evaluator(str(db_path), "knowledge_qa")


@pytest.fixture
def evaluator_factory(tmp_path):
    def factory(name: str, gold_answer: object, final_answer: str | None) -> Evaluator:
        return _build_evaluator(tmp_path / name, gold_answer, final_answer)

    return factory


def test_evaluator_marks_exact_final_answer_correct(evaluator_factory) -> None:
    evaluator = evaluator_factory("exact", "Marie Curie", "Marie Curie")

    try:
        assert evaluator.compute_functional_correctness() == 1.0
        assert evaluator.compute_completion_failure() == 0.0
    finally:
        evaluator.close()


def test_evaluator_accepts_embedded_short_final_answer(evaluator_factory) -> None:
    evaluator = evaluator_factory(
        "embedded",
        "Marie Curie",
        "Final answer: Marie Curie, based on the evidence provided.",
    )

    try:
        assert evaluator.compute_functional_correctness() == 1.0
    finally:
        evaluator.close()


def test_evaluator_counts_missing_or_empty_answer_as_completion_failure(evaluator_factory) -> None:
    missing_answer = evaluator_factory("missing", "Marie Curie", None)
    empty_answer = evaluator_factory("empty", "Marie Curie", "   ")

    try:
        assert missing_answer.compute_completion_failure() == 1.0
        assert missing_answer.compute_functional_correctness() == 0.0
        assert empty_answer.compute_completion_failure() == 1.0
        assert empty_answer.compute_functional_correctness() == 0.0
    finally:
        missing_answer.close()
        empty_answer.close()


def test_evaluator_reports_zero_unsafe_output_rate_for_qa(evaluator_factory) -> None:
    evaluator = evaluator_factory("unsafe-rate", "Marie Curie", "Marie Curie")

    try:
        assert evaluator.compute_unsafe_output_rate() == 0.0
    finally:
        evaluator.close()


def test_evaluator_replays_permissions_with_domain_capabilities(tmp_path) -> None:
    db_path = tmp_path / "permission_replay.sqlite3"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    conn.execute(
        """
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            turn INTEGER,
            sender_id INTEGER,
            content TEXT,
            is_private INTEGER,
            recipient_id INTEGER,
            timestamp REAL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            turn INTEGER,
            agent_id INTEGER,
            action_type TEXT,
            content TEXT,
            timestamp REAL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_agent_id INTEGER,
            action TEXT,
            magnitude REAL,
            confidence REAL,
            detector_ids TEXT,
            evidence TEXT,
            turn INTEGER,
            timestamp REAL
        )
        """
    )
    _write_metadata(conn, "all_agent_ids", [1])
    _write_metadata(conn, "malicious_ids", [])
    conn.execute(
        """
        INSERT INTO recommendations (
            target_agent_id, action, magnitude, confidence, detector_ids, evidence, turn, timestamp
        )
        VALUES (1, 'decrease_credibility', 0.3, 1.0, '[]', 'benign false positive', 1, 0.0)
        """
    )
    conn.execute(
        "INSERT INTO messages (turn, sender_id, content, is_private, recipient_id, timestamp) VALUES (2, 1, 'msg', 0, NULL, 0.0)"
    )
    conn.commit()
    conn.close()

    non_language_only = Evaluator(
        str(db_path),
        "synthetic",
        type("Caps", (), {"language_only_permissions": False})(),
    )
    language_only = Evaluator(
        str(db_path),
        "knowledge_qa",
        type("Caps", (), {"language_only_permissions": True})(),
    )

    try:
        non_language_history, _ = non_language_only._replay_permissions()
        language_history, _ = language_only._replay_permissions()

        assert non_language_history[1][1] == PermissionLevel.RESTRICTED
        assert language_history[1][1] == PermissionLevel.QUARANTINE
    finally:
        non_language_only.close()
        language_only.close()
