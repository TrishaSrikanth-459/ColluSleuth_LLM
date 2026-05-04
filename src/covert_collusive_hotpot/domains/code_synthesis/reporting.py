from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


METRIC_COLUMNS = [
    "unsafe_output_rate_mean",
    "completion_failure_mean",
    "attack_success_mean",
    "latency_mean",
    "false_positive_rate_mean",
    "detection_rate_mean",
    "detection_latency_mean",
    "benign_restriction_rate_mean",
    "benign_recovery_time_mean",
]

STD_COLUMNS = [
    "unsafe_output_rate_std",
    "completion_failure_std",
    "attack_success_std",
    "latency_std",
    "false_positive_rate_std",
    "detection_rate_std",
    "detection_latency_std",
    "benign_restriction_rate_std",
    "benign_recovery_time_std",
]


def _format_mean_std(mean_series: pd.Series, std_series: pd.Series, digits: int = 3) -> pd.Series:
    return mean_series.round(digits).astype(str) + " ± " + std_series.round(digits).astype(str)


def load_results(
    path: str,
    *,
    expected_task_count: int = 25,
    require_full_task_counts: bool = True,
) -> pd.DataFrame:
    input_path = Path(path)
    if not input_path.exists():
        raise FileNotFoundError(f"Could not find results file: {path}")
    df = pd.read_csv(input_path)
    required = {
        "domain",
        "m",
        "d",
        "tasks_evaluated",
        "unsafe_output_rate_mean",
        "latency_mean",
        "detection_rate_mean",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    for col in set(METRIC_COLUMNS + STD_COLUMNS + ["m", "d", "tasks_evaluated"]):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df[df["domain"].astype(str) == "code_synthesis"]
    if require_full_task_counts:
        df = df[df["tasks_evaluated"] == expected_task_count]
    return df.reset_index(drop=True)


def save_summary(df: pd.DataFrame, output_table_dir: str | Path) -> None:
    table_dir = Path(output_table_dir)
    available = [c for c in METRIC_COLUMNS + STD_COLUMNS if c in df.columns]
    grouped = df[available].mean(numeric_only=True).to_frame().T
    display_cols = []
    for metric in ["unsafe_output_rate", "completion_failure", "attack_success",
                   "latency", "false_positive_rate", "detection_rate"]:
        mean_col = f"{metric}_mean"
        std_col = f"{metric}_std"
        if mean_col in grouped.columns and std_col in grouped.columns:
            grouped[metric] = _format_mean_std(grouped[mean_col], grouped[std_col])
            display_cols.append(metric)
    grouped[display_cols].to_csv(table_dir / "summary_code_synthesis.csv", index=False)


def save_condition_table(df: pd.DataFrame, output_table_dir: str | Path) -> None:
    table_dir = Path(output_table_dir)
    out = df.copy()
    out = out.sort_values(by=["m", "d", "rep"], ascending=True)
    out["functional_correctness_mean"] = out.get(
        "functional_correctness_mean", pd.Series(dtype=float)
    ).fillna("deferred")
    out.to_csv(table_dir / "condition_table_code_synthesis.csv", index=False)


def plot_metric_by_condition(
    df: pd.DataFrame,
    metric: str,
    title: str,
    filename: str,
    output_fig_dir: str | Path,
) -> None:
    import matplotlib.pyplot as plt

    metric_col = f"{metric}_mean"
    if metric_col not in df.columns:
        return
    fig_dir = Path(output_fig_dir)
    subset = df.copy()
    subset["condition"] = "m=" + subset["m"].astype(str) + ", d=" + subset["d"].astype(str)
    grouped = subset.groupby("condition", dropna=False)[metric_col].mean().reset_index()
    plt.figure(figsize=(14, 6))
    plt.bar(grouped["condition"], grouped[metric_col])
    plt.xticks(rotation=70, ha="right")
    plt.ylabel(metric.replace("_", " ").title())
    plt.title(title)
    plt.tight_layout()
    plt.savefig(fig_dir / filename, dpi=200)
    plt.close()


@dataclass
class CodeSynthesisReportingAdapter:
    input_csv_path: str
    output_table_dir: str
    output_fig_dir: str
    expected_task_count: int
    require_full_task_counts: bool

    def ensure_dirs(self) -> None:
        Path(self.output_table_dir).mkdir(parents=True, exist_ok=True)
        Path(self.output_fig_dir).mkdir(parents=True, exist_ok=True)

    def load_results(self) -> pd.DataFrame:
        return load_results(
            self.input_csv_path,
            expected_task_count=self.expected_task_count,
            require_full_task_counts=self.require_full_task_counts,
        )

    def run(self) -> None:
        self.ensure_dirs()
        df = self.load_results()
        save_summary(df, self.output_table_dir)
        save_condition_table(df, self.output_table_dir)
        plot_metric_by_condition(
            df,
            "detection_rate",
            "Detection Rate by Condition (Code Synthesis)",
            "cs_detection_rate_by_condition.png",
            self.output_fig_dir,
        )
        plot_metric_by_condition(
            df,
            "attack_success",
            "Attack Success by Condition (Code Synthesis)",
            "cs_attack_success_by_condition.png",
            self.output_fig_dir,
        )
