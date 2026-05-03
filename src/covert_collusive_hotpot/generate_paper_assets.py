"""
Domain-aware entry point for generating paper-ready tables and figures.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from covert_collusive_hotpot.core import config
from covert_collusive_hotpot.domains.base import ReportingAdapter
from covert_collusive_hotpot.domains.registry import get_domain_registry
from covert_collusive_hotpot.domains.knowledge_qa.reporting import load_results as _load_knowledge_qa_results


INPUT_CSV = os.getenv("INPUT_CSV", "experiment_results.csv")
OUTPUT_TABLE_DIR = Path(os.getenv("OUTPUT_TABLE_DIR", "results/paper_tables"))
OUTPUT_FIG_DIR = Path(os.getenv("OUTPUT_FIG_DIR", "results/paper_figures"))
EXPECTED_TASKS = int(os.getenv("EXPECTED_TASKS", "100"))
REQUIRE_FULL_TASK_COUNTS = os.getenv("REQUIRE_FULL_TASK_COUNTS", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "y",
    "on",
}


def resolve_domain_name(cli_value: str | None = None) -> str:
    selected = cli_value if cli_value is not None else os.getenv("REPORT_DOMAIN")
    selected = (selected or "").strip()
    if selected:
        return selected
    return config.DEFAULT_DOMAIN


def load_results(path: str):
    return _load_knowledge_qa_results(
        path,
        expected_task_count=EXPECTED_TASKS,
        require_full_task_counts=REQUIRE_FULL_TASK_COUNTS,
    )


def resolve_reporting_adapter(
    domain_name: str,
    *,
    input_csv_path: str,
    output_table_dir: str,
    output_fig_dir: str,
    expected_task_count: int,
    require_full_task_counts: bool,
) -> ReportingAdapter:
    domain = get_domain_registry().get(domain_name)
    return domain.reporting_adapter(
        input_csv_path=input_csv_path,
        output_table_dir=output_table_dir,
        output_fig_dir=output_fig_dir,
        expected_task_count=expected_task_count,
        require_full_task_counts=require_full_task_counts,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate paper-ready tables and figures from experiment results")
    parser.add_argument("--domain", default=None, help="Reporting domain. Defaults to REPORT_DOMAIN or DOMAIN/default config")
    parser.add_argument("--input-csv", default=INPUT_CSV, help="Input aggregate experiment results CSV")
    parser.add_argument("--output-table-dir", default=str(OUTPUT_TABLE_DIR), help="Directory for generated CSV tables")
    parser.add_argument("--output-fig-dir", default=str(OUTPUT_FIG_DIR), help="Directory for generated figures")
    parser.add_argument("--expected-tasks", type=int, default=EXPECTED_TASKS, help="Expected tasks per condition")
    task_count_group = parser.add_mutually_exclusive_group()
    task_count_group.add_argument(
        "--require-full-task-counts",
        dest="require_full_task_counts",
        action="store_true",
        help="Only include rows with expected task counts",
    )
    task_count_group.add_argument(
        "--allow-partial-task-counts",
        dest="require_full_task_counts",
        action="store_false",
        help="Include rows even if task counts are partial",
    )
    parser.set_defaults(require_full_task_counts=REQUIRE_FULL_TASK_COUNTS)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_arg_parser().parse_args(argv)
    domain_name = resolve_domain_name(args.domain)
    adapter = resolve_reporting_adapter(
        domain_name,
        input_csv_path=args.input_csv,
        output_table_dir=args.output_table_dir,
        output_fig_dir=args.output_fig_dir,
        expected_task_count=args.expected_tasks,
        require_full_task_counts=args.require_full_task_counts,
    )
    adapter.run()
    print(f"Saved {domain_name} paper tables to {Path(args.output_table_dir).resolve()}")
    print(f"Saved {domain_name} paper figures to {Path(args.output_fig_dir).resolve()}")


if __name__ == "__main__":
    main()
