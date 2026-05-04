"""
Post-hoc functional correctness evaluation for code synthesis experiments.

Usage:
    evaluate-code-synthesis --input results.csv --output results_evaluated.csv

Reads rows where domain == "code_synthesis" and functional_correctness_mean is
null, applies each recorded patch against the SWE-bench Docker evaluation
harness, and writes functional_correctness back into the output CSV.

Full Docker harness integration is future work. This entry point exists to
reserve the CLI surface and document the expected interface.
"""
from __future__ import annotations

import argparse


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate deferred code synthesis functional correctness via SWE-bench Docker harness."
    )
    parser.add_argument("--input", required=True, help="Input results CSV path")
    parser.add_argument("--output", required=True, help="Output results CSV path with correctness filled in")
    return parser


def main() -> None:
    build_arg_parser().parse_args()
    raise NotImplementedError(
        "Full SWE-bench Docker harness integration is not yet implemented. "
        "To evaluate: extract predicted patches from the input CSV and run the "
        "official SWE-bench evaluation harness (https://github.com/princeton-nlp/SWE-bench) "
        "against them, then fill in functional_correctness_mean per row."
    )


if __name__ == "__main__":
    main()
