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
