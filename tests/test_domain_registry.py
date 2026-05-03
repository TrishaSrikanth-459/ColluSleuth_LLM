from typing import get_type_hints

from covert_collusive_hotpot.domains.base import (
    DomainCapabilities,
    DomainSpec,
    PromptInjectionContext,
    ReportingAdapter,
)
from covert_collusive_hotpot.domains.registry import DomainRegistry


class DummyReportingAdapter:
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

    def reporting_adapter(self):
        return DummyReportingAdapter


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


def test_domain_spec_reporting_adapter_contract_is_factory_typed() -> None:
    hints = get_type_hints(DomainSpec.reporting_adapter)

    assert hints["return"] == type[ReportingAdapter]


def test_dummy_domain_reporting_adapter_returns_factory() -> None:
    domain = DummyDomain("knowledge_qa")
    adapter_type = domain.reporting_adapter()
    adapter = adapter_type()

    assert adapter_type is DummyReportingAdapter
    assert isinstance(adapter, ReportingAdapter)


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
