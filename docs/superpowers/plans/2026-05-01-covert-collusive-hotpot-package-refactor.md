# Covert Collusive Hotpot Package Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the flat repo into a `src`-layout package named `covert_collusive_hotpot` with clean top-level module entry points and temporary root CLI wrappers.

**Architecture:** Move shared modules into `core/`, agent code into `agents/`, and experiment orchestration into `experiments/` under `src/covert_collusive_hotpot/`. Expose `main()` through `covert_collusive_hotpot.run_experiments` and `covert_collusive_hotpot.generate_paper_assets`, then keep the existing root scripts as thin wrappers that call those packaged entry points.

**Tech Stack:** Python, pytest, setuptools `pyproject.toml`, existing runtime dependencies from `requirements.txt`

---

### Task 1: Add package scaffold and import smoke tests

**Files:**
- Create: `pyproject.toml`
- Create: `src/covert_collusive_hotpot/__init__.py`
- Create: `src/covert_collusive_hotpot/core/__init__.py`
- Create: `src/covert_collusive_hotpot/agents/__init__.py`
- Create: `src/covert_collusive_hotpot/experiments/__init__.py`
- Create: `tests/test_package_entrypoints.py`

- [ ] **Step 1: Write the failing test**

```python
from importlib import import_module
from pathlib import Path
import csv
import os
import subprocess
import sys


def test_packaged_entry_modules_import() -> None:
    run_module = import_module("covert_collusive_hotpot.run_experiments")
    report_module = import_module("covert_collusive_hotpot.generate_paper_assets")
    assert callable(run_module.main)
    assert callable(report_module.main)


def test_runner_wrapper_help_executes() -> None:
    result = subprocess.run(
        [sys.executable, "parallel_experiment_runner.py", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Run collusive covert HotpotQA experiments" in result.stdout


def test_report_wrapper_executes_with_minimal_csv(tmp_path) -> None:
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
        [sys.executable, "generate_paper_tables_and_figures.py"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert result.returncode == 0
    assert (tmp_path / "tables" / "summary.csv").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_package_entrypoints.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'covert_collusive_hotpot'` and missing wrapper behavior.

- [ ] **Step 3: Write minimal package scaffold and packaging metadata**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "covert-collusive-hotpot"
version = "0.1.0"
description = "Collusive covert-attack HotpotQA experiment package"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
  "ag2[openai]>=0.3.0",
  "python-dotenv>=0.19.0",
  "pydantic>=2.0.0",
  "pytest>=7.0.0",
  "aiohttp>=3.8.0",
  "tenacity>=8.0.0",
  "bandit>=1.7.5",
  "datasets>=2.14.0",
  "beautifulsoup4>=4.12.0",
  "ghapi>=1.0.4",
  "unidiff>=0.7.5",
  "lxml>=4.9.0",
  "tqdm>=4.65.0",
  "requests>=2.31.0",
  "scipy>=1.11.0",
  "pandas>=2.0.0",
]

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]
```

```python
# src/covert_collusive_hotpot/__init__.py
"""Top-level package for the collusive covert HotpotQA experiment."""
```

```python
# src/covert_collusive_hotpot/core/__init__.py
"""Shared runtime primitives for covert_collusive_hotpot."""
```

```python
# src/covert_collusive_hotpot/agents/__init__.py
"""Agent implementations for covert_collusive_hotpot."""
```

```python
# src/covert_collusive_hotpot/experiments/__init__.py
"""Experiment orchestration modules for covert_collusive_hotpot."""
```

- [ ] **Step 4: Run test to verify the package is still incomplete but discoverable**

Run: `python -m pip install -e .`
Expected: output includes `Successfully installed covert-collusive-hotpot-0.1.0`

Run: `PYTHONPATH=src pytest tests/test_package_entrypoints.py -v`
Expected: FAIL on missing `covert_collusive_hotpot.run_experiments` and `covert_collusive_hotpot.generate_paper_assets`.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/covert_collusive_hotpot/__init__.py src/covert_collusive_hotpot/core/__init__.py src/covert_collusive_hotpot/agents/__init__.py src/covert_collusive_hotpot/experiments/__init__.py tests/test_package_entrypoints.py
git commit -m "build: add package scaffold and smoke tests"
```

### Task 2: Move core modules into `src/covert_collusive_hotpot/core`

**Files:**
- Create: `src/covert_collusive_hotpot/core/config.py`
- Create: `src/covert_collusive_hotpot/core/models.py`
- Create: `src/covert_collusive_hotpot/core/logging_store.py`
- Create: `src/covert_collusive_hotpot/core/permission_manager.py`
- Create: `src/covert_collusive_hotpot/core/rate_limiter.py`
- Modify: `tests/test_package_entrypoints.py`
- Delete: `config.py`
- Delete: `models.py`
- Delete: `logger.py`
- Delete: `permission_manager.py`
- Delete: `rate_limiter.py`

- [ ] **Step 1: Extend the failing test to import core modules from the new package**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_package_entrypoints.py -k "core_modules_import or packaged_entry_modules_import" -v`
Expected: FAIL because the moved modules do not exist yet.

- [ ] **Step 3: Move the core files and rewrite imports**

```bash
mkdir -p src/covert_collusive_hotpot/core
git mv config.py src/covert_collusive_hotpot/core/config.py
git mv models.py src/covert_collusive_hotpot/core/models.py
git mv logger.py src/covert_collusive_hotpot/core/logging_store.py
git mv permission_manager.py src/covert_collusive_hotpot/core/permission_manager.py
git mv rate_limiter.py src/covert_collusive_hotpot/core/rate_limiter.py
```

```python
# src/covert_collusive_hotpot/core/logging_store.py
from covert_collusive_hotpot.core.models import Action, Message, PermissionChange, Recommendation
```

```python
# src/covert_collusive_hotpot/core/permission_manager.py
from covert_collusive_hotpot.core import config
from covert_collusive_hotpot.core.models import PermissionLevel, Recommendation, RecommendationAction
```

- [ ] **Step 4: Run test to verify the core package imports pass**

Run: `PYTHONPATH=src pytest tests/test_package_entrypoints.py -k core_modules_import -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/covert_collusive_hotpot/core tests/test_package_entrypoints.py
git commit -m "refactor: move core modules into package"
```

### Task 3: Move agent modules into `src/covert_collusive_hotpot/agents`

**Files:**
- Create: `src/covert_collusive_hotpot/agents/worker.py`
- Create: `src/covert_collusive_hotpot/agents/detector.py`
- Modify: `tests/test_package_entrypoints.py`
- Delete: `agent.py`
- Delete: `detector_agent.py`

- [ ] **Step 1: Add the failing agent import test**

```python
def test_agent_modules_import() -> None:
    worker_module = import_module("covert_collusive_hotpot.agents.worker")
    detector_module = import_module("covert_collusive_hotpot.agents.detector")
    assert hasattr(worker_module, "WorkerAgent")
    assert hasattr(detector_module, "DetectorAgent")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_package_entrypoints.py -k agent_modules_import -v`
Expected: FAIL with `ModuleNotFoundError` for `covert_collusive_hotpot.agents.worker`.

- [ ] **Step 3: Move the files and update package-qualified imports**

```bash
mkdir -p src/covert_collusive_hotpot/agents
git mv agent.py src/covert_collusive_hotpot/agents/worker.py
git mv detector_agent.py src/covert_collusive_hotpot/agents/detector.py
```

```python
# src/covert_collusive_hotpot/agents/worker.py
from dotenv import load_dotenv

from covert_collusive_hotpot.core import config
from covert_collusive_hotpot.core.models import Action, Agent as AgentData, Message, Role
from covert_collusive_hotpot.core.rate_limiter import rate_limited_call

load_dotenv()
```

```python
# src/covert_collusive_hotpot/agents/detector.py
from covert_collusive_hotpot.core import config
from covert_collusive_hotpot.core.models import Message
from covert_collusive_hotpot.core.rate_limiter import rate_limited_call
```

- [ ] **Step 4: Run test to verify agent imports pass**

Run: `PYTHONPATH=src pytest tests/test_package_entrypoints.py -k agent_modules_import -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/covert_collusive_hotpot/agents tests/test_package_entrypoints.py
git commit -m "refactor: move agent modules into package"
```

### Task 4: Move experiment orchestration and add the packaged runner entry point

**Files:**
- Create: `src/covert_collusive_hotpot/experiments/evaluation.py`
- Create: `src/covert_collusive_hotpot/experiments/hotpot_loader.py`
- Create: `src/covert_collusive_hotpot/experiments/prompt_injection.py`
- Create: `src/covert_collusive_hotpot/experiments/role_assignment.py`
- Create: `src/covert_collusive_hotpot/experiments/simulation.py`
- Create: `src/covert_collusive_hotpot/experiments/runner.py`
- Create: `src/covert_collusive_hotpot/run_experiments.py`
- Modify: `tests/test_package_entrypoints.py`
- Delete: `evaluation.py`
- Delete: `hotpot_loader.py`
- Delete: `prompt_injection.py`
- Delete: `role_assigner.py`
- Delete: `simulation.py`
- Delete: `parallel_experiment_runner.py`

- [ ] **Step 1: Add the failing experiment runner tests**

```python
def test_experiment_modules_import() -> None:
    evaluation_module = import_module("covert_collusive_hotpot.experiments.evaluation")
    simulation_module = import_module("covert_collusive_hotpot.experiments.simulation")
    runner_module = import_module("covert_collusive_hotpot.run_experiments")
    assert hasattr(evaluation_module, "Evaluator")
    assert hasattr(simulation_module, "Simulation")
    assert callable(runner_module.main)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_package_entrypoints.py -k experiment_modules_import -v`
Expected: FAIL with `ModuleNotFoundError` for the experiment modules.

- [ ] **Step 3: Move the files and rewrite imports**

```bash
mkdir -p src/covert_collusive_hotpot/experiments
git mv evaluation.py src/covert_collusive_hotpot/experiments/evaluation.py
git mv hotpot_loader.py src/covert_collusive_hotpot/experiments/hotpot_loader.py
git mv prompt_injection.py src/covert_collusive_hotpot/experiments/prompt_injection.py
git mv role_assigner.py src/covert_collusive_hotpot/experiments/role_assignment.py
git mv simulation.py src/covert_collusive_hotpot/experiments/simulation.py
git mv parallel_experiment_runner.py src/covert_collusive_hotpot/experiments/runner.py
```

```python
# src/covert_collusive_hotpot/experiments/evaluation.py
from covert_collusive_hotpot.core.models import PermissionLevel, Recommendation
from covert_collusive_hotpot.core.permission_manager import PermissionManager
```

```python
# src/covert_collusive_hotpot/experiments/simulation.py
from covert_collusive_hotpot.agents.detector import DetectorAgent
from covert_collusive_hotpot.agents.worker import WorkerAgent
from covert_collusive_hotpot.core.logging_store import Logger
from covert_collusive_hotpot.core.models import Action, Message, PermissionLevel, Recommendation, Role
from covert_collusive_hotpot.core.permission_manager import PermissionManager
from covert_collusive_hotpot.core.rate_limiter import rate_limited_call
```

```python
# src/covert_collusive_hotpot/experiments/runner.py
from covert_collusive_hotpot.agents.detector import DetectorAgent
from covert_collusive_hotpot.agents.worker import WorkerAgent
from covert_collusive_hotpot.core import config as cfg
from covert_collusive_hotpot.core.models import AttackType, KnowledgeLevel, Role
from covert_collusive_hotpot.experiments.evaluation import Evaluator
from covert_collusive_hotpot.experiments.hotpot_loader import load_hotpotqa_tasks
from covert_collusive_hotpot.experiments.prompt_injection import inject_hidden_prompts
from covert_collusive_hotpot.experiments.role_assignment import (
    assign_roles,
    malicious_count_from_label,
    mark_malicious,
)
from covert_collusive_hotpot.experiments.simulation import Simulation
```

```python
# src/covert_collusive_hotpot/run_experiments.py
from covert_collusive_hotpot.experiments.runner import main


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify imports and `--help` work**

Run: `PYTHONPATH=src pytest tests/test_package_entrypoints.py -k "experiment_modules_import or runner_wrapper_help_executes" -v`
Expected: import test PASS, wrapper test still FAIL until the wrapper is restored in Task 5.

Run: `PYTHONPATH=src python -m covert_collusive_hotpot.run_experiments --help`
Expected: output includes `Run collusive covert HotpotQA experiments`

- [ ] **Step 5: Commit**

```bash
git add src/covert_collusive_hotpot/experiments src/covert_collusive_hotpot/run_experiments.py tests/test_package_entrypoints.py
git commit -m "refactor: package experiment runner modules"
```

### Task 5: Move reporting code and restore root CLI wrappers

**Files:**
- Create: `src/covert_collusive_hotpot/generate_paper_assets.py`
- Create: `parallel_experiment_runner.py`
- Create: `generate_paper_tables_and_figures.py`
- Modify: `tests/test_package_entrypoints.py`
- Delete: `generate_paper_tables_and_figures.py`

- [ ] **Step 1: Add the failing reporting import expectation**

```python
def test_reporting_entry_module_import() -> None:
    report_module = import_module("covert_collusive_hotpot.generate_paper_assets")
    assert callable(report_module.main)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_package_entrypoints.py -k reporting_entry_module_import -v`
Expected: FAIL with `ModuleNotFoundError` for `covert_collusive_hotpot.generate_paper_assets`.

- [ ] **Step 3: Move the reporting module and add wrapper scripts**

```bash
git mv generate_paper_tables_and_figures.py src/covert_collusive_hotpot/generate_paper_assets.py
```

```python
# parallel_experiment_runner.py
from covert_collusive_hotpot.run_experiments import main


if __name__ == "__main__":
    main()
```

```python
# generate_paper_tables_and_figures.py
from covert_collusive_hotpot.generate_paper_assets import main


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify the new entry points and wrappers pass**

Run: `PYTHONPATH=src pytest tests/test_package_entrypoints.py -v`
Expected: PASS

Run: `PYTHONPATH=src python -m covert_collusive_hotpot.run_experiments --help`
Expected: output includes `Run collusive covert HotpotQA experiments`

Run: `PYTHONPATH=src python -m covert_collusive_hotpot.generate_paper_assets`
Expected: if `INPUT_CSV` is unset, the command raises `FileNotFoundError` for the default CSV path; under the test harness with a temp CSV, it exits successfully.

- [ ] **Step 5: Commit**

```bash
git add src/covert_collusive_hotpot/generate_paper_assets.py parallel_experiment_runner.py generate_paper_tables_and_figures.py tests/test_package_entrypoints.py
git commit -m "refactor: add packaged entry points and cli wrappers"
```

### Task 6: Update documentation and verify the final command surface

**Files:**
- Modify: `README.md`
- Modify: `tests/test_package_entrypoints.py`

- [ ] **Step 1: Write the failing documentation expectation test**

```python
def test_readme_mentions_new_entry_points() -> None:
    readme_text = Path(__file__).resolve().parents[1].joinpath("README.md").read_text()
    assert "python -m covert_collusive_hotpot.run_experiments" in readme_text
    assert "python -m covert_collusive_hotpot.generate_paper_assets" in readme_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_package_entrypoints.py -k readme_mentions_new_entry_points -v`
Expected: FAIL because the README still points at root scripts.

- [ ] **Step 3: Update README setup and execution commands**

````markdown
## Setup

Install dependencies and the local package:

```bash
pip install -r requirements.txt
pip install -e .
```

## Smoke Test

```bash
python -m covert_collusive_hotpot.run_experiments --smoke --smoke-tasks 2 --max-concurrent 1 --run-label smoke
```

## Full Run

```bash
tmux new -s collusive_hotpot
python -m covert_collusive_hotpot.run_experiments --max-concurrent 4 --run-label full_collusive_hotpot
```

## Compatibility

The old commands still work during the transition:

```bash
python parallel_experiment_runner.py --help
python generate_paper_tables_and_figures.py
```
````

- [ ] **Step 4: Run final verification**

Run: `python -m pip install -e .`
Expected: output includes `Successfully installed covert-collusive-hotpot-0.1.0` or `Successfully installed covert-collusive-hotpot`

Run: `PYTHONPATH=src pytest tests/test_package_entrypoints.py -v`
Expected: PASS

Run: `PYTHONPATH=src python -m covert_collusive_hotpot.run_experiments --help`
Expected: output includes `Run collusive covert HotpotQA experiments`

Run: `PYTHONPATH=src python parallel_experiment_runner.py --help`
Expected: output includes `Run collusive covert HotpotQA experiments`

- [ ] **Step 5: Commit**

```bash
git add README.md tests/test_package_entrypoints.py
git commit -m "docs: update package usage instructions"
```
