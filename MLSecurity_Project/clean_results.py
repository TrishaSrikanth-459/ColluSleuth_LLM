"""
Filter contaminated pilot / partial runs out of experiment CSV files.

By default, rows are kept only when tasks_evaluated matches the expected full
count for that domain. Excluded rows are written to a companion archive file.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List


DEFAULT_EXPECTED = {
    "knowledge_qa": 100,
    "code_synthesis": 100,
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Clean MLSecurity experiment result CSV files")
    parser.add_argument("input_csv", help="Path to the contaminated source CSV")
    parser.add_argument("--output-csv", help="Path for the cleaned full-only CSV")
    parser.add_argument("--excluded-csv", help="Path for excluded pilot/partial rows")
    parser.add_argument("--summary-json", help="Path for a small cleanup summary JSON")
    parser.add_argument("--expected-qa-tasks", type=int, default=DEFAULT_EXPECTED["knowledge_qa"])
    parser.add_argument("--expected-code-tasks", type=int, default=DEFAULT_EXPECTED["code_synthesis"])
    return parser


def _expected_tasks_by_domain(args: argparse.Namespace) -> Dict[str, int]:
    return {
        "knowledge_qa": int(args.expected_qa_tasks),
        "code_synthesis": int(args.expected_code_tasks),
    }


def _default_paths(input_csv: Path) -> Dict[str, Path]:
    stem = input_csv.stem
    suffix = input_csv.suffix or ".csv"
    return {
        "output_csv": input_csv.with_name(f"{stem}.full_only{suffix}"),
        "excluded_csv": input_csv.with_name(f"{stem}.excluded_partial_or_pilot{suffix}"),
        "summary_json": input_csv.with_name(f"{stem}.cleanup_summary.json"),
    }


def _parse_tasks_evaluated(row: Dict[str, str]) -> int | None:
    raw = (row.get("tasks_evaluated") or "").strip()
    if not raw:
        return None
    try:
        return int(float(raw))
    except Exception:
        return None


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    input_csv = Path(args.input_csv).expanduser().resolve()
    defaults = _default_paths(input_csv)
    output_csv = Path(args.output_csv).expanduser().resolve() if args.output_csv else defaults["output_csv"]
    excluded_csv = Path(args.excluded_csv).expanduser().resolve() if args.excluded_csv else defaults["excluded_csv"]
    summary_json = Path(args.summary_json).expanduser().resolve() if args.summary_json else defaults["summary_json"]

    expected = _expected_tasks_by_domain(args)

    with input_csv.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    kept: List[Dict[str, str]] = []
    excluded: List[Dict[str, str]] = []

    for row in rows:
        domain = (row.get("domain") or "").strip()
        tasks_evaluated = _parse_tasks_evaluated(row)
        expected_tasks = expected.get(domain)
        if expected_tasks is not None and tasks_evaluated == expected_tasks:
            kept.append(row)
        else:
            excluded.append(row)

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    excluded_csv.parent.mkdir(parents=True, exist_ok=True)
    summary_json.parent.mkdir(parents=True, exist_ok=True)

    with output_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(kept)

    with excluded_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(excluded)

    summary = {
        "input_csv": str(input_csv),
        "output_csv": str(output_csv),
        "excluded_csv": str(excluded_csv),
        "rows_total": len(rows),
        "rows_kept": len(kept),
        "rows_excluded": len(excluded),
        "expected_tasks_by_domain": expected,
    }
    summary_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
