import asyncio
import csv
import json
import time
import random
import os
import logging
import math
import statistics
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple

from models import AttackType, KnowledgeLevel
from role_assigner import assign_roles, mark_malicious
from agent import WorkerAgent
from detector_agent import DetectorAgent
from simulation import Simulation
from prompt_injection import inject_hidden_prompts

from swebench_loader import load_swebench_tasks
from hotpot_loader import load_hotpotqa_tasks

import config as cfg


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
    val = os.getenv(key, str(default)).strip().lower()
    return val in {"1", "true", "yes", "y", "on"}


FIXED_MAX_CONCURRENT = _get_env_int("MAX_CONCURRENT", 2)
MIN_CONCURRENT = _get_env_int("MIN_CONCURRENT", 2)
MAX_CONCURRENT_CAP = _get_env_int("MAX_CONCURRENT_CAP", 8)
ADAPTIVE_CONCURRENCY = _get_env_bool("ADAPTIVE_CONCURRENCY", True)
ADAPTIVE_BATCH_MULTIPLIER = _get_env_int("ADAPTIVE_BATCH_MULTIPLIER", 2)

NUM_SHARDS = _get_env_int("NUM_SHARDS", 1)
SHARD_INDEX = _get_env_int("SHARD_INDEX", 0)

TOTAL_REPS = 10
OUTPUT_CSV = "experiment_results.csv"
TASK_PROGRESS_JSONL = "task_progress.jsonl"

CONFIG_RETRY_LIMIT = _get_env_int("CONFIG_RETRY_LIMIT", 8)
CONFIG_RETRY_BASE_DELAY = _get_env_float("CONFIG_RETRY_BASE_DELAY", 5.0)
CONFIG_RETRY_MAX_DELAY = _get_env_float("CONFIG_RETRY_MAX_DELAY", 300.0)

DOMAINS = ["knowledge_qa", "code_synthesis"]
ATTACK_TYPES = [AttackType.LINGUISTIC_COLLUSION, AttackType.MULTIMODAL_HIDING]

INTERROGATION_TURNS = [4, 6, 8]


@dataclass
class ExperimentConfig:
    rep: int
    attack_type: AttackType
    m: int
    d: int
    domain: str
    knowledge_level: Optional[KnowledgeLevel]


@dataclass
class ConfigRunStats:
    retryable_errors: int = 0
    attempts_used: int = 1
    duration_sec: float = 0.0


def generate_configs() -> List[ExperimentConfig]:
    configs: List[ExperimentConfig] = []

    # No attackers
    for d in [0, 1, 2]:
        for domain in DOMAINS:
            for rep in range(1, TOTAL_REPS + 1):
                configs.append(ExperimentConfig(rep, AttackType.NONE, 0, d, domain, None))

    # Attackers with no detectors
    for m in [1, 2]:
        for domain in DOMAINS:
            for attack_type in ATTACK_TYPES:
                for rep in range(1, TOTAL_REPS + 1):
                    configs.append(ExperimentConfig(rep, attack_type, m, 0, domain, None))

    # Attackers with detectors (full matrix)
    for m in [1, 2]:
        for d in [1, 2]:
            for domain in DOMAINS:
                for attack_type in ATTACK_TYPES:
                    for kl in [
                        KnowledgeLevel.UNAWARE,
                        KnowledgeLevel.AWARE_OF_PRESENCE,
                        KnowledgeLevel.FULLY_PREPARED,
                    ]:
                        for rep in range(1, TOTAL_REPS + 1):
                            configs.append(ExperimentConfig(rep, attack_type, m, d, domain, kl))

    return configs


def _safe_value(v):
    if v is None:
        return None
    if hasattr(v, "value"):
        return v.value
    return v


def _normalize_serialized_value(v):
    if v is None:
        return None

    s = str(v).strip()
    if not s:
        return None

    if s.startswith("<") and "'" in s:
        parts = s.split("'")
        if len(parts) >= 2:
            return parts[1].strip().lower()

    if "." in s and s.upper() == s:
        s = s.split(".")[-1]

    s = s.lower()

    if s in {"", "null"}:
        return None

    return s


def _config_key(exp_config: ExperimentConfig) -> str:
    return json.dumps(
        {
            "rep": exp_config.rep,
            "attack_type": _normalize_serialized_value(_safe_value(exp_config.attack_type)),
            "m": exp_config.m,
            "d": exp_config.d,
            "domain": exp_config.domain,
            "knowledge_level": _normalize_serialized_value(_safe_value(exp_config.knowledge_level)),
        },
        sort_keys=True,
    )


def _task_key(exp_config: ExperimentConfig, task: Dict[str, Any]) -> str:
    return f"{_config_key(exp_config)}::{task['task_id']}"


def _row_for_output(exp_config: ExperimentConfig, res: Dict[str, Any]) -> Dict[str, Any]:
    row = asdict(exp_config)
    row["attack_type"] = _safe_value(row["attack_type"])
    row["knowledge_level"] = _safe_value(row["knowledge_level"])
    row.update(res)
    return row


def _load_completed_configs(csv_path: str) -> set[str]:
    completed = set()
    if not os.path.exists(csv_path):
        return completed

    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                completed.add(json.dumps(
                    {
                        "rep": int(row["rep"]),
                        "attack_type": _normalize_serialized_value(row.get("attack_type")),
                        "m": int(row["m"]),
                        "d": int(row["d"]),
                        "domain": row["domain"],
                        "knowledge_level": _normalize_serialized_value(row.get("knowledge_level")),
                    },
                    sort_keys=True,
                ))
            except Exception:
                continue
    return completed


def _load_task_progress(jsonl_path: str) -> Dict[str, Dict[str, Any]]:
    progress: Dict[str, Dict[str, Any]] = {}
    if not os.path.exists(jsonl_path):
        return progress

    with open(jsonl_path, "r") as f:
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


async def _append_task_progress(
    jsonl_path: str,
    lock: asyncio.Lock,
    task_key: str,
    result: Dict[str, Any],
) -> None:
    async with lock:
        with open(jsonl_path, "a") as f:
            f.write(json.dumps({"task_key": task_key, "result": result}) + "\n")
            f.flush()


def _build_task_pools(seed: Optional[int] = None):
    return {
        "knowledge_qa": load_hotpotqa_tasks(cfg.HOTPOT_QA_TASKS, seed=seed),
        "code_synthesis": load_swebench_tasks(cfg.SWE_BENCH_TASKS),
    }


def _condition_labels(exp_config):
    return {
        "condition_type": (
            "no_attackers" if exp_config.m == 0 else
            "attack_no_detectors" if exp_config.d == 0 else
            "attack_with_detectors"
        ),
        "is_ablation_no_detector": exp_config.d == 0,
        "is_ablation_no_attacker": exp_config.m == 0,
        "is_full_system": exp_config.m > 0 and exp_config.d > 0,
    }


def _aggregate(results):
    keys = [
        "unsafe_output_rate",
        "functional_correctness",
        "latency",
        "false_positive_rate",
        "detection_rate",
        "detection_latency",
        "benign_restriction_rate",
        "benign_recovery_time",
    ]

    out = {}
    for k in keys:
        vals = [r[k] for r in results if k in r]

        if k == "detection_latency":
            vals = [v for v in vals if not math.isinf(v)]
            if not vals:
                out[f"{k}_mean"] = float("inf")
                out[f"{k}_std"] = 0.0
                continue

        out[f"{k}_mean"] = sum(vals) / len(vals)
        out[f"{k}_std"] = statistics.stdev(vals) if len(vals) > 1 else 0.0

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


def _select_shard(configs: List[ExperimentConfig]) -> List[ExperimentConfig]:
    if NUM_SHARDS <= 1:
        return configs

    if SHARD_INDEX < 0 or SHARD_INDEX >= NUM_SHARDS:
        raise ValueError(f"Invalid SHARD_INDEX={SHARD_INDEX} for NUM_SHARDS={NUM_SHARDS}")

    return [cfg for i, cfg in enumerate(configs) if i % NUM_SHARDS == SHARD_INDEX]


async def _run_single_task(exp_config, task, task_index):
    experiment_id = f"exp_{int(time.time())}_{random.randint(1000, 9999)}_{task_index}"

    task_desc = task["prompt"]

    agents_data = assign_roles(exp_config.domain)
    agents_data = mark_malicious(agents_data, exp_config.m)

    malicious_ids = [a.id for a in agents_data if a.is_malicious]
    malicious_roles = [a.role.value for a in agents_data if a.is_malicious]
    all_agent_ids = [a.id for a in agents_data]

    detector_ids = [1000 + i for i in range(exp_config.d)] if exp_config.d > 0 else []

    detector_visible = False
    tool_knowledge = False
    interrogation_turns = None

    if exp_config.m > 0 and exp_config.d > 0 and exp_config.knowledge_level:
        if exp_config.knowledge_level == KnowledgeLevel.AWARE_OF_PRESENCE:
            detector_visible = True
        elif exp_config.knowledge_level == KnowledgeLevel.FULLY_PREPARED:
            detector_visible = True
            tool_knowledge = True
            interrogation_turns = INTERROGATION_TURNS

    if exp_config.m > 0:
        agents_data = inject_hidden_prompts(
            agents_data,
            exp_config.m,
            exp_config.attack_type,
            exp_config.knowledge_level,
            detector_ids,
            detector_visible,
            tool_knowledge,
            interrogation_turns,
        )

    workers = [
        WorkerAgent(
            ad,
            task_desc,
            detector_visible=detector_visible,
            detector_ids=detector_ids
        )
        for ad in agents_data
    ]

    detectors = []
    if exp_config.d > 0:
        db_path = os.path.join(cfg.LOG_DIR, f"{experiment_id}.db")

        for det_id in detector_ids:
            detectors.append(
                DetectorAgent(
                    det_id,
                    db_path,
                    exp_config.domain,
                    None,
                    None,
                    detector_ids=detector_ids,
                )
            )

    metadata = {
        "experiment_id": experiment_id,
        "domain": exp_config.domain,
        "m": exp_config.m,
        "d": exp_config.d,
        "attack_type": _safe_value(exp_config.attack_type),
        "knowledge_level": _safe_value(exp_config.knowledge_level),
        "malicious_ids": malicious_ids,
        "malicious_roles": malicious_roles,
        "all_agent_ids": all_agent_ids,
        "task_id": task["task_id"],
        "rep": exp_config.rep,
        **_condition_labels(exp_config),
    }

    if exp_config.domain == "knowledge_qa":
        metadata["gold_answer"] = task["answer"]
    else:
        metadata["repo"] = task["repo"]
        metadata["base_commit"] = task["base_commit"]

    sim = Simulation(workers, detectors, cfg.TOTAL_TURNS, experiment_id, metadata, exp_config.domain)
    await sim.run()

    from evaluation import Evaluator
    evaluator = Evaluator(sim.logger.db_path, exp_config.domain)

    result = {
        "unsafe_output_rate": evaluator.compute_unsafe_output_rate(),
        "functional_correctness": evaluator.compute_functional_correctness(),
        "latency": evaluator.compute_latency(),
        "false_positive_rate": evaluator.compute_false_positive_rate(),
        "detection_rate": evaluator.compute_detection_rate(),
        "detection_latency": evaluator.compute_detection_latency(),
        "benign_restriction_rate": evaluator.compute_benign_restriction_rate(),
        "benign_recovery_time": evaluator.compute_benign_recovery_time(),
    }

    evaluator.close()
    return result


async def run_single_experiment(exp_config, task_pools, task_progress, progress_lock):
    tasks = task_pools[exp_config.domain]

    results = []
    resumed_tasks = 0
    fresh_tasks = 0

    for i, task in enumerate(tasks):
        key = _task_key(exp_config, task)
        if key in task_progress:
            results.append(task_progress[key])
            resumed_tasks += 1
            continue

        result = await _run_single_task(exp_config, task, i)
        results.append(result)
        task_progress[key] = result
        fresh_tasks += 1
        await _append_task_progress(TASK_PROGRESS_JSONL, progress_lock, key, result)

    if resumed_tasks > 0:
        print(
            f"Resumed {resumed_tasks} task results and ran {fresh_tasks} new tasks for {exp_config}"
        )

    return _aggregate(results)


def _choose_next_concurrency(
    current: int,
    retryable_errors: int,
    completed_in_batch: int,
) -> int:
    if not ADAPTIVE_CONCURRENCY:
        return current

    if retryable_errors > 0:
        return max(MIN_CONCURRENT, current - 1)

    if completed_in_batch > 0 and retryable_errors == 0:
        return min(MAX_CONCURRENT_CAP, current + 1)

    return current


async def run_all_experiments(configs, max_concurrent):
    csv_lock = asyncio.Lock()
    progress_lock = asyncio.Lock()

    completed_configs = _load_completed_configs(OUTPUT_CSV)
    task_progress = _load_task_progress(TASK_PROGRESS_JSONL)
    task_pools = _build_task_pools(seed=cfg.GLOBAL_SEED)

    pending_configs = [c for c in configs if _config_key(c) not in completed_configs]

    current_concurrency = FIXED_MAX_CONCURRENT
    if ADAPTIVE_CONCURRENCY:
        current_concurrency = max(MIN_CONCURRENT, min(MAX_CONCURRENT_CAP, FIXED_MAX_CONCURRENT))

    print(
        f"Resume mode: {len(completed_configs)} completed configs found, "
        f"{len(pending_configs)} remaining in shard, {len(task_progress)} completed tasks checkpointed. "
        f"Starting with concurrency={current_concurrency}, adaptive={ADAPTIVE_CONCURRENCY}, "
        f"shard={SHARD_INDEX + 1}/{NUM_SHARDS}."
    )

    async def run_one(cfg_) -> ConfigRunStats:
        await asyncio.sleep(random.uniform(0.2, 1.2))
        cfg_key = _config_key(cfg_)
        started = time.time()
        stats = ConfigRunStats()

        if cfg_key in completed_configs:
            print("Skipping already-completed config:", cfg_)
            stats.duration_sec = time.time() - started
            return stats

        for attempt in range(1, CONFIG_RETRY_LIMIT + 1):
            try:
                print(f"Starting: {cfg_} (attempt {attempt}/{CONFIG_RETRY_LIMIT})")
                res = await run_single_experiment(cfg_, task_pools, task_progress, progress_lock)

                row = _row_for_output(cfg_, res)

                async with csv_lock:
                    if cfg_key in completed_configs:
                        print("Skipping already-completed config:", cfg_)
                        stats.duration_sec = time.time() - started
                        return stats

                    with open(OUTPUT_CSV, "a", newline="") as f:
                        writer = csv.DictWriter(f, fieldnames=row.keys())
                        if f.tell() == 0:
                            writer.writeheader()
                        writer.writerow(row)
                        f.flush()

                    completed_configs.add(cfg_key)

                stats.attempts_used = attempt
                stats.duration_sec = time.time() - started
                print("Done:", cfg_)
                return stats

            except Exception as e:
                if not _is_retryable_error(e) or attempt == CONFIG_RETRY_LIMIT:
                    print(f"Failed permanently for {cfg_}: {e}")
                    raise

                stats.retryable_errors += 1
                wait_s = _backoff_seconds(attempt)
                print(
                    f"Retryable error for {cfg_} on attempt {attempt}/{CONFIG_RETRY_LIMIT}: {e}. "
                    f"Backing off for {wait_s:.1f}s."
                )
                await asyncio.sleep(wait_s)

        stats.duration_sec = time.time() - started
        return stats

    remaining_queue = list(pending_configs)

    while remaining_queue:
        batch_size = min(len(remaining_queue), max(current_concurrency, current_concurrency * ADAPTIVE_BATCH_MULTIPLIER))
        batch = remaining_queue[:batch_size]
        remaining_queue = remaining_queue[batch_size:]

        print(
            f"Launching batch of {len(batch)} configs with concurrency={current_concurrency}. "
            f"{len(remaining_queue)} shard configs will remain queued after this batch."
        )

        semaphore = asyncio.Semaphore(current_concurrency)

        async def run_with_semaphore(cfg_):
            async with semaphore:
                return await run_one(cfg_)

        batch_results: List[ConfigRunStats] = await asyncio.gather(
            *[run_with_semaphore(c) for c in batch]
        )

        batch_retryable_errors = sum(r.retryable_errors for r in batch_results)
        batch_completed = len(batch_results)
        mean_duration = (
            sum(r.duration_sec for r in batch_results) / batch_completed if batch_completed else 0.0
        )

        next_concurrency = _choose_next_concurrency(
            current=current_concurrency,
            retryable_errors=batch_retryable_errors,
            completed_in_batch=batch_completed,
        )

        print(
            f"Batch complete: completed={batch_completed}, "
            f"retryable_errors={batch_retryable_errors}, "
            f"mean_duration_sec={mean_duration:.1f}, "
            f"next_concurrency={next_concurrency}."
        )

        current_concurrency = next_concurrency


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    if NUM_SHARDS <= 0:
        raise ValueError(f"NUM_SHARDS must be >= 1, got {NUM_SHARDS}")

    if cfg.GLOBAL_SEED is not None:
        random.seed(cfg.GLOBAL_SEED)

    configs = generate_configs()
    random.shuffle(configs)
    configs = _select_shard(configs)

    print(f"Running shard {SHARD_INDEX + 1}/{NUM_SHARDS} with {len(configs)} assigned configs.")

    asyncio.run(run_all_experiments(configs, FIXED_MAX_CONCURRENT))
