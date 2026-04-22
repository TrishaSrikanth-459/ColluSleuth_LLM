"""
Cheap smoke pilot for the whole stack.

This stays intentionally small and writes to pilot-specific output files so it
cannot contaminate the main experiment resume state.
"""
from __future__ import annotations

import asyncio
import importlib
import os
import random


def _configure_env() -> None:
    os.environ.setdefault("RUN_LABEL", "smoke_pilot")
    os.environ.setdefault("TOTAL_REPS", "1")
    os.environ.setdefault("HOTPOT_QA_TASKS", "2")
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

    runner = importlib.import_module("parallel_experiment_runner")
    config = importlib.import_module("config")

    if config.GLOBAL_SEED is not None:
        random.seed(config.GLOBAL_SEED)

    configs = runner.generate_configs()
    asyncio.run(runner.run_all_experiments(configs, max_concurrent=1))


if __name__ == "__main__":
    main()
