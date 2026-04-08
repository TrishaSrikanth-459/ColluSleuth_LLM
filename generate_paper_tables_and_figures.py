"""
Generate paper-ready tables and figures from experiment_results.csv.

Expected input columns include:
- domain
- m
- d
- knowledge_level
- condition_type
- is_ablation_no_detector
- is_ablation_no_attacker
- is_full_system
- unsafe_output_rate_mean
- unsafe_output_rate_std
- functional_correctness_mean
- functional_correctness_std
- latency_mean
- latency_std
- false_positive_rate_mean
- false_positive_rate_std
- detection_rate_mean
- detection_rate_std
- detection_latency_mean
- detection_latency_std
- tasks_evaluated

Outputs:
- results/paper_tables/summary_by_domain.csv
- results/paper_tables/ablation_summary.csv
- results/paper_tables/full_condition_table.csv
- results/paper_figures/*.png
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Iterable

import matplotlib.pyplot as plt
import pandas as pd


INPUT_CSV = "experiment_results.csv"
OUTPUT_TABLE_DIR = Path("results/paper_tables")
OUTPUT_FIG_DIR = Path("results/paper_figures")


METRIC_COLUMNS = [
    "unsafe_output_rate_mean",
    "functional_correctness_mean",
    "latency_mean",
    "false_positive_rate_mean",
    "detection_rate_mean",
    "detection_latency_mean",
]

STD_COLUMNS = [
    "unsafe_output_rate_std",
    "functional_correctness_std",
    "latency_std",
    "false_positive_rate_std",
    "detection_rate_std",
    "detection_latency_std",
]


def ensure_dirs() -> None:
    OUTPUT_TABLE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FIG_DIR.mkdir(parents=True, exist_ok=True)


def load_results(path: str) -> pd.DataFrame:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Could not find results file: {path}")

    df = pd.read_csv(path)

    required = {
        "domain",
        "m",
        "d",
        "knowledge_level",
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

    # Coerce numeric columns
    for col in METRIC_COLUMNS + STD_COLUMNS + ["m", "d", "tasks_evaluated"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def _pretty_knowledge_level(val: object) -> str:
    if pd.isna(val):
        return "N/A"
    s = str(val)
    mapping = {
        "unaware": "Unaware",
        "aware_of_presence": "Aware",
        "fully_prepared": "Prepared",
        "None": "N/A",
    }
    return mapping.get(s, s)


def _format_mean_std(mean_series: pd.Series, std_series: pd.Series, digits: int = 3) -> pd.Series:
    return mean_series.round(digits).astype(str) + " ± " + std_series.round(digits).astype(str)


def _safe_mean(df: pd.DataFrame, cols: Iterable[str]) -> pd.DataFrame:
    return df[list(cols)].mean(numeric_only=True).reset_index(drop=True)


def save_summary_by_domain(df: pd.DataFrame) -> None:
    grouped = (
        df.groupby("domain", dropna=False)[METRIC_COLUMNS + STD_COLUMNS]
        .mean(numeric_only=True)
        .reset_index()
    )

    grouped["unsafe_output_rate"] = _format_mean_std(
        grouped["unsafe_output_rate_mean"], grouped["unsafe_output_rate_std"]
    )
    grouped["functional_correctness"] = _format_mean_std(
        grouped["functional_correctness_mean"], grouped["functional_correctness_std"]
    )
    grouped["latency"] = _format_mean_std(
        grouped["latency_mean"], grouped["latency_std"]
    )
    grouped["false_positive_rate"] = _format_mean_std(
        grouped["false_positive_rate_mean"], grouped["false_positive_rate_std"]
    )
    grouped["detection_rate"] = _format_mean_std(
        grouped["detection_rate_mean"], grouped["detection_rate_std"]
    )
    grouped["detection_latency"] = _format_mean_std(
        grouped["detection_latency_mean"], grouped["detection_latency_std"]
    )

    out = grouped[
        [
            "domain",
            "unsafe_output_rate",
            "functional_correctness",
            "latency",
            "false_positive_rate",
            "detection_rate",
            "detection_latency",
        ]
    ]
    out.to_csv(OUTPUT_TABLE_DIR / "summary_by_domain.csv", index=False)


def save_ablation_summary(df: pd.DataFrame) -> None:
    df = df.copy()

    def label_row(row: pd.Series) -> str:
        if row.get("is_ablation_no_attacker", False):
            return "No attackers"
        if row.get("is_ablation_no_detector", False):
            return "No detectors"
        return "Full system"

    if "is_ablation_no_attacker" not in df.columns:
        df["is_ablation_no_attacker"] = df["m"] == 0
    if "is_ablation_no_detector" not in df.columns:
        df["is_ablation_no_detector"] = df["d"] == 0

    df["ablation_group"] = df.apply(label_row, axis=1)

    grouped = (
        df.groupby(["domain", "ablation_group"], dropna=False)[METRIC_COLUMNS + STD_COLUMNS]
        .mean(numeric_only=True)
        .reset_index()
    )

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

    out = grouped[
        [
            "domain",
            "ablation_group",
            "unsafe_output_rate",
            "functional_correctness",
            "false_positive_rate",
            "detection_rate",
        ]
    ]
    out.to_csv(OUTPUT_TABLE_DIR / "ablation_summary.csv", index=False)


def save_full_condition_table(df: pd.DataFrame) -> None:
    out = df.copy()
    out["knowledge_level"] = out["knowledge_level"].apply(_pretty_knowledge_level)

    out = out.sort_values(
        by=["domain", "m", "d", "knowledge_level"],
        ascending=[True, True, True, True],
    )

    out.to_csv(OUTPUT_TABLE_DIR / "full_condition_table.csv", index=False)


def plot_detection_rate_by_condition(df: pd.DataFrame) -> None:
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
        plt.bar(subset["condition"], subset["detection_rate_mean"])
        plt.xticks(rotation=70, ha="right")
        plt.ylabel("Detection Rate")
        plt.title(f"Detection Rate by Condition ({domain})")
        plt.tight_layout()
        plt.savefig(OUTPUT_FIG_DIR / f"detection_rate_by_condition_{domain}.png", dpi=200)
        plt.close()


def plot_functional_correctness_by_condition(df: pd.DataFrame) -> None:
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
        plt.bar(subset["condition"], subset["functional_correctness_mean"])
        plt.xticks(rotation=70, ha="right")
        plt.ylabel("Functional Correctness")
        plt.title(f"Functional Correctness by Condition ({domain})")
        plt.tight_layout()
        plt.savefig(OUTPUT_FIG_DIR / f"functional_correctness_by_condition_{domain}.png", dpi=200)
        plt.close()


def plot_ablation_comparison(df: pd.DataFrame) -> None:
    df = df.copy()
    if "is_ablation_no_attacker" not in df.columns:
        df["is_ablation_no_attacker"] = df["m"] == 0
    if "is_ablation_no_detector" not in df.columns:
        df["is_ablation_no_detector"] = df["d"] == 0

    def label_row(row: pd.Series) -> str:
        if row["is_ablation_no_attacker"]:
            return "No attackers"
        if row["is_ablation_no_detector"]:
            return "No detectors"
        return "Full system"

    df["ablation_group"] = df.apply(label_row, axis=1)

    grouped = (
        df.groupby(["domain", "ablation_group"], dropna=False)[
            ["detection_rate_mean", "functional_correctness_mean", "unsafe_output_rate_mean"]
        ]
        .mean(numeric_only=True)
        .reset_index()
    )

    for metric in ["detection_rate_mean", "functional_correctness_mean", "unsafe_output_rate_mean"]:
        plt.figure(figsize=(10, 5))
        labels: List[str] = []
        values: List[float] = []

        for domain in sorted(grouped["domain"].dropna().unique()):
            sub = grouped[grouped["domain"] == domain]
            for _, row in sub.iterrows():
                labels.append(f"{domain}\n{row['ablation_group']}")
                values.append(row[metric])

        plt.bar(labels, values)
        plt.xticks(rotation=25, ha="right")
        plt.ylabel(metric.replace("_mean", "").replace("_", " ").title())
        plt.title(metric.replace("_mean", "").replace("_", " ").title() + " Across Ablations")
        plt.tight_layout()
        plt.savefig(OUTPUT_FIG_DIR / f"{metric}_ablation_comparison.png", dpi=200)
        plt.close()


def main() -> None:
    ensure_dirs()
    df = load_results(INPUT_CSV)

    save_summary_by_domain(df)
    save_ablation_summary(df)
    save_full_condition_table(df)

    plot_detection_rate_by_condition(df)
    plot_functional_correctness_by_condition(df)
    plot_ablation_comparison(df)

    print(f"Saved tables to: {OUTPUT_TABLE_DIR}")
    print(f"Saved figures to: {OUTPUT_FIG_DIR}")


if __name__ == "__main__":
    main()
