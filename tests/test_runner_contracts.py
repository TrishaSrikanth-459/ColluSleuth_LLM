import argparse
import asyncio
import ast
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from covert_collusive_hotpot.experiments import runner
from covert_collusive_hotpot.experiments.evaluation import Evaluator
from covert_collusive_hotpot.experiments.simulation import Simulation
from covert_collusive_hotpot import generate_paper_assets as paper_assets
from covert_collusive_hotpot.core.models import PermissionLevel, Recommendation


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


def test_runner_defaults_to_registry_default_domain(monkeypatch) -> None:
    class FakeRegistry:
        def default_domain_name(self) -> str:
            return "knowledge_qa"

        def get(self, name: str):
            assert name == "knowledge_qa"
            return type("Domain", (), {"name": name})()

    monkeypatch.setattr(runner, "get_domain_registry", lambda: FakeRegistry())
    monkeypatch.setattr(runner.cfg, "DEFAULT_DOMAIN", "code_synthesis")

    args = runner.build_arg_parser().parse_args([])

    assert args.domain is None
    assert runner._resolve_domain(args).name == "knowledge_qa"


def test_runner_rejects_unknown_domain() -> None:
    parser = runner.build_arg_parser()

    try:
        args = parser.parse_args(["--domain", "missing"])
        runner._resolve_domain(args)
    except ValueError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("Expected invalid domain to raise")


def test_generate_configs_writes_selected_domain() -> None:
    configs = runner.generate_configs(total_reps=1, domain_name="knowledge_qa")

    assert configs
    assert {config.domain for config in configs} == {"knowledge_qa"}


def test_build_task_pools_uses_selected_domain_task_builder(monkeypatch) -> None:
    monkeypatch.setattr(runner.cfg, "HOTPOT_QA_TASKS", 7)
    calls: dict[str, object] = {}

    class FakeDomain:
        name = "knowledge_qa"

        def build_task_pool(self, task_count: int, seed: int | None):
            calls["task_count"] = task_count
            calls["seed"] = seed
            return [{"task_id": "synthetic", "prompt": "prompt", "answer": "answer"}]

    class FakeRegistry:
        def get(self, name: str):
            calls["domain_name"] = name
            return FakeDomain()

    monkeypatch.setattr(runner, "get_domain_registry", lambda: FakeRegistry())

    pools = runner._build_task_pools(domain_name="knowledge_qa", seed=123)

    assert calls == {"domain_name": "knowledge_qa", "task_count": 7, "seed": 123}
    assert pools == {
        "knowledge_qa": [{"task_id": "synthetic", "prompt": "prompt", "answer": "answer"}]
    }


def test_prepare_agents_for_task_uses_domain_for_roles_and_prompt_injection(monkeypatch) -> None:
    calls: list[object] = []

    @dataclass
    class FakeAgent:
        id: int
        role: runner.Role
        is_malicious: bool = False

    class FakeDomain:
        name = "knowledge_qa"
        capabilities = type("Caps", (), {"language_only_permissions": True})()

        def assign_roles(self, rng):
            calls.append(("assign_roles", rng))
            return [
                FakeAgent(id=1, role=runner.Role.REPORTER),
                FakeAgent(id=2, role=runner.Role.RESEARCHER),
            ]

        def inject_prompts(self, agents, context):
            calls.append(("inject_prompts", agents, context))
            return agents

    def fake_mark_malicious(agents, m, rng=None):
        calls.append(("mark_malicious", m, rng))
        agents[0].is_malicious = True
        return agents

    monkeypatch.setattr(runner, "_resolve_domain_for_config", lambda exp_config: FakeDomain())
    monkeypatch.setattr(runner, "mark_malicious", fake_mark_malicious)
    monkeypatch.setattr(runner, "malicious_count_from_label", lambda m, total_agents: 1)

    exp_config = runner.ExperimentConfig(
        rep=1,
        attack_type=runner.AttackType.SUBOPTIMAL_FIXATION,
        m="1",
        d=1,
        domain="knowledge_qa",
        condition_name="single_attacker_one_detector",
    )
    task = {"task_id": "t1", "prompt": "prompt", "answer": "answer"}

    prepared = runner._prepare_agents_for_task(exp_config, task, 0)

    assert prepared["domain"].name == "knowledge_qa"
    assert prepared["malicious_count"] == 1
    assert prepared["detector_ids"] == [1000]
    assert prepared["detector_visible"] is True
    assert prepared["tool_knowledge"] is True
    assert prepared["interrogation_turns"] == runner.INTERROGATION_TURNS
    assert [agent.id for agent in prepared["agents_data"]] == [1, 2]
    assert [agent.id for agent in prepared["agents_data"] if agent.is_malicious] == [1]
    assert [call[0] for call in calls] == ["assign_roles", "mark_malicious", "inject_prompts"]
    _, _, context = calls[-1]
    assert context.m == "1"
    assert context.attack_type == exp_config.attack_type
    assert context.knowledge_level == exp_config.knowledge_level
    assert context.detector_ids == [1000]
    assert context.detector_visible is True
    assert context.tool_knowledge is True
    assert context.interrogation_turns == runner.INTERROGATION_TURNS


def test_run_single_task_delegates_agent_setup_through_prepare_helper(monkeypatch) -> None:
    calls: list[str] = []

    @dataclass
    class FakeAgent:
        id: int
        role: runner.Role
        is_malicious: bool = False

    class FakeWorkerAgent:
        def __init__(self, agent_data, task_description, **kwargs):
            self.id = agent_data.id
            self.agent_data = agent_data

    class FakeLogger:
        db_path = "fake.db"

    capabilities = type("Caps", (), {"language_only_permissions": False})()

    class FakeSimulation:
        def __init__(self, workers, detectors, total_turns, experiment_id, metadata, domain, domain_capabilities):
            calls.append("simulation_init")
            assert domain_capabilities is capabilities
            self.logger = FakeLogger()

        async def run(self):
            calls.append("simulation_run")
            return [], []

    class FakeEvaluator:
        def __init__(self, db_path, domain, domain_capabilities):
            calls.append("evaluator_init")
            assert domain_capabilities is capabilities

        def compute_unsafe_output_rate(self):
            return 0.0

        def compute_functional_correctness(self):
            return 1.0

        def compute_completion_failure(self):
            return 0.0

        def compute_attack_success(self):
            return 0.0

        def compute_latency(self):
            return 0.0

        def compute_false_positive_rate(self):
            return 0.0

        def compute_detection_rate(self):
            return 0.0

        def compute_detection_recall(self):
            return 0.0

        def compute_detection_precision(self):
            return 0.0

        def compute_attribution_accuracy(self):
            return 0.0

        def compute_detection_latency(self):
            return float("inf")

        def compute_benign_restriction_rate(self):
            return 0.0

        def compute_benign_recovery_time(self):
            return 0.0

        def close(self):
            calls.append("evaluator_close")

    def fake_prepare_agents(exp_config, task, task_index):
        calls.append("prepare_agents")
        return {
            "domain": type("Domain", (), {"name": exp_config.domain, "capabilities": capabilities})(),
            "agents_data": [FakeAgent(id=1, role=runner.Role.REPORTER)],
            "malicious_count": 0,
            "detector_ids": [],
            "detector_visible": False,
            "tool_knowledge": False,
            "interrogation_turns": None,
        }

    monkeypatch.setattr(runner, "_prepare_agents_for_task", fake_prepare_agents)
    monkeypatch.setattr(runner, "WorkerAgent", FakeWorkerAgent)
    monkeypatch.setattr(runner, "Simulation", FakeSimulation)
    monkeypatch.setattr(runner, "Evaluator", FakeEvaluator)

    exp_config = runner.ExperimentConfig(
        rep=1,
        attack_type=runner.AttackType.SUBOPTIMAL_FIXATION,
        m="0",
        d=0,
        domain="knowledge_qa",
        condition_name="clean_baseline",
    )
    task = {"task_id": "t1", "prompt": "prompt", "answer": "answer"}

    result = asyncio.run(runner._run_single_task(exp_config, task, 0))

    assert result["functional_correctness"] == 1.0
    assert calls[:4] == ["prepare_agents", "simulation_init", "simulation_run", "evaluator_init"]
    assert calls[-1] == "evaluator_close"


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
        def __init__(self, workers, detectors, total_turns, experiment_id, metadata, domain, domain_capabilities):
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
        domain="knowledge_qa",
        condition_name="clean_baseline",
    )
    task_pools = {
        exp_config.domain: [
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


def test_simulation_uses_domain_capabilities_for_permission_mode() -> None:
    class PermissionManager:
        def __init__(self):
            self.calls: list[tuple[int, bool]] = []

        def get_permission_level(self, agent_id: int, is_language_only: bool):
            self.calls.append((agent_id, is_language_only))
            return PermissionLevel.REMOVED

        def end_turn(self):
            pass

    sim = Simulation.__new__(Simulation)
    sim.turn = 0
    sim.domain = "knowledge_qa"
    sim.workers = {0: object()}
    sim.detectors = {}
    sim.message_log = []
    sim.action_log = []
    sim.recommendation_log = []
    sim.permission_manager = PermissionManager()
    sim.domain_capabilities = type("Caps", (), {"language_only_permissions": False})()

    asyncio.run(sim.run_turn())

    assert sim.permission_manager.calls == [(0, False)]


def test_simulation_defaults_to_non_language_only_permissions_without_capabilities() -> None:
    class PermissionManager:
        def __init__(self):
            self.calls: list[tuple[int, bool]] = []

        def get_permission_level(self, agent_id: int, is_language_only: bool):
            self.calls.append((agent_id, is_language_only))
            return PermissionLevel.REMOVED

        def end_turn(self):
            pass

    sim = Simulation.__new__(Simulation)
    sim.turn = 0
    sim.domain = None
    sim.workers = {0: object()}
    sim.detectors = {}
    sim.message_log = []
    sim.action_log = []
    sim.recommendation_log = []
    sim.permission_manager = PermissionManager()

    asyncio.run(sim.run_turn())

    assert sim.permission_manager.calls == [(0, False)]


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
