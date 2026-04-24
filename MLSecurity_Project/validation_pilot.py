"""
Small QA-only validation pilot.

Kept separate from the main runs and from the code smoke pilot so it cannot
pollute the primary CSV/task-progress files.
"""
from __future__ import annotations

import asyncio
import importlib
import os
import random


def _configure_env() -> None:
    os.environ.setdefault("RUN_LABEL", "validation_qa_pilot")
    os.environ.setdefault("TOTAL_REPS", "1")
    os.environ.setdefault("HOTPOT_QA_TASKS", "5")
    os.environ.setdefault("SWE_BENCH_TASKS", "0")
    os.environ.setdefault("TOTAL_TURNS", "3")
    os.environ.setdefault("ACTIVATION_TURN", "1")
    os.environ.setdefault("MAX_CONCURRENT", "1")
    os.environ.setdefault("MIN_CONCURRENT", "1")
    os.environ.setdefault("MAX_CONCURRENT_CAP", "1")
    os.environ.setdefault("ADAPTIVE_CONCURRENCY", "false")


def main() -> None:
    _configure_env()

    config = importlib.import_module("config")
    runner = importlib.import_module("parallel_experiment_runner")

    if config.GLOBAL_SEED is not None:
        random.seed(config.GLOBAL_SEED)

    configs = [
        runner.ExperimentConfig(
            rep=1,
            attack_type=runner.AttackType.NONE,
            m=0,
            d=1,
            domain="knowledge_qa",
            knowledge_level=None,
        ),
        runner.ExperimentConfig(
            rep=1,
            attack_type=runner.AttackType.LINGUISTIC_COLLUSION,
            m=1,
            d=1,
            domain="knowledge_qa",
            knowledge_level=runner.KnowledgeLevel.AWARE_OF_PRESENCE,
        ),
    ]
    asyncio.run(runner.run_all_experiments(configs, max_concurrent=1))


if __name__ == "__main__":
    main()
