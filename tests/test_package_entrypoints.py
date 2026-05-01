from importlib import import_module
from pathlib import Path
import csv
import os
import subprocess
import sys


def _run_wrapper_bootstrap(script_name: str, module_name: str) -> subprocess.CompletedProcess[str]:
    bootstrap_code = """
import builtins
from pathlib import Path
import runpy
import sys
import types

script = sys.argv[1]
module_name = sys.argv[2]
expected_src = str(Path(script).resolve().parent / "src")
package_name = module_name.split(".")[0]

package = types.ModuleType(package_name)
package.__path__ = []
module = types.ModuleType(module_name)
module.main = lambda: None
original_import = builtins.__import__

def checking_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == module_name:
        assert sys.path[0] == expected_src, (sys.path[0], expected_src)
        sys.modules.setdefault(package_name, package)
        sys.modules[module_name] = module
        return module
    return original_import(name, globals, locals, fromlist, level)

builtins.__import__ = checking_import
runpy.run_path(script, run_name="wrapper_bootstrap_test")
"""
    return subprocess.run(
        [
            sys.executable,
            "-S",
            "-c",
            bootstrap_code,
            script_name,
            module_name,
        ],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )


def test_packaged_entry_modules_import() -> None:
    run_module = import_module("covert_collusive_hotpot.run_experiments")
    assert callable(run_module.main)


def test_reporting_entry_module_import() -> None:
    report_module = import_module("covert_collusive_hotpot.generate_paper_assets")
    assert callable(report_module.main)


def test_readme_mentions_new_entry_points() -> None:
    readme_text = Path(__file__).resolve().parents[1].joinpath("README.md").read_text()
    assert "python -m covert_collusive_hotpot.run_experiments" in readme_text
    assert "python -m covert_collusive_hotpot.generate_paper_assets" in readme_text


def test_core_modules_import() -> None:
    config_module = import_module("covert_collusive_hotpot.core.config")
    models_module = import_module("covert_collusive_hotpot.core.models")
    logger_module = import_module("covert_collusive_hotpot.core.logging_store")
    permission_module = import_module("covert_collusive_hotpot.core.permission_manager")
    limiter_module = import_module("covert_collusive_hotpot.core.rate_limiter")

    assert config_module.MODEL_NAME
    assert hasattr(models_module, "AttackType")
    assert hasattr(logger_module, "Logger")
    assert hasattr(permission_module, "PermissionManager")
    assert hasattr(limiter_module, "rate_limited_call")


def test_agent_modules_import() -> None:
    worker_module = import_module("covert_collusive_hotpot.agents.worker")
    detector_module = import_module("covert_collusive_hotpot.agents.detector")
    assert hasattr(worker_module, "WorkerAgent")
    assert hasattr(detector_module, "DetectorAgent")


def test_experiment_modules_import() -> None:
    evaluation_module = import_module("covert_collusive_hotpot.experiments.evaluation")
    simulation_module = import_module("covert_collusive_hotpot.experiments.simulation")
    runner_module = import_module("covert_collusive_hotpot.run_experiments")

    assert hasattr(evaluation_module, "Evaluator")
    assert hasattr(simulation_module, "Simulation")
    assert callable(runner_module.main)


def test_runner_wrapper_bootstraps_from_checkout() -> None:
    result = _run_wrapper_bootstrap(
        "parallel_experiment_runner.py",
        "covert_collusive_hotpot.run_experiments",
    )
    assert result.returncode == 0
    assert result.stderr == ""


def test_report_wrapper_bootstraps_from_checkout() -> None:
    result = _run_wrapper_bootstrap(
        "generate_paper_tables_and_figures.py",
        "covert_collusive_hotpot.generate_paper_assets",
    )
    assert result.returncode == 0
    assert result.stderr == ""


def test_packaged_reporting_entry_point_executes_with_minimal_csv(tmp_path) -> None:
    input_csv = tmp_path / "results.csv"
    with input_csv.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
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
                "unsafe_output_rate_std",
                "functional_correctness_std",
                "latency_std",
                "false_positive_rate_std",
                "detection_rate_std",
                "detection_latency_std",
                "benign_restriction_rate_mean",
                "benign_recovery_time_mean",
                "benign_restriction_rate_std",
                "benign_recovery_time_std",
                "rep",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "domain": "knowledge_qa",
                "m": 0,
                "d": 0,
                "knowledge_level": "none",
                "tasks_evaluated": 100,
                "unsafe_output_rate_mean": 0.0,
                "functional_correctness_mean": 1.0,
                "latency_mean": 1.0,
                "false_positive_rate_mean": 0.0,
                "detection_rate_mean": 0.0,
                "detection_latency_mean": 0.0,
                "unsafe_output_rate_std": 0.0,
                "functional_correctness_std": 0.0,
                "latency_std": 0.0,
                "false_positive_rate_std": 0.0,
                "detection_rate_std": 0.0,
                "detection_latency_std": 0.0,
                "benign_restriction_rate_mean": 0.0,
                "benign_recovery_time_mean": 0.0,
                "benign_restriction_rate_std": 0.0,
                "benign_recovery_time_std": 0.0,
                "rep": 1,
            }
        )

    env = os.environ.copy()
    env.update(
        {
            "INPUT_CSV": str(input_csv),
            "OUTPUT_TABLE_DIR": str(tmp_path / "tables"),
            "OUTPUT_FIG_DIR": str(tmp_path / "figures"),
        }
    )
    result = subprocess.run(
        [sys.executable, "-m", "covert_collusive_hotpot.generate_paper_assets"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0
    assert (tmp_path / "tables" / "summary.csv").exists()
