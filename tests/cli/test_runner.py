"""
Unit tests for the interactive CLI runner, menu display, report export, and error handling.
"""

import io
from pathlib import Path
from incident_investigator.cli.runner import IncidentInvestigatorCLI


def test_cli_prints_banner_and_menu():
    out = io.StringIO()
    cli = IncidentInvestigatorCLI(stdout=out)
    cli.print_banner()
    cli.print_menu()
    text = out.getvalue()

    assert "DATA INCIDENT INVESTIGATOR" in text
    assert "[1] Critical Ingestion Volume Drop" in text
    assert "[2] Silver Layer Quality Failure" in text
    assert "[3] Gold Revenue Mart Freshness SLA Breach" in text
    assert "[0] Exit" in text


def test_run_scenario_by_number_success(tmp_path):
    out = io.StringIO()
    cli = IncidentInvestigatorCLI(data_dir=Path("data"), stdout=out)
    res = cli.run_scenario_by_number(1, save_report=True)

    assert res is not None
    assert res.incident is not None
    output = out.getvalue()
    assert "SCENARIO 1" in output
    assert "PIPELINE EXECUTION INGESTION" in output
    assert "DEPENDENCY & BLAST-RADIUS ANALYSIS" in output
    assert "EVIDENCE-BASED HYPOTHESIS EVALUATION" in output
    assert "AI INVESTIGATION SYNTHESIS BRIEF" in output
    assert "Saved comprehensive Markdown report" in output


def test_run_scenario_by_number_invalid():
    out = io.StringIO()
    cli = IncidentInvestigatorCLI(stdout=out)
    res = cli.run_scenario_by_number(999)

    assert res is None
    assert "Invalid scenario number: 999" in out.getvalue()


def test_save_markdown_report_creates_file(tmp_path):
    out = io.StringIO()
    cli = IncidentInvestigatorCLI(data_dir=tmp_path, stdout=out)

    # Copy data directories needed for scenario 1 to tmp_path
    import shutil
    shutil.copytree("data/raw", tmp_path / "raw")
    shutil.copytree("data/fixtures", tmp_path / "fixtures")

    res = cli.run_scenario_by_number(1, save_report=True)
    report_file = tmp_path / "incidents" / "report_scenario_volume_drop.md"

    assert report_file.exists()
    content = report_file.read_text(encoding="utf-8")
    assert "# Incident Report" in content
    assert "EVD-001" in content
