from __future__ import annotations

from covert_collusive_hotpot.domains.base import DomainSpec


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
