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
