from __future__ import annotations

from covert_collusive_hotpot.core.config import DEFAULT_DOMAIN
from covert_collusive_hotpot.domains.base import DomainSpec


_BOOTSTRAP_DEFAULT_DOMAIN = "knowledge_qa"
_domain_registry: DomainRegistry | None = None


class DomainRegistry:
    def __init__(self, default_domain: str):
        self._default_domain_name = default_domain
        self._domains: dict[str, DomainSpec] = {}

    def register(self, domain: DomainSpec) -> None:
        if domain.name in self._domains:
            raise ValueError(f"Domain '{domain.name}' is already registered")
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
        try:
            return self._domains[self._default_domain_name]
        except KeyError as exc:
            supported = ", ".join(sorted(self._domains))
            raise ValueError(
                f"Default domain '{self._default_domain_name}' is not registered. "
                f"Supported domains: {supported}"
            ) from exc


def get_domain_registry() -> DomainRegistry:
    global _domain_registry

    if _domain_registry is None:
        from covert_collusive_hotpot.domains.knowledge_qa import KnowledgeQADomain

        knowledge_qa = KnowledgeQADomain()
        default_domain = DEFAULT_DOMAIN if DEFAULT_DOMAIN == knowledge_qa.name else _BOOTSTRAP_DEFAULT_DOMAIN
        registry = DomainRegistry(default_domain=default_domain)
        registry.register(knowledge_qa)
        _domain_registry = registry

    return _domain_registry
