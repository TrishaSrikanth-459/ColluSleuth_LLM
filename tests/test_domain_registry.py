from importlib import reload
from typing import get_type_hints

from covert_collusive_hotpot.core import config as cfg
from covert_collusive_hotpot.domains.base import (
    DomainCapabilities,
    DomainSpec,
    PromptInjectionContext,
    ReportingAdapter,
)
from covert_collusive_hotpot.domains.knowledge_qa import KnowledgeQADomain
from covert_collusive_hotpot.domains.registry import DomainRegistry, get_domain_registry


class DummyReportingAdapter:
    def __init__(
        self,
        input_csv_path: str,
        output_table_dir: str,
        output_fig_dir: str,
        expected_task_count: int,
        require_full_task_counts: bool,
    ):
        self.input_csv_path = input_csv_path
        self.output_table_dir = output_table_dir
        self.output_fig_dir = output_fig_dir
        self.expected_task_count = expected_task_count
        self.require_full_task_counts = require_full_task_counts

    def run(self) -> None:
        return None


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

    def inject_prompts(self, agents, context: PromptInjectionContext):
        assert isinstance(context, PromptInjectionContext)
        return agents

    def reporting_adapter(
        self,
        input_csv_path: str,
        output_table_dir: str,
        output_fig_dir: str,
        expected_task_count: int,
        require_full_task_counts: bool,
    ):
        return DummyReportingAdapter(
            input_csv_path=input_csv_path,
            output_table_dir=output_table_dir,
            output_fig_dir=output_fig_dir,
            expected_task_count=expected_task_count,
            require_full_task_counts=require_full_task_counts,
        )


def test_domain_spec_is_abstract() -> None:
    try:
        DomainSpec(
            name="incomplete",
            capabilities=DomainCapabilities(language_only_permissions=False),
        )
    except TypeError:
        pass
    else:
        raise AssertionError("Expected DomainSpec instantiation to fail")


def test_domain_spec_reporting_adapter_contract_is_instance_typed() -> None:
    hints = get_type_hints(DomainSpec.reporting_adapter)

    assert hints["input_csv_path"] is str
    assert hints["output_table_dir"] is str
    assert hints["output_fig_dir"] is str
    assert hints["expected_task_count"] is int
    assert hints["require_full_task_counts"] is bool
    assert hints["return"] is ReportingAdapter


def test_dummy_domain_reporting_adapter_returns_configured_instance() -> None:
    domain = DummyDomain("knowledge_qa")
    adapter = domain.reporting_adapter(
        input_csv_path="results.csv",
        output_table_dir="tables",
        output_fig_dir="figures",
        expected_task_count=100,
        require_full_task_counts=True,
    )

    assert isinstance(adapter, ReportingAdapter)
    assert adapter.input_csv_path == "results.csv"
    assert adapter.output_table_dir == "tables"
    assert adapter.output_fig_dir == "figures"
    assert adapter.expected_task_count == 100
    assert adapter.require_full_task_counts is True


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


def test_registry_rejects_duplicate_domain_names() -> None:
    registry = DomainRegistry(default_domain="knowledge_qa")
    registry.register(DummyDomain("knowledge_qa"))

    try:
        registry.register(DummyDomain("knowledge_qa"))
    except ValueError as exc:
        assert "knowledge_qa" in str(exc)
    else:
        raise AssertionError("Expected ValueError for duplicate domain")


def test_registry_rejects_unknown_domain() -> None:
    registry = DomainRegistry(default_domain="knowledge_qa")
    registry.register(DummyDomain("knowledge_qa"))

    try:
        registry.get("missing")
    except ValueError as exc:
        assert "missing" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown domain")


def test_registry_rejects_missing_default_domain() -> None:
    registry = DomainRegistry(default_domain="knowledge_qa")
    registry.register(DummyDomain("dummy"))

    try:
        registry.default_domain()
    except ValueError as exc:
        assert "knowledge_qa" in str(exc)
        assert "default" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for missing default domain")


def test_global_registry_defaults_to_knowledge_qa() -> None:
    registry = get_domain_registry()

    assert registry.default_domain_name() == "knowledge_qa"
    assert "knowledge_qa" in registry.names()


def test_config_default_domain_is_knowledge_qa(monkeypatch) -> None:
    monkeypatch.delenv("DOMAIN", raising=False)
    module = reload(cfg)

    assert module.DEFAULT_DOMAIN == "knowledge_qa"


def test_config_reads_domain_override(monkeypatch) -> None:
    monkeypatch.setenv("DOMAIN", "code_synthesis")
    module = reload(cfg)

    assert module.DEFAULT_DOMAIN == "code_synthesis"


def test_config_uses_canonical_default_for_whitespace_domain(monkeypatch) -> None:
    monkeypatch.setenv("DOMAIN", "   ")
    module = reload(cfg)

    assert module.DEFAULT_DOMAIN == "knowledge_qa"


def test_knowledge_qa_domain_capabilities_are_exposed() -> None:
    registry = get_domain_registry()
    domain = registry.get("knowledge_qa")

    assert domain.name == "knowledge_qa"
    assert domain.capabilities.language_only_permissions is True


def test_knowledge_qa_reporting_adapter_runs_reporting_pipeline(monkeypatch) -> None:
    calls: list[tuple[str, str, str, int, bool]] = []

    def fake_run_reporting(
        input_csv_path: str,
        output_table_dir: str,
        output_fig_dir: str,
        expected_task_count: int,
        require_full_task_counts: bool,
    ) -> None:
        calls.append(
            (
                input_csv_path,
                output_table_dir,
                output_fig_dir,
                expected_task_count,
                require_full_task_counts,
            )
        )

    monkeypatch.setattr(
        "covert_collusive_hotpot.domains.knowledge_qa.reporting.run_knowledge_qa_reporting",
        fake_run_reporting,
    )

    adapter = KnowledgeQADomain().reporting_adapter(
        input_csv_path="results.csv",
        output_table_dir="tables",
        output_fig_dir="figures",
        expected_task_count=100,
        require_full_task_counts=True,
    )

    adapter.run()

    assert calls == [("results.csv", "tables", "figures", 100, True)]
