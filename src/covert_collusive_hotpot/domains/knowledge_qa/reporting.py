from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


@contextmanager
def _paper_asset_config(
    *,
    input_csv_path: str,
    output_table_dir: str,
    output_fig_dir: str,
    expected_task_count: int,
    require_full_task_counts: bool,
) -> Iterator[None]:
    from covert_collusive_hotpot import generate_paper_assets as paper_assets

    original = {
        "INPUT_CSV": paper_assets.INPUT_CSV,
        "OUTPUT_TABLE_DIR": paper_assets.OUTPUT_TABLE_DIR,
        "OUTPUT_FIG_DIR": paper_assets.OUTPUT_FIG_DIR,
        "EXPECTED_TASKS": paper_assets.EXPECTED_TASKS,
        "REQUIRE_FULL_TASK_COUNTS": paper_assets.REQUIRE_FULL_TASK_COUNTS,
    }

    paper_assets.INPUT_CSV = input_csv_path
    paper_assets.OUTPUT_TABLE_DIR = Path(output_table_dir)
    paper_assets.OUTPUT_FIG_DIR = Path(output_fig_dir)
    paper_assets.EXPECTED_TASKS = expected_task_count
    paper_assets.REQUIRE_FULL_TASK_COUNTS = require_full_task_counts
    try:
        yield
    finally:
        paper_assets.INPUT_CSV = original["INPUT_CSV"]
        paper_assets.OUTPUT_TABLE_DIR = original["OUTPUT_TABLE_DIR"]
        paper_assets.OUTPUT_FIG_DIR = original["OUTPUT_FIG_DIR"]
        paper_assets.EXPECTED_TASKS = original["EXPECTED_TASKS"]
        paper_assets.REQUIRE_FULL_TASK_COUNTS = original["REQUIRE_FULL_TASK_COUNTS"]


def run_knowledge_qa_reporting(
    input_csv_path: str,
    output_table_dir: str,
    output_fig_dir: str,
    expected_task_count: int,
    require_full_task_counts: bool,
) -> None:
    from covert_collusive_hotpot import generate_paper_assets as paper_assets

    with _paper_asset_config(
        input_csv_path=input_csv_path,
        output_table_dir=output_table_dir,
        output_fig_dir=output_fig_dir,
        expected_task_count=expected_task_count,
        require_full_task_counts=require_full_task_counts,
    ):
        paper_assets.main()
