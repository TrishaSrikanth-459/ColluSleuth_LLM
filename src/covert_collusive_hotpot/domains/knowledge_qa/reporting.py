from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


METRIC_COLUMNS = [
    "unsafe_output_rate_mean",
    "functional_correctness_mean",
    "latency_mean",
    "false_positive_rate_mean",
    "detection_rate_mean",
    "detection_latency_mean",
    "benign_restriction_rate_mean",
    "benign_recovery_time_mean",
]

STD_COLUMNS = [
    "unsafe_output_rate_std",
    "functional_correctness_std",
    "latency_std",
    "false_positive_rate_std",
    "detection_rate_std",
    "detection_latency_std",
    "benign_restriction_rate_std",
    "benign_recovery_time_std",
]


def _pretty_knowledge_level(value: object) -> str:
    if pd.isna(value):
        return "N/A"
    mapping = {
        "unaware": "Unaware",
        "aware_of_presence": "Aware",
        "fully_prepared": "Prepared",
        "None": "N/A",
        "none": "N/A",
        "": "N/A",
    }
    return mapping.get(str(value), str(value))


def _format_mean_std(mean_series: pd.Series, std_series: pd.Series, digits: int = 3) -> pd.Series:
    return mean_series.round(digits).astype(str) + " ± " + std_series.round(digits).astype(str)


def load_results(
    path: str,
    *,
    expected_task_count: int = 100,
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
    df = df[df["domain"].astype(str) == "knowledge_qa"]
    if require_full_task_counts:
        df = df[df["tasks_evaluated"] == expected_task_count]
    return df.reset_index(drop=True)


def save_summary(df: pd.DataFrame, output_table_dir: str | Path) -> None:
    table_dir = Path(output_table_dir)
    grouped = df[METRIC_COLUMNS + STD_COLUMNS].mean(numeric_only=True).to_frame().T
    grouped["unsafe_output_rate"] = _format_mean_std(grouped["unsafe_output_rate_mean"], grouped["unsafe_output_rate_std"])
    grouped["functional_correctness"] = _format_mean_std(grouped["functional_correctness_mean"], grouped["functional_correctness_std"])
    grouped["latency"] = _format_mean_std(grouped["latency_mean"], grouped["latency_std"])
    grouped["false_positive_rate"] = _format_mean_std(grouped["false_positive_rate_mean"], grouped["false_positive_rate_std"])
    grouped["detection_rate"] = _format_mean_std(grouped["detection_rate_mean"], grouped["detection_rate_std"])
    grouped[["unsafe_output_rate", "functional_correctness", "latency", "false_positive_rate", "detection_rate"]].to_csv(
        table_dir / "summary.csv", index=False
    )


def save_condition_table(df: pd.DataFrame, output_table_dir: str | Path) -> None:
    table_dir = Path(output_table_dir)
    out = df.copy()
    out["knowledge_level"] = out["knowledge_level"].apply(_pretty_knowledge_level)
    out = out.sort_values(by=["m", "d", "knowledge_level", "rep"], ascending=[True, True, True, True])
    out.to_csv(table_dir / "condition_table.csv", index=False)


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
    subset["knowledge_level_pretty"] = subset["knowledge_level"].apply(_pretty_knowledge_level)
    subset["condition"] = (
        "m=" + subset["m"].astype(str)
        + ", d=" + subset["d"].astype(str)
        + ", k=" + subset["knowledge_level_pretty"].astype(str)
    )
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
class KnowledgeQAReportingAdapter:
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
            "Detection Rate by Condition",
            "detection_rate_by_condition.png",
            self.output_fig_dir,
        )
        plot_metric_by_condition(
            df,
            "functional_correctness",
            "Functional Correctness by Condition",
            "functional_correctness_by_condition.png",
            self.output_fig_dir,
        )


def run_knowledge_qa_reporting(
    input_csv_path: str,
    output_table_dir: str,
    output_fig_dir: str,
    expected_task_count: int,
    require_full_task_counts: bool,
) -> None:
    KnowledgeQAReportingAdapter(
        input_csv_path=input_csv_path,
        output_table_dir=output_table_dir,
        output_fig_dir=output_fig_dir,
        expected_task_count=expected_task_count,
        require_full_task_counts=require_full_task_counts,
    ).run()
