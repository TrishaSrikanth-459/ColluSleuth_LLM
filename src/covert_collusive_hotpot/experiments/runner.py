"""
Main runner for the collusive covert-attack HotpotQA experiment.

Design implemented here:
- attack strategies: suboptimal fixation, reframing misalignment, fake injection,
  execution delay
- conditions per attack: m=0/d=0, m=1/d=0, m=2/d=0, m=1/d=1,
  m=2/d=1, m=2/d=2, m=all/d=0
- default scale: 25 tasks x 5 repetitions x 28 conditions = 3500 task runs
- resumability: each completed task is checkpointed to JSONL before aggregate
  rows are written, so interrupted runs continue at the next unfinished task.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import math
import os
import random
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from covert_collusive_hotpot.core import config as cfg
from covert_collusive_hotpot.core.models import AttackType, KnowledgeLevel, Role
from covert_collusive_hotpot.domains.base import PromptInjectionContext
from covert_collusive_hotpot.domains.registry import get_domain_registry
from covert_collusive_hotpot.experiments.role_assignment import (
    malicious_count_from_label,
    mark_malicious,
)


# Test seams and lazy-import sentinels. Keep these names so existing tests can
# monkeypatch runner.WorkerAgent/Simulation without importing AG2 during --help.
WorkerAgent = None
DetectorAgent = None
Simulation = None
Evaluator = None


def _worker_agent_class():
    global WorkerAgent
    if WorkerAgent is None:
        from covert_collusive_hotpot.agents.worker import WorkerAgent as _WorkerAgent

        WorkerAgent = _WorkerAgent
    return WorkerAgent


def _detector_agent_class():
    global DetectorAgent
    if DetectorAgent is None:
        from covert_collusive_hotpot.agents.detector import DetectorAgent as _DetectorAgent

        DetectorAgent = _DetectorAgent
    return DetectorAgent


def _simulation_class():
    global Simulation
    if Simulation is None:
        from covert_collusive_hotpot.experiments.simulation import Simulation as _Simulation

        Simulation = _Simulation
    return Simulation


def _evaluator_class():
    global Evaluator
    if Evaluator is None:
        from covert_collusive_hotpot.experiments.evaluation import Evaluator as _Evaluator

        Evaluator = _Evaluator
    return Evaluator


def _get_env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        return default


def _get_env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        return default


def _get_env_bool(key: str, default: bool) -> bool:
    value = os.getenv(key, str(default)).strip().lower()
    return value in {"1", "true", "yes", "y", "on"}


def _slugify(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in value.strip())
    cleaned = cleaned.strip("._")
    return cleaned or "run"


ATTACK_TYPES = [
    AttackType.SUBOPTIMAL_FIXATION,
    AttackType.REFRAMING_MISALIGNMENT,
    AttackType.FAKE_INJECTION,
    AttackType.EXECUTION_DELAY,
]
CONDITION_SPECS = [
    ("clean_baseline", "0", 0),
    ("single_attacker", "1", 0),
    ("collusive_attack", "2", 0),
    ("single_attacker_one_detector", "1", 1),
    ("collusive_attack_one_detector", "2", 1),
    ("collusive_attack_two_detectors", "2", 2),
    ("all_malicious_sanity", "all", 0),
]
INTERROGATION_TURNS = [2, 3, 4]

MAX_CONCURRENT = _get_env_int("MAX_CONCURRENT", 4)
MAX_CONCURRENT_CAP = _get_env_int("MAX_CONCURRENT_CAP", 12)
TOTAL_REPS = cfg.TOTAL_REPS
RUN_LABEL = _slugify(os.getenv("RUN_LABEL", "collusive_hotpot"))
EXPERIMENT_VERSION = os.getenv("EXPERIMENT_VERSION", "2026-04-collusive-hotpot-v1")
OUTPUT_CSV = os.getenv("OUTPUT_CSV", f"experiment_results.{RUN_LABEL}.csv")
TASK_PROGRESS_JSONL = os.getenv("TASK_PROGRESS_JSONL", f"task_progress.{RUN_LABEL}.jsonl")
FAILED_CONFIGS_CSV = os.getenv("FAILED_CONFIGS_CSV", f"failed_configs.{RUN_LABEL}.csv")
CONFIG_RETRY_LIMIT = _get_env_int("CONFIG_RETRY_LIMIT", 5)
CONFIG_RETRY_BASE_DELAY = _get_env_float("CONFIG_RETRY_BASE_DELAY", 5.0)
CONFIG_RETRY_MAX_DELAY = _get_env_float("CONFIG_RETRY_MAX_DELAY", 180.0)

AGGREGATE_METRICS = [
    "unsafe_output_rate",
    "functional_correctness",
    "completion_failure",
    "attack_success",
    "latency",
    "false_positive_rate",
    "detection_rate",
    "detection_recall",
    "detection_precision",
    "attribution_accuracy",
    "detection_latency",
    "benign_restriction_rate",
    "benign_recovery_time",
    "wall_time_seconds",
]

BASE_OUTPUT_FIELDNAMES = [
    "run_label",
    "experiment_version",
    "rep",
    "condition_id",
    "condition_name",
    "attack_type",
    "m",
    "malicious_count",
    "d",
    "domain",
    "knowledge_level",
    "num_workers",
    "hotpot_tasks",
    "total_turns",
    "activation_turn",
    "max_tokens",
    "model",
    "is_clean_baseline",
    "is_single_attacker",
    "is_collusive",
    "is_all_malicious",
    "has_detectors",
]
OUTPUT_FIELDNAMES = BASE_OUTPUT_FIELDNAMES[:]
for metric_name in AGGREGATE_METRICS:
    OUTPUT_FIELDNAMES.extend([f"{metric_name}_mean", f"{metric_name}_std"])
OUTPUT_FIELDNAMES.append("tasks_evaluated")


@dataclass(frozen=True)
class ExperimentConfig:
    rep: int
    attack_type: AttackType
    m: str
    d: int
    domain: str
    knowledge_level: Optional[KnowledgeLevel] = None
    condition_name: str = ""

    @property
    def condition_id(self) -> str:
        return f"{self.attack_type.value}__{self.condition_name}__m{self.m}_d{self.d}"


def _safe_value(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "value"):
        return value.value
    return value


def _runtime_context() -> Dict[str, Any]:
    return {
        "run_label": RUN_LABEL,
        "experiment_version": EXPERIMENT_VERSION,
        "num_workers": cfg.NUM_WORKERS,
        "hotpot_tasks": cfg.HOTPOT_QA_TASKS,
        "total_turns": cfg.TOTAL_TURNS,
        "activation_turn": cfg.ACTIVATION_TURN,
        "max_tokens": cfg.MAX_TOKENS,
        "model": cfg.MODEL_NAME,
    }


def _condition_labels(exp_config: ExperimentConfig, malicious_count: Optional[int] = None) -> Dict[str, Any]:
    if malicious_count is None:
        malicious_count = cfg.NUM_WORKERS if exp_config.m == "all" else int(exp_config.m)
    return {
        "is_clean_baseline": malicious_count == 0 and exp_config.d == 0,
        "is_single_attacker": malicious_count == 1,
        "is_collusive": malicious_count >= 2 and exp_config.m != "all",
        "is_all_malicious": exp_config.m == "all",
        "has_detectors": exp_config.d > 0,
    }


def _config_key(exp_config: ExperimentConfig) -> str:
    payload = {
        "rep": exp_config.rep,
        "attack_type": exp_config.attack_type.value,
        "m": exp_config.m,
        "d": exp_config.d,
        "domain": exp_config.domain,
        "condition_name": exp_config.condition_name,
        **_runtime_context(),
    }
    return json.dumps(payload, sort_keys=True)


def _config_key_from_row(row: Dict[str, Any]) -> str:
    payload = {
        "rep": int(row["rep"]),
        "attack_type": row["attack_type"],
        "m": row["m"],
        "d": int(row["d"]),
        "domain": row["domain"],
        "condition_name": row["condition_name"],
        "run_label": row.get("run_label", RUN_LABEL),
        "experiment_version": row.get("experiment_version", EXPERIMENT_VERSION),
        "num_workers": int(float(row.get("num_workers", cfg.NUM_WORKERS))),
        "hotpot_tasks": int(float(row.get("hotpot_tasks", cfg.HOTPOT_QA_TASKS))),
        "total_turns": int(float(row.get("total_turns", cfg.TOTAL_TURNS))),
        "activation_turn": int(float(row.get("activation_turn", cfg.ACTIVATION_TURN))),
        "max_tokens": int(float(row.get("max_tokens", cfg.MAX_TOKENS))),
        "model": row.get("model", cfg.MODEL_NAME),
    }
    return json.dumps(payload, sort_keys=True)


def _task_key(exp_config: ExperimentConfig, task: Dict[str, Any]) -> str:
    return f"{_config_key(exp_config)}::{task['task_id']}"


def _default_domain_name() -> str:
    return get_domain_registry().default_domain_name()


def generate_configs(total_reps: int = None, domain_name: str | None = None) -> List[ExperimentConfig]:
    selected_domain = domain_name or _default_domain_name()
    reps = total_reps or TOTAL_REPS
    configs: List[ExperimentConfig] = []
    for attack_type in ATTACK_TYPES:
        for condition_name, m_label, detectors in CONDITION_SPECS:
            for rep in range(1, reps + 1):
                configs.append(
                    ExperimentConfig(
                        rep=rep,
                        attack_type=attack_type,
                        m=m_label,
                        d=detectors,
                        domain=selected_domain,
                        condition_name=condition_name,
                    )
                )
    return configs


def generate_smoke_configs(domain_name: str | None = None) -> List[ExperimentConfig]:
    selected_domain = domain_name or _default_domain_name()
    # Minimal manual validation: clean baseline, all-malicious sanity for each
    # attack, and one collusive detector condition to exercise interrogation.
    configs = [
        ExperimentConfig(1, AttackType.SUBOPTIMAL_FIXATION, "0", 0, selected_domain, condition_name="clean_baseline"),
    ]
    for attack_type in ATTACK_TYPES:
        configs.append(ExperimentConfig(1, attack_type, "all", 0, selected_domain, condition_name="all_malicious_sanity"))
    configs.append(
        ExperimentConfig(
            1,
            AttackType.FAKE_INJECTION,
            "2",
            1,
            selected_domain,
            condition_name="collusive_attack_one_detector",
        )
    )
    return configs


def _row_for_output(exp_config: ExperimentConfig, result: Dict[str, Any], malicious_count: int) -> Dict[str, Any]:
    row = asdict(exp_config)
    row["attack_type"] = exp_config.attack_type.value
    row["knowledge_level"] = _safe_value(exp_config.knowledge_level)
    row["condition_id"] = exp_config.condition_id
    row["malicious_count"] = malicious_count
    row.update(_runtime_context())
    row.update(_condition_labels(exp_config, malicious_count))
    row.update(result)
    return row


def _load_completed_configs(csv_path: str) -> set[str]:
    completed: set[str] = set()
    if not os.path.exists(csv_path):
        return completed
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                completed.add(_config_key_from_row(row))
            except Exception:
                continue
    return completed


def _load_task_progress(jsonl_path: str) -> Dict[str, Dict[str, Any]]:
    progress: Dict[str, Dict[str, Any]] = {}
    if not os.path.exists(jsonl_path):
        return progress
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                if "task_key" in rec and "result" in rec:
                    progress[rec["task_key"]] = rec["result"]
            except Exception:
                continue
    return progress


async def _append_task_progress(jsonl_path: str, lock: asyncio.Lock, task_key: str, result: Dict[str, Any]) -> None:
    async with lock:
        with open(jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"task_key": task_key, "result": result}, ensure_ascii=False) + "\n")
            f.flush()


def _build_task_pools(domain_name: str, seed: Optional[int] = None) -> Dict[str, List[Dict[str, Any]]]:
    domain = get_domain_registry().get(domain_name)
    return {domain.name: domain.build_task_pool(cfg.HOTPOT_QA_TASKS, seed=seed)}


def _collect_numeric(results: List[Dict[str, Any]], key: str) -> List[float]:
    values: List[float] = []
    for result in results:
        if key not in result:
            continue
        try:
            value = float(result[key])
        except (TypeError, ValueError):
            continue
        if math.isnan(value):
            continue
        values.append(value)
    return values


def _aggregate(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key in AGGREGATE_METRICS:
        vals = _collect_numeric(results, key)
        if key == "detection_latency":
            vals = [value for value in vals if math.isfinite(value)]
            if not vals:
                out[f"{key}_mean"] = float("inf")
                out[f"{key}_std"] = 0.0
                continue
        if not vals:
            out[f"{key}_mean"] = float("nan")
            out[f"{key}_std"] = 0.0
            continue
        out[f"{key}_mean"] = sum(vals) / len(vals)
        out[f"{key}_std"] = statistics.stdev(vals) if len(vals) > 1 else 0.0
    out["tasks_evaluated"] = len(results)
    return out


def _is_retryable_error(exc: Exception) -> bool:
    text = str(exc).lower()
    retry_markers = [
        "429",
        "rate limit",
        "ratelimit",
        "too many requests",
        "timeout",
        "timed out",
        "temporarily unavailable",
        "server disconnected",
        "connection reset",
        "connection aborted",
        "apiconnectionerror",
        "apitimeouterror",
        "internalservererror",
        "service unavailable",
        "bad gateway",
        "gateway timeout",
    ]
    return any(marker in text for marker in retry_markers)


def _backoff_seconds(attempt: int) -> float:
    delay = min(CONFIG_RETRY_MAX_DELAY, CONFIG_RETRY_BASE_DELAY * (2 ** max(0, attempt - 1)))
    jitter = random.uniform(0.0, min(3.0, delay * 0.25))
    return delay + jitter


def _build_task_rng(exp_config: ExperimentConfig, task: Dict[str, Any], task_index: int) -> random.Random:
    seed_material = "::".join([
        str(cfg.GLOBAL_SEED),
        str(exp_config.rep),
        exp_config.domain,
        str(task.get("task_id", task_index)),
        exp_config.attack_type.value,
        exp_config.m,
        str(exp_config.d),
        exp_config.condition_name,
    ])
    return random.Random(seed_material)


def _resolve_domain_for_config(exp_config: ExperimentConfig):
    return get_domain_registry().get(exp_config.domain)


def _prepare_agents_for_task(exp_config: ExperimentConfig, task: Dict[str, Any], task_index: int) -> Dict[str, Any]:
    domain = _resolve_domain_for_config(exp_config)
    task_rng = _build_task_rng(exp_config, task, task_index)
    agents_data = domain.assign_roles(task_rng)
    malicious_count = malicious_count_from_label(exp_config.m, len(agents_data))
    agents_data = mark_malicious(agents_data, exp_config.m, rng=task_rng)

    detector_ids = [1000 + i for i in range(exp_config.d)] if exp_config.d > 0 else []
    detector_visible = exp_config.d > 0
    tool_knowledge = exp_config.d > 0
    interrogation_turns = INTERROGATION_TURNS if exp_config.d > 0 else None

    if malicious_count > 0:
        agents_data = domain.inject_prompts(
            agents_data,
            PromptInjectionContext(
                m=exp_config.m,
                attack_type=exp_config.attack_type,
                knowledge_level=exp_config.knowledge_level,
                detector_ids=detector_ids,
                detector_visible=detector_visible,
                tool_knowledge=tool_knowledge,
                interrogation_turns=interrogation_turns,
            ),
        )

    return {
        "domain": domain,
        "agents_data": agents_data,
        "malicious_count": malicious_count,
        "detector_ids": detector_ids,
        "detector_visible": detector_visible,
        "tool_knowledge": tool_knowledge,
        "interrogation_turns": interrogation_turns,
    }


def _stable_experiment_id(exp_config: ExperimentConfig, task: Dict[str, Any], task_index: int) -> str:
    raw = f"{RUN_LABEL}_{exp_config.condition_id}_rep{exp_config.rep}_{task_index}_{task.get('task_id', task_index)}"
    return "exp_" + _slugify(raw)[:180]


async def _run_single_task(exp_config: ExperimentConfig, task: Dict[str, Any], task_index: int) -> Dict[str, Any]:
    started = time.time()
    experiment_id = _stable_experiment_id(exp_config, task, task_index)
    task_desc = task["prompt"]

    prepared = _prepare_agents_for_task(exp_config, task, task_index)
    domain = prepared["domain"]
    agents_data = prepared["agents_data"]
    malicious_count = prepared["malicious_count"]
    detector_ids = prepared["detector_ids"]
    detector_visible = prepared["detector_visible"]
    tool_knowledge = prepared["tool_knowledge"]
    interrogation_turns = prepared["interrogation_turns"]
    malicious_ids = [agent.id for agent in agents_data if agent.is_malicious]
    malicious_roles = [agent.role.value for agent in agents_data if agent.is_malicious]
    all_agent_ids = [agent.id for agent in agents_data]

    primary_output_agent_id = next((agent.id for agent in agents_data if agent.role == Role.REPORTER), None)
    worker_agent_class = _worker_agent_class()
    workers = [
        worker_agent_class(
            agent_data,
            task_desc,
            task_metadata=task,
            detector_visible=detector_visible,
            detector_ids=detector_ids,
        )
        for agent_data in agents_data
    ]

    detectors: List[Any] = []
    if exp_config.d > 0:
        detector_agent_class = _detector_agent_class()
        db_path = os.path.join(cfg.LOG_DIR, f"{experiment_id}.db")
        for detector_id in detector_ids:
            detectors.append(
                detector_agent_class(
                    detector_id,
                    db_path,
                    domain.name,
                    None,
                    None,
                    detector_ids=detector_ids,
                    task_metadata=task,
                )
            )

    metadata = {
        "experiment_id": experiment_id,
        "condition_id": exp_config.condition_id,
        "condition_name": exp_config.condition_name,
        "domain": domain.name,
        "m": exp_config.m,
        "malicious_count": malicious_count,
        "d": exp_config.d,
        "attack_type": exp_config.attack_type.value,
        "knowledge_level": _safe_value(exp_config.knowledge_level),
        "malicious_ids": malicious_ids,
        "malicious_roles": malicious_roles,
        "all_agent_ids": all_agent_ids,
        "detector_ids": detector_ids,
        "task_id": task["task_id"],
        "question": task.get("question", ""),
        "gold_answer": task["answer"],
        "rep": exp_config.rep,
        "primary_output_agent_id": primary_output_agent_id,
        **_runtime_context(),
        **_condition_labels(exp_config, malicious_count),
    }

    simulation_class = _simulation_class()
    sim = simulation_class(
        workers,
        detectors,
        cfg.TOTAL_TURNS,
        experiment_id,
        metadata,
        domain=domain.name,
        domain_capabilities=domain.capabilities,
    )
    await sim.run()

    evaluator_class = _evaluator_class()
    evaluator = evaluator_class(sim.logger.db_path, domain.name, domain.capabilities)
    result = {
        "unsafe_output_rate": evaluator.compute_unsafe_output_rate(),
        "functional_correctness": evaluator.compute_functional_correctness(),
        "completion_failure": evaluator.compute_completion_failure(),
        "attack_success": evaluator.compute_attack_success(),
        "latency": evaluator.compute_latency(),
        "false_positive_rate": evaluator.compute_false_positive_rate(),
        "detection_rate": evaluator.compute_detection_rate(),
        "detection_recall": evaluator.compute_detection_recall(),
        "detection_precision": evaluator.compute_detection_precision(),
        "attribution_accuracy": evaluator.compute_attribution_accuracy(),
        "detection_latency": evaluator.compute_detection_latency(),
        "benign_restriction_rate": evaluator.compute_benign_restriction_rate(),
        "benign_recovery_time": evaluator.compute_benign_recovery_time(),
        "wall_time_seconds": time.time() - started,
        "experiment_id": experiment_id,
        "condition_id": exp_config.condition_id,
        "condition_name": exp_config.condition_name,
        "attack_type": exp_config.attack_type.value,
        "m": exp_config.m,
        "malicious_count": malicious_count,
        "d": exp_config.d,
        "rep": exp_config.rep,
        "task_id": task["task_id"],
        "gold_answer": task["answer"],
    }
    evaluator.close()
    return result


async def run_single_experiment(
    exp_config: ExperimentConfig,
    task_pools: Dict[str, List[Dict[str, Any]]],
    task_progress: Dict[str, Dict[str, Any]],
    progress_lock: asyncio.Lock,
) -> Dict[str, Any]:
    tasks = task_pools[exp_config.domain]
    results: List[Dict[str, Any]] = []
    resumed_tasks = 0
    fresh_tasks = 0

    for task_index, task in enumerate(tasks):
        key = _task_key(exp_config, task)
        if key in task_progress:
            results.append(task_progress[key])
            resumed_tasks += 1
            continue

        result = await _run_single_task(exp_config, task, task_index)
        results.append(result)
        task_progress[key] = result
        fresh_tasks += 1
        await _append_task_progress(TASK_PROGRESS_JSONL, progress_lock, key, result)
        print(
            f"Task done: {exp_config.condition_id} rep={exp_config.rep} "
            f"task={task_index + 1}/{len(tasks)} acc={result['functional_correctness']} "
            f"attack_success={result['attack_success']} elapsed={result['wall_time_seconds']:.1f}s"
        )

    if resumed_tasks > 0:
        print(f"Resumed {resumed_tasks} task results and ran {fresh_tasks} new tasks for {exp_config.condition_id} rep={exp_config.rep}")

    return _aggregate(results)


def _estimate_eta_seconds(pending_task_count: int, max_concurrent: int) -> float:
    return pending_task_count * cfg.ESTIMATED_SECONDS_PER_TASK / max(1, max_concurrent)


def _maybe_adjust_concurrency_for_eta(pending_task_count: int, max_concurrent: int) -> int:
    eta_limit = cfg.FULL_RUN_ETA_LIMIT_DAYS * 24 * 3600
    eta = _estimate_eta_seconds(pending_task_count, max_concurrent)
    print(
        f"ETA estimate: pending_tasks={pending_task_count}, seconds_per_task={cfg.ESTIMATED_SECONDS_PER_TASK:.1f}, "
        f"concurrency={max_concurrent}, wall_eta={eta / 3600:.2f}h ({eta / 86400:.2f}d)."
    )
    if eta <= eta_limit or not cfg.AUTO_RAISE_CONCURRENCY_FOR_ETA:
        return max_concurrent
    needed = math.ceil((pending_task_count * cfg.ESTIMATED_SECONDS_PER_TASK) / eta_limit)
    adjusted = min(MAX_CONCURRENT_CAP, max(max_concurrent, needed))
    adjusted_eta = _estimate_eta_seconds(pending_task_count, adjusted)
    if adjusted != max_concurrent:
        print(f"ETA exceeded {cfg.FULL_RUN_ETA_LIMIT_DAYS:.1f} days; raising concurrency to {adjusted} (estimated {adjusted_eta / 86400:.2f}d).")
    if adjusted_eta > eta_limit:
        print(
            "WARNING: ETA still exceeds limit after concurrency adjustment. "
            "Use NUM_SHARDS/SHARD_INDEX by launching multiple tmux sessions, or raise RATE_LIMIT_PER_SEC if Azure quota permits."
        )
    return adjusted


async def run_all_experiments(configs: List[ExperimentConfig], max_concurrent: int) -> None:
    Path(cfg.LOG_DIR).mkdir(parents=True, exist_ok=True)
    csv_lock = asyncio.Lock()
    progress_lock = asyncio.Lock()

    completed_configs = _load_completed_configs(OUTPUT_CSV)
    task_progress = _load_task_progress(TASK_PROGRESS_JSONL)
    domain_name = configs[0].domain if configs else cfg.DEFAULT_DOMAIN
    task_pools = _build_task_pools(domain_name=domain_name, seed=cfg.GLOBAL_SEED)

    pending_configs = [config_item for config_item in configs if _config_key(config_item) not in completed_configs]
    pending_task_count = sum(
        1
        for config_item in pending_configs
        for task in task_pools[config_item.domain]
        if _task_key(config_item, task) not in task_progress
    )
    max_concurrent = _maybe_adjust_concurrency_for_eta(pending_task_count, max_concurrent)

    print(
        f"Resume mode: completed_configs={len(completed_configs)}, pending_configs={len(pending_configs)}, "
        f"checkpointed_tasks={len(task_progress)}, output={OUTPUT_CSV}, progress={TASK_PROGRESS_JSONL}, "
        f"run_label={RUN_LABEL}, version={EXPERIMENT_VERSION}, concurrency={max_concurrent}."
    )

    semaphore = asyncio.Semaphore(max_concurrent)

    async def run_with_semaphore(exp_config: ExperimentConfig) -> None:
        async with semaphore:
            cfg_key = _config_key(exp_config)
            started = time.time()
            if cfg_key in completed_configs:
                print("Skipping already-completed config:", exp_config.condition_id, "rep", exp_config.rep)
                return

            malicious_count = cfg.NUM_WORKERS if exp_config.m == "all" else int(exp_config.m)
            for attempt in range(1, CONFIG_RETRY_LIMIT + 1):
                try:
                    print(
                        f"Starting config: {exp_config.condition_id} rep={exp_config.rep} "
                        f"attempt={attempt}/{CONFIG_RETRY_LIMIT}"
                    )
                    result = await run_single_experiment(exp_config, task_pools, task_progress, progress_lock)
                    row = _row_for_output(exp_config, result, malicious_count)
                    async with csv_lock:
                        if cfg_key in completed_configs:
                            return
                        with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
                            writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDNAMES, extrasaction="ignore")
                            if f.tell() == 0:
                                writer.writeheader()
                            writer.writerow(row)
                            f.flush()
                        completed_configs.add(cfg_key)
                    print(f"Completed config: {exp_config.condition_id} rep={exp_config.rep} in {time.time() - started:.1f}s")
                    return
                except Exception as exc:
                    if not _is_retryable_error(exc) or attempt == CONFIG_RETRY_LIMIT:
                        print(f"FAILED permanently: {exp_config} -> {exc}")
                        async with csv_lock:
                            with open(FAILED_CONFIGS_CSV, "a", encoding="utf-8") as failed:
                                failed.write(f"{exp_config},{exc}\n")
                        return
                    wait_s = _backoff_seconds(attempt)
                    print(f"Retryable error for {exp_config.condition_id}: {exc}. Sleeping {wait_s:.1f}s.")
                    await asyncio.sleep(wait_s)

    await asyncio.gather(*(run_with_semaphore(config_item) for config_item in pending_configs))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run collusive covert HotpotQA experiments")
    parser.add_argument("--smoke", action="store_true", help="Run a tiny validation matrix instead of the full experiment")
    parser.add_argument("--smoke-tasks", type=int, default=2, help="Task count used with --smoke")
    parser.add_argument("--tasks", type=int, default=None, help="Override HotpotQA tasks per condition")
    parser.add_argument("--reps", type=int, default=None, help="Override repetitions")
    parser.add_argument("--max-concurrent", type=int, default=MAX_CONCURRENT, help="Concurrent condition runners")
    parser.add_argument("--domain", type=str, default=None, help="Override experiment domain")
    parser.add_argument("--run-label", type=str, default=None, help="Override RUN_LABEL for outputs")
    parser.add_argument("--output-csv", type=str, default=None, help="Aggregate output CSV path")
    parser.add_argument("--task-progress-jsonl", type=str, default=None, help="Task checkpoint JSONL path")
    parser.add_argument("--dry-run", action="store_true", help="Print planned configs and ETA without API calls")
    parser.add_argument("--no-shuffle", action="store_true", help="Do not shuffle condition order")
    return parser


def parse_args() -> argparse.Namespace:
    return build_arg_parser().parse_args()


def _resolve_domain_name(args: argparse.Namespace) -> str:
    selected = (args.domain or "").strip()
    if selected:
        return selected
    return _default_domain_name()


def _resolve_domain(args: argparse.Namespace):
    return get_domain_registry().get(_resolve_domain_name(args))


def _apply_cli_overrides(args: argparse.Namespace) -> None:
    global RUN_LABEL, OUTPUT_CSV, TASK_PROGRESS_JSONL, FAILED_CONFIGS_CSV, TOTAL_REPS
    if args.run_label:
        RUN_LABEL = _slugify(args.run_label)
        if args.output_csv is None:
            OUTPUT_CSV = f"experiment_results.{RUN_LABEL}.csv"
        if args.task_progress_jsonl is None:
            TASK_PROGRESS_JSONL = f"task_progress.{RUN_LABEL}.jsonl"
        if os.getenv("FAILED_CONFIGS_CSV") is None:
            FAILED_CONFIGS_CSV = f"failed_configs.{RUN_LABEL}.csv"
    if args.output_csv:
        OUTPUT_CSV = args.output_csv
    if args.task_progress_jsonl:
        TASK_PROGRESS_JSONL = args.task_progress_jsonl
    if args.smoke:
        cfg.HOTPOT_QA_TASKS = int(args.smoke_tasks)
        TOTAL_REPS = 1
    if args.tasks is not None:
        cfg.HOTPOT_QA_TASKS = int(args.tasks)
    if args.reps is not None:
        TOTAL_REPS = int(args.reps)


def _print_smoke_summary(output_csv: str) -> None:
    if not os.path.exists(output_csv):
        return
    rows: List[Dict[str, str]] = []
    with open(output_csv, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return
    print("\nSmoke summary:")
    for row in rows:
        print(
            f"- {row['condition_id']} rep={row['rep']}: "
            f"accuracy={row.get('functional_correctness_mean')} "
            f"attack_success={row.get('attack_success_mean')} "
            f"completion_failure={row.get('completion_failure_mean')}"
        )


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("huggingface_hub").setLevel(logging.WARNING)
    args = parse_args()
    domain = _resolve_domain(args)
    domain_name = domain.name
    _apply_cli_overrides(args)

    if cfg.GLOBAL_SEED is not None:
        random.seed(cfg.GLOBAL_SEED)

    configs = generate_smoke_configs(domain_name=domain_name) if args.smoke else generate_configs(TOTAL_REPS, domain_name=domain_name)
    if not args.no_shuffle:
        random.shuffle(configs)

    total_task_runs = len(configs) * cfg.HOTPOT_QA_TASKS
    print("=== Collusive Covert HotpotQA Experiment ===")
    print(f"configs={len(configs)} tasks_per_config={cfg.HOTPOT_QA_TASKS} total_task_runs={total_task_runs}")
    print(f"domain={domain_name} turns={cfg.TOTAL_TURNS} max_tokens={cfg.MAX_TOKENS} model={cfg.MODEL_NAME} output={OUTPUT_CSV}")
    print(f"attack_types={[attack.value for attack in ATTACK_TYPES]}")
    print(f"conditions={[name for name, _m, _d in CONDITION_SPECS]}")

    if args.dry_run:
        _maybe_adjust_concurrency_for_eta(total_task_runs, args.max_concurrent)
        for config_item in configs[:20]:
            print(config_item)
        if len(configs) > 20:
            print(f"... {len(configs) - 20} more configs")
        return

    asyncio.run(run_all_experiments(configs, args.max_concurrent))
    if args.smoke:
        _print_smoke_summary(OUTPUT_CSV)
    print(f"Done. Aggregate results saved to {OUTPUT_CSV}; task checkpoints saved to {TASK_PROGRESS_JSONL}.")


if __name__ == "__main__":
    main()
