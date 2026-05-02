import json
import sqlite3

import pytest

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
