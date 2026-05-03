import csv
from importlib import reload

import pytest

from covert_collusive_hotpot import generate_paper_assets as paper_assets
from covert_collusive_hotpot.core import config as cfg
from covert_collusive_hotpot.domains import registry as registry_module
from covert_collusive_hotpot.domains.base import ReportingAdapter
from covert_collusive_hotpot.domains.knowledge_qa.reporting import KnowledgeQAReportingAdapter


def _write_synthetic_qa_csv(path) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
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
                "unsafe_output_rate_std",
                "functional_correctness_std",
                "latency_std",
                "false_positive_rate_std",
                "detection_rate_std",
                "detection_latency_std",
                "benign_restriction_rate_mean",
                "benign_recovery_time_mean",
                "benign_restriction_rate_std",
                "benign_recovery_time_std",
                "rep",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "domain": "knowledge_qa",
                "m": "0",
                "d": "0",
                "knowledge_level": "none",
                "tasks_evaluated": "100",
                "unsafe_output_rate_mean": "0.0",
                "functional_correctness_mean": "1.0",
                "latency_mean": "1.0",
                "false_positive_rate_mean": "0.0",
                "detection_rate_mean": "0.0",
                "detection_latency_mean": "0.0",
                "unsafe_output_rate_std": "0.0",
                "functional_correctness_std": "0.0",
                "latency_std": "0.0",
                "false_positive_rate_std": "0.0",
                "detection_rate_std": "0.0",
                "detection_latency_std": "0.0",
                "benign_restriction_rate_mean": "0.0",
                "benign_recovery_time_mean": "0.0",
                "benign_restriction_rate_std": "0.0",
                "benign_recovery_time_std": "0.0",
                "rep": "1",
            }
        )
        writer.writerow(
            {
                "domain": "code_synthesis",
                "m": "0",
                "d": "0",
                "knowledge_level": "none",
                "tasks_evaluated": "100",
                "unsafe_output_rate_mean": "0.5",
                "functional_correctness_mean": "0.5",
                "latency_mean": "1.0",
                "false_positive_rate_mean": "0.0",
                "detection_rate_mean": "0.5",
                "detection_latency_mean": "0.0",
                "unsafe_output_rate_std": "0.0",
                "functional_correctness_std": "0.0",
                "latency_std": "0.0",
                "false_positive_rate_std": "0.0",
                "detection_rate_std": "0.0",
                "detection_latency_std": "0.0",
                "benign_restriction_rate_mean": "0.0",
                "benign_recovery_time_mean": "0.0",
                "benign_restriction_rate_std": "0.0",
                "benign_recovery_time_std": "0.0",
                "rep": "1",
            }
        )


@pytest.fixture(autouse=True)
def restore_reporting_environment(monkeypatch):
    monkeypatch.delenv("REPORT_DOMAIN", raising=False)
    monkeypatch.delenv("DOMAIN", raising=False)
    reload(cfg)
    reload(registry_module)
    reload(paper_assets)


def test_resolve_domain_name_uses_registry_default_and_env_with_cli_winning(monkeypatch) -> None:
    assert paper_assets.resolve_domain_name() == "knowledge_qa"

    monkeypatch.setenv("REPORT_DOMAIN", "env_domain")
    assert paper_assets.resolve_domain_name() == "env_domain"
    assert paper_assets.resolve_domain_name("cli_domain") == "cli_domain"


def test_resolve_domain_name_falls_back_to_registry_default_for_blank_values(monkeypatch) -> None:
    monkeypatch.setenv("REPORT_DOMAIN", "   ")

    assert paper_assets.resolve_domain_name() == "knowledge_qa"
    assert paper_assets.resolve_domain_name("   ") == "knowledge_qa"


def test_resolve_domain_name_uses_registered_default_when_domain_env_is_unimplemented(monkeypatch) -> None:
    monkeypatch.setenv("DOMAIN", "code_synthesis")
    reload(cfg)
    reload(registry_module)
    reload(paper_assets)

    assert paper_assets.resolve_domain_name() == "knowledge_qa"


def test_resolve_reporting_adapter_returns_registry_backed_qa_adapter(tmp_path) -> None:
    adapter = paper_assets.resolve_reporting_adapter(
        "knowledge_qa",
        input_csv_path=str(tmp_path / "results.csv"),
        output_table_dir=str(tmp_path / "tables"),
        output_fig_dir=str(tmp_path / "figures"),
        expected_task_count=100,
        require_full_task_counts=False,
    )

    assert isinstance(adapter, ReportingAdapter)
    assert isinstance(adapter, KnowledgeQAReportingAdapter)
    assert adapter.input_csv_path == str(tmp_path / "results.csv")
    assert adapter.require_full_task_counts is False


def test_generate_paper_assets_load_results_reexports_qa_loader(tmp_path) -> None:
    csv_path = tmp_path / "results.csv"
    _write_synthetic_qa_csv(csv_path)

    loaded = paper_assets.load_results(str(csv_path))

    assert len(loaded) == 1
    assert loaded.loc[0, "domain"] == "knowledge_qa"
    assert loaded.loc[0, "tasks_evaluated"] == 100
    assert loaded.loc[0, "functional_correctness_mean"] == 1.0


def test_cli_help_includes_domain_without_running_reporting(capsys) -> None:
    with pytest.raises(SystemExit) as exc_info:
        paper_assets.main(["--help"])

    captured = capsys.readouterr()
    assert exc_info.value.code == 0
    assert "--domain" in captured.out
    assert "--input-csv" in captured.out


def test_resolve_reporting_adapter_surfaces_unknown_domain_error(tmp_path) -> None:
    with pytest.raises(ValueError, match="Unknown domain 'missing'. Supported domains: knowledge_qa"):
        paper_assets.resolve_reporting_adapter(
            "missing",
            input_csv_path=str(tmp_path / "results.csv"),
            output_table_dir=str(tmp_path / "tables"),
            output_fig_dir=str(tmp_path / "figures"),
            expected_task_count=100,
            require_full_task_counts=True,
        )
