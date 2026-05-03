from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class DomainCapabilities:
    language_only_permissions: bool


@dataclass(frozen=True)
class PromptInjectionContext:
    m: int | str
    attack_type: Any
    knowledge_level: Any
    detector_ids: list[int]
    detector_visible: bool
    tool_knowledge: bool
    interrogation_turns: list[int] | None


@runtime_checkable
class ReportingAdapter(Protocol):
    def run(self) -> None:
        raise NotImplementedError


class DomainSpec(ABC):
    def __init__(self, name: str, capabilities: DomainCapabilities):
        self.name = name
        self.capabilities = capabilities

    @abstractmethod
    def build_task_pool(self, task_count: int, seed: int | None) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def assign_roles(self, rng) -> list[Any]:
        raise NotImplementedError

    @abstractmethod
    def inject_prompts(
        self,
        agents: list[Any],
        context: PromptInjectionContext,
    ) -> list[Any]:
        raise NotImplementedError

    @abstractmethod
    def reporting_adapter(
        self,
        input_csv_path: str,
        output_table_dir: str,
        output_fig_dir: str,
        expected_task_count: int,
        require_full_task_counts: bool,
    ) -> ReportingAdapter:
        raise NotImplementedError
