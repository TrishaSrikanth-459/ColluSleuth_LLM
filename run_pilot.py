"""
Cheap pilot runner for quick functional validation.
Does NOT modify experiment_runner.py or parallel_experiment_runner.py.
Adds a runtime shim so hotpot_loader accepts a 'seed' kwarg.
"""

import os
import importlib
import inspect
import sys


def _patch_hotpot_loader():
    hotpot_loader = importlib.import_module("hotpot_loader")

    try:
        sig = inspect.signature(hotpot_loader.load_hotpotqa_tasks)
        if "seed" in sig.parameters:
            return  # already supports seed
    except Exception:
        pass

    original = hotpot_loader.load_hotpotqa_tasks

    def load_hotpotqa_tasks(num_tasks: int = 100, *args, **kwargs):
        # Ignore seed/extra kwargs and defer to original
        return original(num_tasks)

    hotpot_loader.load_hotpotqa_tasks = load_hotpotqa_tasks


def main():
    # Minimal cost settings
    os.environ["HOTPOT_QA_TASKS"] = "10"
    os.environ["SWE_BENCH_TASKS"] = "5"
    os.environ["TOTAL_TURNS"] = "6"
    os.environ["ACTIVATION_TURN"] = "2"
    os.environ["TOTAL_REPS"] = "1"
    os.environ["MAX_CONCURRENT"] = "1"
    os.environ["GLOBAL_SEED"] = "42"

    # Optional: disable Falco for pilot cost/stability
    os.environ["ENABLE_FALCO_DYNAMIC_ANALYSIS"] = "false"

    _patch_hotpot_loader()

    # Import and run the existing runner module directly (no subprocess)
    runner = None
    if importlib.util.find_spec("parallel_experiment_runner"):
        runner = importlib.import_module("parallel_experiment_runner")
    elif importlib.util.find_spec("experiment_runner"):
        runner = importlib.import_module("experiment_runner")
    else:
        raise RuntimeError("Could not find parallel_experiment_runner.py or experiment_runner.py")

    # Execute the runner's main block (same effect as python file.py)
    if hasattr(runner, "main"):
        runner.main()
    else:
        # Fall back to top-level execution pattern
        if hasattr(runner, "run_all_experiments"):
            import asyncio
            configs = runner.generate_configs()
            asyncio.run(runner.run_all_experiments(configs, runner.MAX_CONCURRENT))


if __name__ == "__main__":
    main()
