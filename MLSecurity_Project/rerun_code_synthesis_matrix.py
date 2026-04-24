"""Run the full reduced code-synthesis matrix with the current runner settings."""
from __future__ import annotations

import asyncio
import importlib
import random


def main() -> None:
    config = importlib.import_module("config")
    runner = importlib.import_module("parallel_experiment_runner")

    if config.GLOBAL_SEED is not None:
        random.seed(config.GLOBAL_SEED)

    configs = [cfg for cfg in runner.generate_configs() if cfg.domain == "code_synthesis"]
    asyncio.run(runner.run_all_experiments(configs, runner.FIXED_MAX_CONCURRENT))


if __name__ == "__main__":
    main()
