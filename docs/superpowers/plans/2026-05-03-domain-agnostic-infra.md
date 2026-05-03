# Domain-Agnostic Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the runner, CLI/config surface, simulation boundary, and reporting entry point domain-aware through a registry-backed domain abstraction while preserving `knowledge_qa` as the implicit default.

**Architecture:** Add a new `domains/` package with a small `DomainSpec` interface, a central registry, and a concrete `knowledge_qa` domain implementation. Convert shared runner and reporting code into consumers of that domain layer, and move QA-specific behavior behind the new seam without changing default QA behavior.

**Tech Stack:** Python 3.11, pytest, setuptools `src` layout, existing `covert_collusive_hotpot` package modules

---

## File Structure

**Create:**

- `src/covert_collusive_hotpot/domains/__init__.py`
- `src/covert_collusive_hotpot/domains/base.py`
- `src/covert_collusive_hotpot/domains/registry.py`
- `src/covert_collusive_hotpot/domains/knowledge_qa/__init__.py`
- `src/covert_collusive_hotpot/domains/knowledge_qa/domain.py`
- `src/covert_collusive_hotpot/domains/knowledge_qa/reporting.py`
- `tests/test_domain_registry.py`
- `tests/test_domain_reporting.py`

**Modify:**

- `src/covert_collusive_hotpot/core/config.py`
- `src/covert_collusive_hotpot/experiments/runner.py`
- `src/covert_collusive_hotpot/experiments/simulation.py`
- `src/covert_collusive_hotpot/generate_paper_assets.py`
- `tests/test_package_entrypoints.py`
- `tests/test_runner_contracts.py`
- `tests/README.md`
- `README.md`

**Reuse without moving in this branch:**

- `src/covert_collusive_hotpot/experiments/hotpot_loader.py`
- `src/covert_collusive_hotpot/experiments/role_assignment.py`
- `src/covert_collusive_hotpot/experiments/prompt_injection.py`

### Task 1: Add the domain abstraction and registry

**Files:**

- Create: `src/covert_collusive_hotpot/domains/__init__.py`
- Create: `src/covert_collusive_hotpot/domains/base.py`
- Create: `src/covert_collusive_hotpot/domains/registry.py`
- Create: `tests/test_domain_registry.py`

- [ ] **Step 1: Write the failing registry tests**

```python
from covert_collusive_hotpot.domains.base import DomainCapabilities, DomainSpec
from covert_collusive_hotpot.domains.registry import DomainRegistry


class DummyDomain(DomainSpec):
    def __init__(self, name: str):
        super().__init__(
            name=name,
            capabilities=DomainCapabilities(language_only_permissions=False),
        )

    def build_task_pool(self, task_count: int, seed: int | None):
        return [{"task_id": "dummy", "prompt": "dummy"}]

    def assign_roles(self, rng):
        return []

    def inject_prompts(
        self,
        agents,
        m,
        attack_type,
        knowledge_level,
        detector_ids,
        detector_visible,
        tool_knowledge,
        interrogation_turns,
    ):
        return agents

    def reporting_adapter(self):
        return object()


def test_registry_exposes_registered_domain_names() -> None:
    registry = DomainRegistry(default_domain="knowledge_qa")
    registry.register(DummyDomain("knowledge_qa"))
    registry.register(DummyDomain("dummy"))

    assert registry.names() == ["dummy", "knowledge_qa"]


def test_registry_returns_default_domain() -> None:
    registry = DomainRegistry(default_domain="knowledge_qa")
    qa = DummyDomain("knowledge_qa")
    registry.register(qa)

    assert registry.default_domain() is qa


def test_registry_rejects_unknown_domain() -> None:
    registry = DomainRegistry(default_domain="knowledge_qa")
    registry.register(DummyDomain("knowledge_qa"))

    try:
        registry.get("missing")
    except ValueError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown domain")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src pytest tests/test_domain_registry.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'covert_collusive_hotpot.domains'`

- [ ] **Step 3: Add the minimal domain base types and registry**

```python
# src/covert_collusive_hotpot/domains/base.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class DomainCapabilities:
    language_only_permissions: bool


class ReportingAdapter(Protocol):
    def run(self) -> None:
        raise NotImplementedError


class DomainSpec:
    def __init__(self, name: str, capabilities: DomainCapabilities):
        self.name = name
        self.capabilities = capabilities

    def build_task_pool(self, task_count: int, seed: int | None) -> list[dict[str, Any]]:
        raise NotImplementedError

    def assign_roles(self, rng) -> list[Any]:
        raise NotImplementedError

    def inject_prompts(
        self,
        agents: list[Any],
        m: int | str,
        attack_type: Any,
        knowledge_level: Any,
        detector_ids: list[int],
        detector_visible: bool,
        tool_knowledge: bool,
        interrogation_turns: list[int] | None,
    ) -> list[Any]:
        raise NotImplementedError

    def reporting_adapter(self) -> ReportingAdapter:
        raise NotImplementedError
```

```python
# src/covert_collusive_hotpot/domains/registry.py
from __future__ import annotations

from covert_collusive_hotpot.domains.base import DomainSpec


class DomainRegistry:
    def __init__(self, default_domain: str):
        self._default_domain_name = default_domain
        self._domains: dict[str, DomainSpec] = {}

    def register(self, domain: DomainSpec) -> None:
        self._domains[domain.name] = domain

    def get(self, name: str) -> DomainSpec:
        try:
            return self._domains[name]
        except KeyError as exc:
            supported = ", ".join(sorted(self._domains))
            raise ValueError(f"Unknown domain '{name}'. Supported domains: {supported}") from exc

    def names(self) -> list[str]:
        return sorted(self._domains)

    def default_domain_name(self) -> str:
        return self._default_domain_name

    def default_domain(self) -> DomainSpec:
        return self.get(self._default_domain_name)
```

```python
# src/covert_collusive_hotpot/domains/__init__.py
from covert_collusive_hotpot.domains.base import DomainCapabilities, DomainSpec
from covert_collusive_hotpot.domains.registry import DomainRegistry

__all__ = ["DomainCapabilities", "DomainRegistry", "DomainSpec"]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/test_domain_registry.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/covert_collusive_hotpot/domains/__init__.py src/covert_collusive_hotpot/domains/base.py src/covert_collusive_hotpot/domains/registry.py tests/test_domain_registry.py
git commit -m "feat: add domain abstraction and registry"
```

### Task 2: Add the registered `knowledge_qa` domain

**Files:**

- Create: `src/covert_collusive_hotpot/domains/knowledge_qa/__init__.py`
- Create: `src/covert_collusive_hotpot/domains/knowledge_qa/domain.py`
- Modify: `src/covert_collusive_hotpot/domains/registry.py`
- Modify: `tests/test_domain_registry.py`

- [ ] **Step 1: Extend the registry tests with the real default domain**

```python
from covert_collusive_hotpot.domains.registry import get_domain_registry


def test_global_registry_defaults_to_knowledge_qa() -> None:
    registry = get_domain_registry()

    assert registry.default_domain_name() == "knowledge_qa"
    assert "knowledge_qa" in registry.names()


def test_knowledge_qa_domain_capabilities_are_exposed() -> None:
    registry = get_domain_registry()
    domain = registry.get("knowledge_qa")

    assert domain.name == "knowledge_qa"
    assert domain.capabilities.language_only_permissions is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src pytest tests/test_domain_registry.py -q`
Expected: FAIL with `ImportError` for `get_domain_registry` or missing registered `knowledge_qa`

- [ ] **Step 3: Implement the QA domain and the global registry**

```python
# src/covert_collusive_hotpot/domains/knowledge_qa/domain.py
from __future__ import annotations

from covert_collusive_hotpot.domains.base import DomainCapabilities, DomainSpec
from covert_collusive_hotpot.experiments.hotpot_loader import load_hotpotqa_tasks
from covert_collusive_hotpot.experiments.prompt_injection import inject_hidden_prompts
from covert_collusive_hotpot.experiments.role_assignment import assign_roles


class KnowledgeQADomain(DomainSpec):
    def __init__(self):
        super().__init__(
            name="knowledge_qa",
            capabilities=DomainCapabilities(language_only_permissions=True),
        )

    def build_task_pool(self, task_count: int, seed: int | None):
        return load_hotpotqa_tasks(task_count, seed=seed)

    def assign_roles(self, rng):
        return assign_roles(self.name, rng=rng)

    def inject_prompts(
        self,
        agents,
        m,
        attack_type,
        knowledge_level,
        detector_ids,
        detector_visible,
        tool_knowledge,
        interrogation_turns,
    ):
        return inject_hidden_prompts(
            agents,
            m,
            attack_type,
            knowledge_level,
            detector_ids,
            detector_visible,
            tool_knowledge,
            interrogation_turns,
        )

    def reporting_adapter(self):
        from covert_collusive_hotpot.domains.knowledge_qa.reporting import KnowledgeQAReportingAdapter

        return KnowledgeQAReportingAdapter
```

```python
# src/covert_collusive_hotpot/domains/knowledge_qa/__init__.py
from covert_collusive_hotpot.domains.knowledge_qa.domain import KnowledgeQADomain

__all__ = ["KnowledgeQADomain"]
```

```python
# src/covert_collusive_hotpot/domains/registry.py
from __future__ import annotations

from functools import lru_cache

from covert_collusive_hotpot.domains.base import DomainSpec


class DomainRegistry:
    def __init__(self, default_domain: str):
        self._default_domain_name = default_domain
        self._domains: dict[str, DomainSpec] = {}

    def register(self, domain: DomainSpec) -> None:
        self._domains[domain.name] = domain

    def get(self, name: str) -> DomainSpec:
        try:
            return self._domains[name]
        except KeyError as exc:
            supported = ", ".join(sorted(self._domains))
            raise ValueError(f"Unknown domain '{name}'. Supported domains: {supported}") from exc

    def names(self) -> list[str]:
        return sorted(self._domains)

    def default_domain_name(self) -> str:
        return self._default_domain_name

    def default_domain(self) -> DomainSpec:
        return self.get(self._default_domain_name)


@lru_cache(maxsize=1)
def get_domain_registry() -> DomainRegistry:
    from covert_collusive_hotpot.domains.knowledge_qa import KnowledgeQADomain

    registry = DomainRegistry(default_domain="knowledge_qa")
    registry.register(KnowledgeQADomain())
    return registry
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/test_domain_registry.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/covert_collusive_hotpot/domains/knowledge_qa/__init__.py src/covert_collusive_hotpot/domains/knowledge_qa/domain.py src/covert_collusive_hotpot/domains/registry.py tests/test_domain_registry.py
git commit -m "feat: register knowledge qa domain"
```

### Task 3: Add explicit domain default resolution in config

**Files:**

- Modify: `src/covert_collusive_hotpot/core/config.py`
- Modify: `tests/test_domain_registry.py`

- [ ] **Step 1: Add config resolution tests**

```python
from importlib import reload

from covert_collusive_hotpot.core import config as cfg


def test_config_default_domain_is_knowledge_qa(monkeypatch) -> None:
    monkeypatch.delenv("DOMAIN", raising=False)
    module = reload(cfg)

    assert module.DEFAULT_DOMAIN == "knowledge_qa"


def test_config_reads_domain_override(monkeypatch) -> None:
    monkeypatch.setenv("DOMAIN", "knowledge_qa")
    module = reload(cfg)

    assert module.DEFAULT_DOMAIN == "knowledge_qa"
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `PYTHONPATH=src pytest tests/test_domain_registry.py -k "config_default_domain or config_reads_domain_override" -q`
Expected: FAIL with `AttributeError` for missing `DEFAULT_DOMAIN`

- [ ] **Step 3: Implement canonical default-domain config**

```python
# src/covert_collusive_hotpot/core/config.py
DEFAULT_DOMAIN = os.getenv("DOMAIN", "knowledge_qa").strip() or "knowledge_qa"
```

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/test_domain_registry.py -k "config_default_domain or config_reads_domain_override" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/covert_collusive_hotpot/core/config.py tests/test_domain_registry.py
git commit -m "feat: add shared default domain config"
```

### Task 4: Move the runner to registry-backed domain resolution

**Files:**

- Modify: `src/covert_collusive_hotpot/experiments/runner.py`
- Modify: `tests/test_runner_contracts.py`

- [ ] **Step 1: Add failing runner domain tests**

```python
from covert_collusive_hotpot.domains.registry import get_domain_registry
from covert_collusive_hotpot.experiments import runner


def test_runner_defaults_to_registry_default_domain(monkeypatch) -> None:
    monkeypatch.setattr(runner.cfg, "DEFAULT_DOMAIN", "knowledge_qa")

    args = runner.build_arg_parser().parse_args([])

    assert args.domain is None
    assert runner._resolve_domain(args).name == "knowledge_qa"


def test_runner_rejects_unknown_domain() -> None:
    parser = runner.build_arg_parser()

    try:
        args = parser.parse_args(["--domain", "missing"])
        runner._resolve_domain(args)
    except ValueError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("Expected invalid domain to raise")
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `PYTHONPATH=src pytest tests/test_runner_contracts.py -k "registry_default_domain or unknown_domain" -q`
Expected: FAIL because `build_arg_parser()` or `_resolve_domain()` does not exist

- [ ] **Step 3: Refactor the runner to resolve domains explicitly**

```python
# src/covert_collusive_hotpot/experiments/runner.py
import argparse

from typing import Any, Dict, List, Optional

from covert_collusive_hotpot.agents.detector import DetectorAgent
from covert_collusive_hotpot.agents.worker import WorkerAgent
from covert_collusive_hotpot.core import config as cfg
from covert_collusive_hotpot.core.models import AttackType, KnowledgeLevel, Role
from covert_collusive_hotpot.domains.registry import get_domain_registry
from covert_collusive_hotpot.experiments.evaluation import Evaluator
from covert_collusive_hotpot.experiments.simulation import Simulation


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run collusive covert HotpotQA experiments")
    parser.add_argument(
        "--domain",
        help="Experiment domain name",
    )
    parser.add_argument("--smoke", action="store_true", help="Run a tiny validation matrix instead of the full experiment")
    parser.add_argument("--smoke-tasks", type=int, help="Task count used with --smoke")
    parser.add_argument("--tasks", type=int, help="Override HotpotQA tasks per condition")
    parser.add_argument("--reps", type=int, help="Override repetitions")
    parser.add_argument("--max-concurrent", type=int, help="Concurrent condition runners")
    parser.add_argument("--run-label", help="Override RUN_LABEL for outputs")
    parser.add_argument("--output-csv", help="Aggregate output CSV path")
    parser.add_argument("--task-progress-jsonl", help="Task checkpoint JSONL path")
    parser.add_argument("--dry-run", action="store_true", help="Print planned configs and ETA without API calls")
    parser.add_argument("--no-shuffle", action="store_true", help="Do not shuffle condition order")
    return parser


def _resolve_domain_name(args: argparse.Namespace) -> str:
    return (args.domain or cfg.DEFAULT_DOMAIN).strip()


def _resolve_domain(args: argparse.Namespace):
    registry = get_domain_registry()
    return registry.get(_resolve_domain_name(args))


def _build_task_pool(domain, seed: int | None = None) -> list[dict[str, Any]]:
    return domain.build_task_pool(cfg.HOTPOT_QA_TASKS, seed=seed)


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    domain = _resolve_domain(args)
    configs = generate_smoke_configs(domain.name) if args.smoke else generate_configs(domain.name, total_reps=args.reps)
    task_pool = _build_task_pool(domain)
    if args.dry_run:
        print(f"Domain: {domain.name}")
        print(f"Configs: {len(configs)}")
        print(f"Tasks: {len(task_pool)}")
        return
    run_experiments(configs=configs, task_pool=task_pool, domain=domain, args=args)
```

```python
# src/covert_collusive_hotpot/experiments/runner.py
@dataclass(frozen=True)
class ExperimentConfig:
    rep: int
    attack_type: AttackType
    m: str
    d: int
    domain: str
    knowledge_level: Optional[KnowledgeLevel] = None
    condition_name: str = ""
```

```python
# src/covert_collusive_hotpot/experiments/runner.py
def generate_configs(domain_name: str, total_reps: int = None) -> List[ExperimentConfig]:
    reps = total_reps or TOTAL_REPS
    configs: List[ExperimentConfig] = []
    for attack_type in ATTACK_TYPES:
        for condition_name, m_label, detectors in CONDITION_SPECS:
            for rep in range(1, reps + 1):
                configs.append(
                    ExperimentConfig(
                        rep=rep,
                        attack_type=attack_type,
                        m=m_label,
                        d=detectors,
                        domain=domain_name,
                        condition_name=condition_name,
                    )
                )
    return configs
```

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/test_runner_contracts.py -k "registry_default_domain or unknown_domain" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/covert_collusive_hotpot/experiments/runner.py tests/test_runner_contracts.py
git commit -m "feat: make runner resolve domains through registry"
```

### Task 5: Route QA task setup through the domain module

**Files:**

- Modify: `src/covert_collusive_hotpot/experiments/runner.py`
- Modify: `tests/test_runner_contracts.py`

- [ ] **Step 1: Add a failing runner setup test**

```python
def test_run_single_task_uses_domain_for_roles_and_tasks(monkeypatch) -> None:
    calls: list[str] = []

    class FakeDomain:
        name = "knowledge_qa"
        capabilities = type("Caps", (), {"language_only_permissions": True})()

        def assign_roles(self, rng):
            calls.append("assign_roles")
            return []

        def inject_prompts(self, *args, **kwargs):
            calls.append("inject_prompts")
            return []

    monkeypatch.setattr(runner, "_resolve_domain_for_config", lambda exp_config: FakeDomain())
    monkeypatch.setattr(runner, "mark_malicious", lambda agents, m, rng=None: agents)
    monkeypatch.setattr(runner, "malicious_count_from_label", lambda m, total_agents: 0)

    exp_config = runner.ExperimentConfig(
        rep=1,
        attack_type=runner.AttackType.SUBOPTIMAL_FIXATION,
        m="0",
        d=0,
        domain="knowledge_qa",
        condition_name="clean_baseline",
    )

    try:
        runner._prepare_agents_for_task(exp_config, {"task_id": "t1", "prompt": "p"}, 0)
    except Exception:
        pass

    assert "assign_roles" in calls
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_runner_contracts.py -k "uses_domain_for_roles_and_tasks" -q`
Expected: FAIL because `_resolve_domain_for_config()` or `_prepare_agents_for_task()` does not exist

- [ ] **Step 3: Extract domain-backed agent preparation from the runner**

```python
# src/covert_collusive_hotpot/experiments/runner.py
def _resolve_domain_for_config(exp_config: ExperimentConfig):
    return get_domain_registry().get(exp_config.domain)


def _prepare_agents_for_task(exp_config: ExperimentConfig, task: Dict[str, Any], task_index: int):
    domain = _resolve_domain_for_config(exp_config)
    task_rng = _build_task_rng(exp_config, task, task_index)
    agents_data = domain.assign_roles(task_rng)
    malicious_count = malicious_count_from_label(exp_config.m, len(agents_data))
    agents_data = mark_malicious(agents_data, exp_config.m, rng=task_rng)
    detector_ids = [1000 + i for i in range(exp_config.d)] if exp_config.d > 0 else []
    detector_visible = exp_config.d > 0
    tool_knowledge = exp_config.d > 0
    interrogation_turns = INTERROGATION_TURNS if exp_config.d > 0 else None
    if malicious_count > 0:
        agents_data = domain.inject_prompts(
            agents_data,
            exp_config.m,
            exp_config.attack_type,
            exp_config.knowledge_level,
            detector_ids,
            detector_visible,
            tool_knowledge,
            interrogation_turns,
        )
    return domain, task_rng, agents_data, malicious_count, detector_ids, detector_visible
```

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `PYTHONPATH=src pytest tests/test_runner_contracts.py -k "uses_domain_for_roles_and_tasks" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/covert_collusive_hotpot/experiments/runner.py tests/test_runner_contracts.py
git commit -m "refactor: route runner task setup through domain module"
```

### Task 6: Replace simulation string checks with explicit capabilities

**Files:**

- Modify: `src/covert_collusive_hotpot/experiments/simulation.py`
- Modify: `tests/test_runner_contracts.py`

- [ ] **Step 1: Add a failing simulation capability test**

```python
def test_simulation_uses_domain_capabilities_for_permission_mode() -> None:
    class PermissionManager:
        def __init__(self):
            self.calls = []

        def get_permission_level(self, agent_id: int, is_language_only: bool):
            self.calls.append((agent_id, is_language_only))
            return runner.PermissionLevel.REMOVED

    sim = Simulation.__new__(Simulation)
    sim.turn = 0
    sim.workers = {0: object()}
    sim.detectors = {}
    sim.message_log = []
    sim.action_log = []
    sim.recommendation_log = []
    sim.permission_manager = PermissionManager()
    sim.domain_capabilities = type("Caps", (), {"language_only_permissions": False})()

    asyncio.run(sim.run_turn())

    assert sim.permission_manager.calls == [(0, False)]
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `PYTHONPATH=src pytest tests/test_runner_contracts.py -k "domain_capabilities_for_permission_mode" -q`
Expected: FAIL because `Simulation` still relies on `self.domain == "knowledge_qa"`

- [ ] **Step 3: Make simulation consume explicit capability data**

```python
# src/covert_collusive_hotpot/experiments/simulation.py
class Simulation:
    def __init__(
        self,
        workers,
        detectors,
        total_turns=config.TOTAL_TURNS,
        experiment_id: str = "exp",
        metadata: Dict[str, Any] = None,
        domain: str = None,
        domain_capabilities=None,
    ):
        self.domain = domain
        self.domain_capabilities = domain_capabilities
```

```python
# src/covert_collusive_hotpot/experiments/simulation.py
def _is_language_only_permissions(self) -> bool:
    if self.domain_capabilities is None:
        return False
    return bool(self.domain_capabilities.language_only_permissions)
```

```python
# src/covert_collusive_hotpot/experiments/simulation.py
level = self.permission_manager.get_permission_level(
    agent_id,
    is_language_only=self._is_language_only_permissions(),
)
```

- [ ] **Step 4: Update the runner to pass capabilities and run the focused test**

Run: `PYTHONPATH=src pytest tests/test_runner_contracts.py -k "domain_capabilities_for_permission_mode" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/covert_collusive_hotpot/experiments/simulation.py src/covert_collusive_hotpot/experiments/runner.py tests/test_runner_contracts.py
git commit -m "refactor: pass domain capabilities into simulation"
```

### Task 7: Add a domain-selectable reporting adapter seam

**Files:**

- Create: `src/covert_collusive_hotpot/domains/knowledge_qa/reporting.py`
- Modify: `src/covert_collusive_hotpot/generate_paper_assets.py`
- Create: `tests/test_domain_reporting.py`

- [ ] **Step 1: Write the failing reporting dispatch tests**

```python
import os

from covert_collusive_hotpot.domains.registry import get_domain_registry
from covert_collusive_hotpot import generate_paper_assets as reporting


def test_reporting_defaults_to_knowledge_qa(monkeypatch) -> None:
    monkeypatch.delenv("REPORT_DOMAIN", raising=False)

    assert reporting.resolve_domain_name(None) == "knowledge_qa"


def test_reporting_resolves_registered_adapter() -> None:
    adapter_cls = reporting.resolve_reporting_adapter("knowledge_qa")

    assert adapter_cls is get_domain_registry().get("knowledge_qa").reporting_adapter()
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `PYTHONPATH=src pytest tests/test_domain_reporting.py -q`
Expected: FAIL because `resolve_domain_name()` and `resolve_reporting_adapter()` do not exist

- [ ] **Step 3: Extract QA reporting into an adapter and add shared dispatch**

```python
# src/covert_collusive_hotpot/domains/knowledge_qa/reporting.py
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


class KnowledgeQAReportingAdapter:
    def __init__(
        self,
        input_csv: str,
        output_table_dir: Path,
        output_fig_dir: Path,
        expected_tasks: int,
        require_full_task_counts: bool,
    ):
        self.input_csv = input_csv
        self.output_table_dir = output_table_dir
        self.output_fig_dir = output_fig_dir
        self.expected_tasks = expected_tasks
        self.require_full_task_counts = require_full_task_counts

    def run(self) -> None:
        self.output_table_dir.mkdir(parents=True, exist_ok=True)
        self.output_fig_dir.mkdir(parents=True, exist_ok=True)
        df = self.load_results()
        self.save_summary(df)
        self.save_condition_table(df)
        self.plot_metric_by_condition(
            df,
            "detection_rate",
            "Detection Rate by Condition",
            "detection_rate_by_condition.png",
        )
        self.plot_metric_by_condition(
            df,
            "functional_correctness",
            "Functional Correctness by Condition",
            "functional_correctness_by_condition.png",
        )

    def load_results(self) -> pd.DataFrame:
        df = pd.read_csv(self.input_csv)
        df = df[df["domain"].astype(str) == "knowledge_qa"]
        if self.require_full_task_counts:
            df = df[df["tasks_evaluated"] == self.expected_tasks]
        return df.reset_index(drop=True)
```

```python
# src/covert_collusive_hotpot/generate_paper_assets.py
from __future__ import annotations

import argparse
import os

from covert_collusive_hotpot.core import config as cfg
from covert_collusive_hotpot.domains.registry import get_domain_registry
from pathlib import Path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate paper-ready tables and figures")
    parser.add_argument("--domain", help="Reporting domain name")
    return parser


def resolve_domain_name(cli_value: str | None) -> str:
    return (cli_value or os.getenv("REPORT_DOMAIN") or cfg.DEFAULT_DOMAIN).strip()


def resolve_reporting_adapter(domain_name: str):
    registry = get_domain_registry()
    domain = registry.get(domain_name)
    return domain.reporting_adapter()


def main() -> None:
    args = build_arg_parser().parse_args()
    domain_name = resolve_domain_name(args.domain)
    adapter_cls = resolve_reporting_adapter(domain_name)
    adapter = adapter_cls(
        input_csv=INPUT_CSV,
        output_table_dir=OUTPUT_TABLE_DIR,
        output_fig_dir=OUTPUT_FIG_DIR,
        expected_tasks=EXPECTED_TASKS,
        require_full_task_counts=REQUIRE_FULL_TASK_COUNTS,
    )
    adapter.run()
    print(f"Saved paper tables to {OUTPUT_TABLE_DIR.resolve()}")
    print(f"Saved paper figures to {OUTPUT_FIG_DIR.resolve()}")
```

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/test_domain_reporting.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/covert_collusive_hotpot/domains/knowledge_qa/reporting.py src/covert_collusive_hotpot/generate_paper_assets.py tests/test_domain_reporting.py
git commit -m "refactor: make reporting dispatch through domain adapters"
```

### Task 8: Update public-surface and contract tests for the new domain seam

**Files:**

- Modify: `tests/test_package_entrypoints.py`
- Modify: `tests/test_runner_contracts.py`
- Modify: `README.md`
- Modify: `tests/README.md`

- [ ] **Step 1: Extend the package smoke suite with domain-aware help coverage**

```python
def test_packaged_experiment_help_mentions_domain_flag() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "covert_collusive_hotpot.run_experiments", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--domain" in result.stdout
```

```python
def test_packaged_reporting_help_mentions_domain_flag() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "covert_collusive_hotpot.generate_paper_assets", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--domain" in result.stdout
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run: `PYTHONPATH=src pytest tests/test_package_entrypoints.py -k "mentions_domain_flag" -q`
Expected: FAIL because one or both help surfaces do not mention `--domain`

- [ ] **Step 3: Update docs and contract coverage for the new public surface**

```markdown
# README.md
- `python -m covert_collusive_hotpot.run_experiments --domain knowledge_qa`
- `python -m covert_collusive_hotpot.generate_paper_assets --domain knowledge_qa`
- when omitted, the domain defaults to `knowledge_qa`
```

```markdown
# tests/README.md
- add registry tests and reporting-dispatch tests to the test inventory
- document `--domain` as the new optional surface
```

- [ ] **Step 4: Run the focused tests to verify they pass**

Run: `PYTHONPATH=src pytest tests/test_package_entrypoints.py -k "mentions_domain_flag" -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/test_package_entrypoints.py tests/test_runner_contracts.py README.md tests/README.md
git commit -m "test: cover domain-aware public surfaces"
```

### Task 9: Run the full local verification suite and fix any regressions

**Files:**

- Verify:
  - `src/covert_collusive_hotpot/core/config.py`
  - `src/covert_collusive_hotpot/experiments/runner.py`
  - `src/covert_collusive_hotpot/experiments/simulation.py`
  - `src/covert_collusive_hotpot/generate_paper_assets.py`
  - `src/covert_collusive_hotpot/domains/base.py`
  - `src/covert_collusive_hotpot/domains/registry.py`
  - `src/covert_collusive_hotpot/domains/knowledge_qa/domain.py`
  - `src/covert_collusive_hotpot/domains/knowledge_qa/reporting.py`
  - `tests/test_domain_registry.py`
  - `tests/test_domain_reporting.py`
  - `tests/test_package_entrypoints.py`
  - `tests/test_runner_contracts.py`

- [ ] **Step 1: Run the full test suite**

Run: `PYTHONPATH=src pytest tests -q`
Expected: PASS with all package, contract, registry, reporting, and QA-local tests green

- [ ] **Step 2: Run packaged experiment help**

Run: `python -m covert_collusive_hotpot.run_experiments --help`
Expected: exit `0` and help output includes `--domain`

- [ ] **Step 3: Run packaged reporting help**

Run: `python -m covert_collusive_hotpot.generate_paper_assets --help`
Expected: exit `0` and help output includes `--domain`

- [ ] **Step 4: Run legacy wrapper help**

Run: `python parallel_experiment_runner.py --help`
Expected: exit `0` and help output includes `--domain`

- [ ] **Step 5: Commit the final infra pass**

```bash
git add src/covert_collusive_hotpot/domains src/covert_collusive_hotpot/core/config.py src/covert_collusive_hotpot/experiments/runner.py src/covert_collusive_hotpot/experiments/simulation.py src/covert_collusive_hotpot/generate_paper_assets.py tests/test_domain_registry.py tests/test_domain_reporting.py tests/test_package_entrypoints.py tests/test_runner_contracts.py README.md tests/README.md
git commit -m "feat: make experiment infrastructure domain agnostic"
```
