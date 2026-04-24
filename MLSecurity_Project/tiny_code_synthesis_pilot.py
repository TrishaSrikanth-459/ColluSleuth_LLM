"""
Extremely small code-synthesis smoke pilot.

This is the first thing to run after the fixes land. It checks the evaluator,
result separation, and basic detector/non-detector plumbing on just two tasks.
"""
from __future__ import annotations

import asyncio
import importlib
import os
import random


def _configure_env() -> None:
    os.environ.setdefault("RUN_LABEL", "code_smoke_pilot")
    os.environ.setdefault("TOTAL_REPS", "1")
    os.environ.setdefault("HOTPOT_QA_TASKS", "0")
    os.environ.setdefault("SWE_BENCH_TASKS", "2")
    os.environ.setdefault("TOTAL_TURNS", "4")
    os.environ.setdefault("ACTIVATION_TURN", "1")
    os.environ.setdefault("MAX_CONCURRENT", "1")
    os.environ.setdefault("MIN_CONCURRENT", "1")
    os.environ.setdefault("MAX_CONCURRENT_CAP", "1")
    os.environ.setdefault("ADAPTIVE_CONCURRENCY", "false")
    os.environ.setdefault("ENABLE_FALCO_DYNAMIC_ANALYSIS", "false")
    os.environ.setdefault("GLOBAL_SEED", "42")


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
            d=0,
            domain="code_synthesis",
            knowledge_level=None,
        ),
        runner.ExperimentConfig(
            rep=1,
            attack_type=runner.AttackType.NONE,
            m=0,
            d=1,
            domain="code_synthesis",
            knowledge_level=None,
        ),
    ]
    asyncio.run(runner.run_all_experiments(configs, max_concurrent=1))


if __name__ == "__main__":
    main()
