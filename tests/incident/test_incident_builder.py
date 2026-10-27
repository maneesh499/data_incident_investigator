"""
Unit and integration tests for incident builder and severity rules.
"""

from incident_investigator.detection.volume import PipelineRun, VolumeAnomalyResult
from incident_investigator.detection.quality import QualityCheckResult
from incident_investigator.incident.models import Evidence, Incident, IncidentStatus, Severity
from incident_investigator.incident.builder import build_incident_from_findings, determine_severity


def test_determine_severity_hierarchy():
    """Verify severity calculation respects the hierarchy CRITICAL > HIGH > MEDIUM > LOW > INFO."""
    ev_info = Evidence("1", "src", "info check", "INFO", 0, 0)
    ev_medium = Evidence("2", "src", "medium check", "MEDIUM", 0, 0)
    ev_high = Evidence("3", "src", "high check", "HIGH", 0, 0)
    ev_critical = Evidence("4", "src", "critical check", "CRITICAL", 0, 0)

    assert determine_severity([ev_info]) == "INFO"
    assert determine_severity([ev_info, ev_medium]) == "MEDIUM"
    assert determine_severity([ev_medium, ev_high]) == "HIGH"
    assert determine_severity([ev_info, ev_high, ev_critical]) == "CRITICAL"
    assert determine_severity([]) == "LOW"


def test_build_incident_returns_none_when_no_issues():
    """When volume is normal and quality checks pass, no incident should be opened."""
    run = PipelineRun(
        pipeline_name="orders_etl",
        run_id="run_100",
        status="SUCCESS",
        actual_record_count=1000,
        expected_record_count=1000,
    )
    volume_ok = VolumeAnomalyResult(
        is_anomaly=False,
        volume_difference_percentage=0.0,
        message="Volume drop is within acceptable limits."
    )
    quality_ok = QualityCheckResult(
        check_name="null_column_check",
        passed=True,
        severity="INFO",
        observed_value=0,
        threshold=0,
        message="Passed"
    )

    incident = build_incident_from_findings(
        run=run,
        volume_result=volume_ok,
        quality_results=[quality_ok]
    )
    assert incident is None


def test_build_incident_from_critical_volume_drop():
    """A volume drop >= 30% must trigger a CRITICAL severity incident with evidence."""
    run = PipelineRun(
        pipeline_name="orders_ingestion",
        run_id="run_001",
        status="SUCCESS",
        actual_record_count=6200000,
        expected_record_count=10000000,
    )
    vol_result = VolumeAnomalyResult(
        is_anomaly=True,
        volume_difference_percentage=38.0,
        message="Volume anomaly detected! Record count dropped by 38.00%."
    )

    incident = build_incident_from_findings(run=run, volume_result=vol_result)
    assert incident is not None
    assert incident.incident_id == "INC-orders_ingestion-run_001"
    assert incident.severity == "CRITICAL"
    assert incident.status == IncidentStatus.OPEN.value
    assert incident.root_cause is None  # Must NOT assume cause
    assert len(incident.evidence_items) == 1
    assert incident.evidence_items[0].evidence_id == "EVD-001"
    assert incident.evidence_items[0].source == "volume_detector"
    assert incident.evidence_items[0].severity == "CRITICAL"
    assert len(incident.symptoms) == 1
    assert "38.00%" in incident.symptoms[0]


def test_build_incident_from_quality_failures():
    """Failed quality checks are converted into structured evidence items."""
    run = PipelineRun(
        pipeline_name="customer_sync",
        run_id="run_002",
        status="SUCCESS",
        actual_record_count=5000,
        expected_record_count=5000,
    )
    duplicate_fail = QualityCheckResult(
        check_name="duplicate_key_check",
        passed=False,
        severity="CRITICAL",
        observed_value=4,
        threshold=0,
        message="Found 4 duplicate records on primary key order_id."
    )
    freshness_fail = QualityCheckResult(
        check_name="freshness_check",
        passed=False,
        severity="HIGH",
        observed_value=6.5,
        threshold=2.0,
        message="Data freshness SLA breached! Observed lag is 6.50 hours."
    )

    incident = build_incident_from_findings(
        run=run,
        quality_results=[duplicate_fail, freshness_fail]
    )
    assert incident is not None
    assert incident.severity == "CRITICAL"  # Highest of CRITICAL and HIGH
    assert len(incident.evidence_items) == 2
    assert incident.evidence_items[0].evidence_id == "EVD-001"
    assert incident.evidence_items[0].source == "duplicate_key_check"
    assert incident.evidence_items[1].evidence_id == "EVD-002"
    assert incident.evidence_items[1].source == "freshness_check"
    assert len(incident.symptoms) == 2


def test_incident_serialization_to_dict():
    """Verify that an incident and its evidence serialize cleanly to dictionaries."""
    run = PipelineRun(
        pipeline_name="events_pipeline",
        run_id="run_999",
        status="SUCCESS",
        actual_record_count=800,
        expected_record_count=1000,
    )
    vol_result = VolumeAnomalyResult(
        is_anomaly=True,
        volume_difference_percentage=20.0,
        message="Volume dropped by 20.00%."
    )
    incident = build_incident_from_findings(run=run, volume_result=vol_result)
    assert incident is not None

    data = incident.to_dict()
    assert isinstance(data, dict)
    assert data["incident_id"] == "INC-events_pipeline-run_999"
    assert data["severity"] == "HIGH"  # 20% drop < 30%
    assert isinstance(data["evidence_items"], list)
    assert len(data["evidence_items"]) == 1
    assert data["evidence_items"][0]["severity"] == "HIGH"
