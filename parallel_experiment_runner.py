import asyncio
import csv
import time
import random
import os
import logging
import math
import statistics
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

from models import AttackType, KnowledgeLevel
from role_assigner import assign_roles, mark_malicious
from agent import WorkerAgent
from detector_agent import DetectorAgent
from simulation import Simulation
from prompt_injection import inject_hidden_prompts

from swebench_loader import load_swebench_tasks
from hotpot_loader import load_hotpotqa_tasks

import config as cfg


MAX_CONCURRENT = 1
TOTAL_REPS = 10
OUTPUT_CSV = "experiment_results.csv"

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
    return v.value if hasattr(v, "value") else v


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


async def run_single_experiment(exp_config, task_pools):
    tasks = task_pools[exp_config.domain][:100]

    results = []
    for i, task in enumerate(tasks):
        results.append(await _run_single_task(exp_config, task, i))

    return _aggregate(results)


async def run_all_experiments(configs, max_concurrent):
    semaphore = asyncio.Semaphore(max_concurrent)
    task_pools = _build_task_pools(seed=cfg.GLOBAL_SEED)

    async def run_one(cfg_):
        async with semaphore:
            print("Starting:", cfg_)
            res = await run_single_experiment(cfg_, task_pools)

            row = {**asdict(cfg_), **res}

            with open(OUTPUT_CSV, "a", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=row.keys())
                if f.tell() == 0:
                    writer.writeheader()
                writer.writerow(row)

            print("Done:", cfg_)

    await asyncio.gather(*[run_one(c) for c in configs])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Reproducibility
    if cfg.GLOBAL_SEED is not None:
        random.seed(cfg.GLOBAL_SEED)

    configs = generate_configs()
    random.shuffle(configs)

    asyncio.run(run_all_experiments(configs, MAX_CONCURRENT))
