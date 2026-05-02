import argparse
import asyncio
import ast
import sqlite3
import time
from pathlib import Path

from covert_collusive_hotpot.experiments import runner
from covert_collusive_hotpot.experiments.evaluation import Evaluator
from covert_collusive_hotpot.experiments.simulation import Simulation
from covert_collusive_hotpot import generate_paper_assets as paper_assets
from covert_collusive_hotpot.core.models import Recommendation


def _evaluator_methods_called_by_runner() -> set[str]:
    source = Path(runner.__file__).read_text()
    tree = ast.parse(source)
    methods: set[str] = set()

    class Visitor(ast.NodeVisitor):
        def visit_Call(self, node):
            if (
                isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "evaluator"
            ):
                methods.add(node.func.attr)
            self.generic_visit(node)

    Visitor().visit(tree)
    methods.discard("close")
    return methods


def test_runner_only_calls_existing_evaluator_methods() -> None:
    called = _evaluator_methods_called_by_runner()
    available = {name for name in dir(Evaluator) if callable(getattr(Evaluator, name))}
    assert called <= available


def test_reporting_required_columns_are_emitted_by_runner() -> None:
    output_fields = set(runner.OUTPUT_FIELDNAMES)
    required = {
        "domain",
        "m",
        "d",
        "knowledge_level",
        "tasks_evaluated",
        "unsafe_output_rate_mean",
        "functional_correctness_mean",
        "latency_mean",
        "false_positive_rate_mean",
        "detection_rate_mean",
        "detection_latency_mean",
    }
    assert required <= output_fields


def test_run_label_override_updates_failed_configs_path(monkeypatch) -> None:
    monkeypatch.setattr(runner, "RUN_LABEL", "collusive_hotpot")
    monkeypatch.setattr(runner, "OUTPUT_CSV", "experiment_results.collusive_hotpot.csv")
    monkeypatch.setattr(runner, "TASK_PROGRESS_JSONL", "task_progress.collusive_hotpot.jsonl")
    monkeypatch.setattr(runner, "FAILED_CONFIGS_CSV", "failed_configs.collusive_hotpot.csv")
    monkeypatch.delenv("FAILED_CONFIGS_CSV", raising=False)

    args = argparse.Namespace(
        run_label="local_smoke",
        output_csv=None,
        task_progress_jsonl=None,
        smoke=False,
        smoke_tasks=2,
        tasks=None,
        reps=None,
    )

    runner._apply_cli_overrides(args)

    assert runner.OUTPUT_CSV == "experiment_results.local_smoke.csv"
    assert runner.TASK_PROGRESS_JSONL == "task_progress.local_smoke.jsonl"
    assert runner.FAILED_CONFIGS_CSV == "failed_configs.local_smoke.csv"


def test_single_experiment_fake_smoke_produces_reporting_compatible_row(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(runner.cfg, "LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setattr(runner, "RUN_LABEL", "contract_smoke")
    monkeypatch.setattr(runner, "OUTPUT_CSV", str(tmp_path / "experiment_results.contract_smoke.csv"))
    monkeypatch.setattr(runner, "TASK_PROGRESS_JSONL", str(tmp_path / "task_progress.contract_smoke.jsonl"))
    monkeypatch.setattr(runner, "FAILED_CONFIGS_CSV", str(tmp_path / "failed_configs.contract_smoke.csv"))

    class FakeWorkerAgent:
        def __init__(self, agent_data, task_description, **kwargs):
            self.id = agent_data.id
            self.agent_data = agent_data
            self.task_description = task_description

    class FakeDetectorAgent:
        def __init__(self, detector_id, *args, **kwargs):
            self.id = detector_id

    class FakeLogger:
        def __init__(self, db_path: str):
            self.db_path = db_path

    class FakeSimulation:
        def __init__(self, workers, detectors, total_turns, experiment_id, metadata, domain):
            db_path = Path(runner.cfg.LOG_DIR) / f"{experiment_id}.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(db_path)
            conn.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT)")
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
            conn.execute(
                """
                CREATE TABLE permission_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id INTEGER,
                    old_credibility REAL,
                    new_credibility REAL,
                    reason TEXT,
                    recommending_detectors TEXT,
                    timestamp REAL
                )
                """
            )
            for key, value in metadata.items():
                import json

                stored = value if isinstance(value, str) else json.dumps(value)
                conn.execute("INSERT INTO metadata (key, value) VALUES (?, ?)", (key, stored))
            conn.commit()
            conn.close()
            self.logger = FakeLogger(str(db_path))
            self.metadata = metadata

        async def run(self):
            conn = sqlite3.connect(self.logger.db_path)
            conn.execute(
                """
                INSERT INTO actions (turn, agent_id, action_type, content, timestamp)
                VALUES (?, ?, 'final_answer', ?, ?)
                """,
                (4, 0, "Marie Curie", time.time()),
            )
            conn.execute(
                """
                INSERT INTO messages (turn, sender_id, content, is_private, recipient_id, timestamp)
                VALUES (?, ?, ?, 0, NULL, ?)
                """,
                (4, 0, "Marie Curie", time.time()),
            )
            conn.commit()
            conn.close()
            return [], []

    monkeypatch.setattr(runner, "WorkerAgent", FakeWorkerAgent)
    monkeypatch.setattr(runner, "DetectorAgent", FakeDetectorAgent)
    monkeypatch.setattr(runner, "Simulation", FakeSimulation)
    monkeypatch.setattr(paper_assets, "REQUIRE_FULL_TASK_COUNTS", False)

    exp_config = runner.ExperimentConfig(
        rep=1,
        attack_type=runner.AttackType.SUBOPTIMAL_FIXATION,
        m="0",
        d=0,
        condition_name="clean_baseline",
    )
    task_pools = {
        runner.DOMAIN: [
            {
                "task_id": "synthetic_hotpot_1",
                "prompt": "Question: Who discovered radium?",
                "question": "Who discovered radium?",
                "answer": "Marie Curie",
            }
        ]
    }

    result = asyncio.run(
        runner.run_single_experiment(
            exp_config=exp_config,
            task_pools=task_pools,
            task_progress={},
            progress_lock=asyncio.Lock(),
        )
    )

    row = runner._row_for_output(exp_config, result, malicious_count=0)
    csv_path = tmp_path / "synthetic_results.csv"
    import csv

    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=runner.OUTPUT_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerow(row)

    loaded = paper_assets.load_results(str(csv_path))
    assert result["tasks_evaluated"] == 1
    assert result["functional_correctness_mean"] == 1.0
    assert result["completion_failure_mean"] == 0.0
    assert result["unsafe_output_rate_mean"] == 0.0
    assert len(loaded) == 1


def test_simulation_detection_latency_matches_evaluator_turn_definition() -> None:
    class AgentData:
        def __init__(self, is_malicious: bool):
            self.is_malicious = is_malicious

    class Worker:
        def __init__(self, agent_id: int, is_malicious: bool):
            self.id = agent_id
            self.agent_data = AgentData(is_malicious)

    sim = Simulation.__new__(Simulation)
    sim.turn = 4
    sim.workers = {
        0: Worker(0, True),
        1: Worker(1, False),
        2: Worker(2, True),
    }
    sim.recommendation_log = [
        Recommendation(
            target_agent_id=2,
            action="quarantine",
            magnitude=0.2,
            confidence=0.9,
            detector_ids=[1000],
            evidence="evidence",
            turn=2,
        )
    ]

    metrics = sim._compute_metrics()

    assert metrics["detection_rate"] == 0.5
    assert metrics["detection_precision"] == 1.0
    assert metrics["attribution_accuracy"] == 0.5
    assert metrics["detection_latency"] == 2.0
