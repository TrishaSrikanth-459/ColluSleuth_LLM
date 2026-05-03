from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from covert_collusive_hotpot.domains.base import (
    DomainCapabilities,
    DomainSpec,
    PromptInjectionContext,
    ReportingAdapter,
)


@dataclass
class _KnowledgeQAReportingAdapter:
    input_csv_path: str
    output_table_dir: str
    output_fig_dir: str
    expected_task_count: int
    require_full_task_counts: bool

    def run(self) -> None:
        from covert_collusive_hotpot.domains.knowledge_qa.reporting import (
            run_knowledge_qa_reporting,
        )

        run_knowledge_qa_reporting(
            input_csv_path=self.input_csv_path,
            output_table_dir=self.output_table_dir,
            output_fig_dir=self.output_fig_dir,
            expected_task_count=self.expected_task_count,
            require_full_task_counts=self.require_full_task_counts,
        )


class KnowledgeQADomain(DomainSpec):
    def __init__(self) -> None:
        super().__init__(
            name="knowledge_qa",
            capabilities=DomainCapabilities(language_only_permissions=True),
        )

    def build_task_pool(self, task_count: int, seed: int | None) -> list[dict[str, Any]]:
        from covert_collusive_hotpot.experiments.hotpot_loader import load_hotpotqa_tasks

        return load_hotpotqa_tasks(num_tasks=task_count, seed=seed)

    def assign_roles(self, rng) -> list[Any]:
        from covert_collusive_hotpot.experiments.role_assignment import assign_roles

        return assign_roles(self.name, rng=rng)

    def inject_prompts(
        self,
        agents: list[Any],
        context: PromptInjectionContext,
    ) -> list[Any]:
        from covert_collusive_hotpot.experiments.prompt_injection import inject_hidden_prompts

        return inject_hidden_prompts(
            agents,
            m=context.m,
            attack_type=context.attack_type,
            knowledge_level=context.knowledge_level,
            detector_ids=context.detector_ids,
            detector_visible=context.detector_visible,
            tool_knowledge=context.tool_knowledge,
            interrogation_turns=context.interrogation_turns,
        )

    def reporting_adapter(
        self,
        input_csv_path: str,
        output_table_dir: str,
        output_fig_dir: str,
        expected_task_count: int,
        require_full_task_counts: bool,
    ) -> ReportingAdapter:
        return _KnowledgeQAReportingAdapter(
            input_csv_path=input_csv_path,
            output_table_dir=output_table_dir,
            output_fig_dir=output_fig_dir,
            expected_task_count=expected_task_count,
            require_full_task_counts=require_full_task_counts,
        )
