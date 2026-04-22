"""
Generate paper-ready tables and figures from experiment results.

This version defaults to excluding pilot/partial rows so the plotting pipeline
cannot silently mix 5-task pilots with 100-task full runs.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import pandas as pd


INPUT_CSV = os.getenv("INPUT_CSV", "experiment_results.csv")
OUTPUT_TABLE_DIR = Path(os.getenv("OUTPUT_TABLE_DIR", "results/paper_tables"))
OUTPUT_FIG_DIR = Path(os.getenv("OUTPUT_FIG_DIR", "results/paper_figures"))
EXPECTED_QA_TASKS = int(os.getenv("EXPECTED_QA_TASKS", "100"))
EXPECTED_CODE_TASKS = int(os.getenv("EXPECTED_CODE_TASKS", "100"))
REQUIRE_FULL_TASK_COUNTS = os.getenv("REQUIRE_FULL_TASK_COUNTS", "true").strip().lower() in {"1", "true", "yes", "y", "on"}
RUN_LABEL_FILTER = os.getenv("RUN_LABEL_FILTER", "").strip()

METRIC_COLUMNS = [
    "unsafe_output_rate_mean",
    "functional_correctness_mean",
    "latency_mean",
    "false_positive_rate_mean",
    "detection_rate_mean",
    "detection_latency_mean",
    "code_eval_ok_mean",
    "code_eval_error_mean",
    "code_patch_selected_mean",
    "code_patch_has_placeholder_mean",
]

STD_COLUMNS = [
    "unsafe_output_rate_std",
    "functional_correctness_std",
    "latency_std",
    "false_positive_rate_std",
    "detection_rate_std",
    "detection_latency_std",
    "code_eval_ok_std",
    "code_eval_error_std",
    "code_patch_selected_std",
    "code_patch_has_placeholder_std",
]


def ensure_dirs() -> None:
    OUTPUT_TABLE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FIG_DIR.mkdir(parents=True, exist_ok=True)


def _pretty_knowledge_level(val: object) -> str:
    if pd.isna(val):
        return "N/A"
    mapping = {
        "unaware": "Unaware",
        "aware_of_presence": "Aware",
        "fully_prepared": "Prepared",
        "None": "N/A",
        "none": "N/A",
    }
    s = str(val)
    return mapping.get(s, s)


def _format_mean_std(mean_series: pd.Series, std_series: pd.Series, digits: int = 3) -> pd.Series:
    return mean_series.round(digits).astype(str) + " ± " + std_series.round(digits).astype(str)


def _expected_tasks(domain: str) -> int | None:
    if domain == "knowledge_qa":
        return EXPECTED_QA_TASKS
    if domain == "code_synthesis":
        return EXPECTED_CODE_TASKS
    return None


def load_results(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Could not find results file: {path}")

    df = pd.read_csv(path)
    required = {
        "domain",
        "m",
        "d",
        "knowledge_level",
        "tasks_evaluated",
        "unsafe_output_rate_mean",
        "functional_correctness_mean",
        "latency_mean",
        "false_positive_rate_mean",
        "detection_rate_mean",
        "detection_latency_mean",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    for col in set(METRIC_COLUMNS + STD_COLUMNS + ["m", "d", "tasks_evaluated"]):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if REQUIRE_FULL_TASK_COUNTS:
        df = df[df.apply(lambda row: row["tasks_evaluated"] == _expected_tasks(str(row["domain"])), axis=1)]

    if RUN_LABEL_FILTER and "run_label" in df.columns:
        df = df[df["run_label"].astype(str) == RUN_LABEL_FILTER]

    return df.reset_index(drop=True)


def save_summary_by_domain(df: pd.DataFrame) -> None:
    use_cols = [c for c in METRIC_COLUMNS + STD_COLUMNS if c in df.columns]
    grouped = df.groupby("domain", dropna=False)[use_cols].mean(numeric_only=True).reset_index()

    grouped["unsafe_output_rate"] = _format_mean_std(
        grouped["unsafe_output_rate_mean"], grouped["unsafe_output_rate_std"]
    )
    grouped["functional_correctness"] = _format_mean_std(
        grouped["functional_correctness_mean"], grouped["functional_correctness_std"]
    )
    grouped["latency"] = _format_mean_std(grouped["latency_mean"], grouped["latency_std"])
    grouped["false_positive_rate"] = _format_mean_std(
        grouped["false_positive_rate_mean"], grouped["false_positive_rate_std"]
    )
    grouped["detection_rate"] = _format_mean_std(
        grouped["detection_rate_mean"], grouped["detection_rate_std"]
    )

    out = grouped[
        [
            "domain",
            "unsafe_output_rate",
            "functional_correctness",
            "latency",
            "false_positive_rate",
            "detection_rate",
        ]
    ]
    out.to_csv(OUTPUT_TABLE_DIR / "summary_by_domain.csv", index=False)


def save_ablation_summary(df: pd.DataFrame) -> None:
    df = df.copy()
    if "is_ablation_no_attacker" not in df.columns:
        df["is_ablation_no_attacker"] = df["m"] == 0
    if "is_ablation_no_detector" not in df.columns:
        df["is_ablation_no_detector"] = df["d"] == 0

    def label_row(row: pd.Series) -> str:
        if row.get("is_ablation_no_attacker", False):
            return "No attackers"
        if row.get("is_ablation_no_detector", False):
            return "No detectors"
        return "Full system"

    df["ablation_group"] = df.apply(label_row, axis=1)
    use_cols = [c for c in METRIC_COLUMNS + STD_COLUMNS if c in df.columns]
    grouped = df.groupby(["domain", "ablation_group"], dropna=False)[use_cols].mean(numeric_only=True).reset_index()

    grouped["unsafe_output_rate"] = _format_mean_std(
        grouped["unsafe_output_rate_mean"], grouped["unsafe_output_rate_std"]
    )
    grouped["functional_correctness"] = _format_mean_std(
        grouped["functional_correctness_mean"], grouped["functional_correctness_std"]
    )
    grouped["false_positive_rate"] = _format_mean_std(
        grouped["false_positive_rate_mean"], grouped["false_positive_rate_std"]
    )
    grouped["detection_rate"] = _format_mean_std(
        grouped["detection_rate_mean"], grouped["detection_rate_std"]
    )

    grouped[[
        "domain",
        "ablation_group",
        "unsafe_output_rate",
        "functional_correctness",
        "false_positive_rate",
        "detection_rate",
    ]].to_csv(OUTPUT_TABLE_DIR / "ablation_summary.csv", index=False)


def save_full_condition_table(df: pd.DataFrame) -> None:
    out = df.copy()
    out["knowledge_level"] = out["knowledge_level"].apply(_pretty_knowledge_level)
    out = out.sort_values(by=["domain", "m", "d", "knowledge_level"], ascending=[True, True, True, True])
    out.to_csv(OUTPUT_TABLE_DIR / "full_condition_table.csv", index=False)


def plot_metric_by_condition(df: pd.DataFrame, metric: str, title: str, filename_prefix: str) -> None:
    metric_col = f"{metric}_mean"
    if metric_col not in df.columns:
        return

    for domain in sorted(df["domain"].dropna().unique()):
        subset = df[df["domain"] == domain].copy()
        subset["knowledge_level_pretty"] = subset["knowledge_level"].apply(_pretty_knowledge_level)
        subset["condition"] = (
            "m=" + subset["m"].astype(str)
            + ", d=" + subset["d"].astype(str)
            + ", k=" + subset["knowledge_level_pretty"].astype(str)
        )
        subset = subset.sort_values(by=["m", "d", "knowledge_level_pretty"])

        plt.figure(figsize=(14, 6))
        plt.bar(subset["condition"], subset[metric_col])
        plt.xticks(rotation=70, ha="right")
        plt.ylabel(metric.replace("_", " ").title())
        plt.title(f"{title} ({domain})")
        plt.tight_layout()
        plt.savefig(OUTPUT_FIG_DIR / f"{filename_prefix}_{domain}.png", dpi=200)
        plt.close()


def main() -> None:
    ensure_dirs()
    df = load_results(INPUT_CSV)
    save_summary_by_domain(df)
    save_ablation_summary(df)
    save_full_condition_table(df)
    plot_metric_by_condition(df, "detection_rate", "Detection Rate by Condition", "detection_rate_by_condition")
    plot_metric_by_condition(df, "functional_correctness", "Functional Correctness by Condition", "functional_correctness_by_condition")
    print(f"Saved paper tables to {OUTPUT_TABLE_DIR.resolve()}")
    print(f"Saved paper figures to {OUTPUT_FIG_DIR.resolve()}")


if __name__ == "__main__":
    main()
