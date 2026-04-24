"""
Main experiment runner for the collaborative knowledge-QA study.
"""
from __future__ import annotations

import asyncio
import csv
import logging
import math
import os
import random
import statistics
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

import config as cfg
from agent import WorkerAgent
from detector_agent import DetectorAgent
from evaluation import Evaluator
from hotpot_loader import load_hotpotqa_tasks
from models import AttackType, KnowledgeLevel, Role
from prompt_injection import inject_hidden_prompts
from role_assigner import assign_roles, mark_malicious
from simulation import Simulation


def _get_env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        return default


MAX_CONCURRENT = _get_env_int("MAX_CONCURRENT", 5)
TOTAL_REPS = _get_env_int("TOTAL_REPS", 10)
OUTPUT_CSV = os.getenv("OUTPUT_CSV", "experiment_results.csv")
DOMAIN = "knowledge_qa"
ATTACK_TYPES = [AttackType.LINGUISTIC_COLLUSION, AttackType.MULTIMODAL_HIDING]
OUTPUT_FIELDNAMES = [
    "rep",
    "attack_type",
    "m",
    "d",
    "domain",
    "knowledge_level",
    "unsafe_output_rate_mean",
    "unsafe_output_rate_std",
    "functional_correctness_mean",
    "functional_correctness_std",
    "latency_mean",
    "latency_std",
    "false_positive_rate_mean",
    "false_positive_rate_std",
    "detection_rate_mean",
    "detection_rate_std",
    "detection_latency_mean",
    "detection_latency_std",
    "benign_restriction_rate_mean",
    "benign_restriction_rate_std",
    "benign_recovery_time_mean",
    "benign_recovery_time_std",
    "tasks_evaluated",
]


@dataclass
class ExperimentConfig:
    rep: int
    attack_type: AttackType
    m: int
    d: int
    domain: str
    knowledge_level: Optional[KnowledgeLevel]


def generate_configs() -> List[ExperimentConfig]:
    configs: List[ExperimentConfig] = []

    for d in [0, 1]:
        for rep in range(1, TOTAL_REPS + 1):
            configs.append(ExperimentConfig(rep, AttackType.NONE, 0, d, DOMAIN, None))

    for m in [1, 2]:
        for attack_type in ATTACK_TYPES:
            for rep in range(1, TOTAL_REPS + 1):
                configs.append(ExperimentConfig(rep, attack_type, m, 0, DOMAIN, None))

    for m in [1, 2]:
        for attack_type in ATTACK_TYPES:
            for knowledge_level in [
                KnowledgeLevel.UNAWARE,
                KnowledgeLevel.AWARE_OF_PRESENCE,
                KnowledgeLevel.FULLY_PREPARED,
            ]:
                for rep in range(1, TOTAL_REPS + 1):
                    configs.append(ExperimentConfig(rep, attack_type, m, 1, DOMAIN, knowledge_level))
    return configs


def _row_for_output(exp_config: ExperimentConfig, result: Dict[str, Any]) -> Dict[str, Any]:
    row = asdict(exp_config)
    row["attack_type"] = row["attack_type"].value if hasattr(row["attack_type"], "value") else row["attack_type"]
    row["knowledge_level"] = row["knowledge_level"].value if hasattr(row["knowledge_level"], "value") else row["knowledge_level"]
    row.update(result)
    return row


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
    metrics = [
        "unsafe_output_rate",
        "functional_correctness",
        "latency",
        "false_positive_rate",
        "detection_rate",
        "detection_latency",
        "benign_restriction_rate",
        "benign_recovery_time",
    ]
    out: Dict[str, Any] = {}
    for key in metrics:
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


def _build_task_pools(seed: Optional[int] = None) -> Dict[str, List[Dict[str, Any]]]:
    return {DOMAIN: load_hotpotqa_tasks(cfg.HOTPOT_QA_TASKS, seed=seed)}


def _build_task_rng(exp_config: ExperimentConfig, task: Dict[str, Any], task_index: int) -> random.Random:
    seed_material = "::".join([
        str(cfg.GLOBAL_SEED),
        str(exp_config.rep),
        str(exp_config.domain),
        str(task.get("task_id", task_index)),
        str(exp_config.attack_type.value if hasattr(exp_config.attack_type, "value") else exp_config.attack_type),
        str(exp_config.m),
        str(exp_config.d),
        str(exp_config.knowledge_level.value if getattr(exp_config.knowledge_level, "value", None) else exp_config.knowledge_level),
    ])
    return random.Random(seed_material)


async def _run_single_task(exp_config: ExperimentConfig, task: Dict[str, Any], task_index: int) -> Dict[str, Any]:
    task_rng = _build_task_rng(exp_config, task, task_index)
    experiment_id = f"exp_{int(time.time())}_{task_rng.randint(1000, 9999)}_{task_index}"
    task_desc = task["prompt"]

    agents_data = assign_roles(exp_config.domain, rng=task_rng)
    agents_data = mark_malicious(agents_data, exp_config.m, rng=task_rng)

    malicious_ids = [agent.id for agent in agents_data if agent.is_malicious]
    malicious_roles = [agent.role.value for agent in agents_data if agent.is_malicious]
    all_agent_ids = [agent.id for agent in agents_data]
    detector_ids = [1000 + i for i in range(exp_config.d)] if exp_config.d > 0 else []

    detector_visible = False
    tool_knowledge = False
    interrogation_turns = None
    if exp_config.m > 0 and exp_config.d > 0 and exp_config.knowledge_level:
        if exp_config.knowledge_level == KnowledgeLevel.AWARE_OF_PRESENCE:
            detector_visible = True
        elif exp_config.knowledge_level == KnowledgeLevel.FULLY_PREPARED:
            detector_visible = True
            interrogation_turns = [4, 6, 8]

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

    primary_output_agent_id = next((agent.id for agent in agents_data if agent.role == Role.REPORTER), None)
    workers = [
        WorkerAgent(
            agent_data,
            task_desc,
            detector_visible=detector_visible,
            detector_ids=detector_ids,
        )
        for agent_data in agents_data
    ]

    detectors = []
    if exp_config.d > 0:
        db_path = os.path.join(cfg.LOG_DIR, f"{experiment_id}.db")
        for detector_id in detector_ids:
            detectors.append(
                DetectorAgent(
                    detector_id,
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
        "attack_type": exp_config.attack_type.value if hasattr(exp_config.attack_type, "value") else exp_config.attack_type,
        "knowledge_level": exp_config.knowledge_level.value if getattr(exp_config.knowledge_level, "value", None) else exp_config.knowledge_level,
        "malicious_ids": malicious_ids,
        "malicious_roles": malicious_roles,
        "all_agent_ids": all_agent_ids,
        "task_id": task["task_id"],
        "gold_answer": task["answer"],
        "rep": exp_config.rep,
        "primary_output_agent_id": primary_output_agent_id,
    }

    sim = Simulation(workers, detectors, cfg.TOTAL_TURNS, experiment_id, metadata, exp_config.domain)
    await sim.run()

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


async def run_single_experiment(exp_config: ExperimentConfig, task_pools: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
    tasks = task_pools[exp_config.domain]
    results = []
    for task_index, task in enumerate(tasks):
        results.append(await _run_single_task(exp_config, task, task_index))
    return _aggregate(results)


async def run_all_experiments(configs: List[ExperimentConfig], max_concurrent: int) -> None:
    task_pools = _build_task_pools(seed=cfg.GLOBAL_SEED)
    semaphore = asyncio.Semaphore(max_concurrent)

    async def run_with_semaphore(exp_config: ExperimentConfig) -> None:
        async with semaphore:
            print(f"Starting: {exp_config}")
            start = time.time()
            try:
                result = await run_single_experiment(exp_config, task_pools)
                row = _row_for_output(exp_config, result)
                with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDNAMES)
                    if f.tell() == 0:
                        writer.writeheader()
                    writer.writerow(row)
                print(f"Completed: {exp_config} in {time.time() - start:.2f}s")
            except Exception as exc:
                print(f"FAILED: {exp_config} – {exc}")
                with open("failed_configs.csv", "a", encoding="utf-8") as failed:
                    failed.write(f"{exp_config},{exc}\n")

    await asyncio.gather(*(run_with_semaphore(config) for config in configs))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if cfg.GLOBAL_SEED is not None:
        random.seed(cfg.GLOBAL_SEED)
    all_configs = generate_configs()
    random.shuffle(all_configs)
    print(f"Total experiments: {len(all_configs)}")
    asyncio.run(run_all_experiments(all_configs, MAX_CONCURRENT))
    print(f"Done. Results saved to {OUTPUT_CSV}")
