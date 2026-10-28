"""
Unit and integration tests for CLI scenario execution.
"""

from pathlib import Path
import pytest
from incident_investigator.cli.scenarios import (
    AVAILABLE_SCENARIOS,
    Scenario,
    execute_scenario,
)


def test_available_scenarios_configuration():
    assert len(AVAILABLE_SCENARIOS) >= 3
    numbers = [s.number for s in AVAILABLE_SCENARIOS]
    assert numbers == list(range(1, len(AVAILABLE_SCENARIOS) + 1))


def test_execute_scenario_1_volume_drop():
    s1 = AVAILABLE_SCENARIOS[0]
    result = execute_scenario(s1)

    assert result.run.pipeline_name == "orders_ingestion"
    assert result.incident is not None
    assert result.incident.severity == "CRITICAL"
    assert len(result.incident.evidence_items) == 1
    assert result.incident.evidence_items[0].source == "volume_detector"
    assert result.investigation is not None
    assert len(result.investigation.affected_assets) == 6
    assert result.ai_report is not None
    assert result.ai_report.root_cause_status == "UNCONFIRMED_PENDING_EVIDENCE"


def test_execute_scenario_2_data_quality():
    s2 = AVAILABLE_SCENARIOS[1]
    result = execute_scenario(s2)

    assert result.run.pipeline_name == "orders_cleaning_pipeline"
    assert result.incident is not None
    assert result.incident.severity == "CRITICAL"
    assert len(result.incident.evidence_items) == 2
    sources = {ev.source for ev in result.incident.evidence_items}
    assert "duplicate_key_check" in sources
    assert "null_column_check" in sources
    assert result.ai_report is not None


def test_execute_scenario_3_freshness_sla():
    s3 = AVAILABLE_SCENARIOS[2]
    result = execute_scenario(s3)

    assert result.run.pipeline_name == "revenue_mart_pipeline"
    assert result.incident is not None
    assert result.incident.severity == "HIGH"
    assert result.incident.evidence_items[0].source == "freshness_check"


def test_execute_scenario_4_healthy_run():
    s4 = AVAILABLE_SCENARIOS[3]
    result = execute_scenario(s4)

    assert result.run.actual_record_count == 10000000
    assert result.incident is None  # Healthy run creates no incident
    assert result.investigation is None
    assert "No incident opened" in result.markdown_report


def test_execute_scenario_missing_file_raises_filenotfound(tmp_path):
    fake_scenario = Scenario(
        id="fake",
        number=99,
        title="Fake",
        category="Test",
        summary="Test",
        run_file="missing_run.json",
    )
    with pytest.raises(FileNotFoundError, match="Scenario run log file not found"):
        execute_scenario(fake_scenario, data_dir=tmp_path)
