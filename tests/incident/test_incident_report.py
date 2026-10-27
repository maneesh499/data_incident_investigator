"""
Unit tests for incident report generation.
"""

from datetime import datetime, timezone
from incident_investigator.incident.models import Evidence, Incident, IncidentStatus, Severity
from incident_investigator.incident.report import generate_incident_report


def test_generate_report_with_pending_investigation():
    """Report without root cause highlights pending investigation and lists evidence."""
    evidence = Evidence(
        evidence_id="EVD-001",
        source="volume_detector",
        description="Volume dropped by 38.00%",
        severity="CRITICAL",
        observed_value=6200000,
        threshold=10000000,
        timestamp=datetime(2026, 10, 26, 12, 0, 0, tzinfo=timezone.utc),
    )
    incident = Incident(
        incident_id="INC-orders_ingestion-run_001",
        title="Data Incident on orders_ingestion (run_001)",
        pipeline_name="orders_ingestion",
        run_id="run_001",
        severity=Severity.CRITICAL.value,
        status=IncidentStatus.OPEN.value,
        created_at=datetime(2026, 10, 26, 12, 5, 0, tzinfo=timezone.utc),
        symptoms=["Volume drop anomaly: record count dropped by 38.00%"],
        evidence_items=[evidence],
        root_cause=None,
        affected_assets=["orders_ingestion", "silver_orders_cleaned"],
    )

    report = generate_incident_report(incident)

    assert "# Incident Report: INC-orders_ingestion-run_001" in report
    assert "**Severity**: `CRITICAL`" in report
    assert "**Pipeline**: `orders_ingestion`" in report
    assert "silver_orders_cleaned" in report
    assert "Volume drop anomaly: record count dropped by 38.00%" in report
    assert "| EVD-001 | volume_detector | CRITICAL | 6200000 | 10000000 | Volume dropped by 38.00% |" in report
    assert "Pending Investigation" in report
    assert "In accordance with investigative rigor" in report


def test_generate_report_with_confirmed_root_cause():
    """Report displays confirmed root cause when present."""
    incident = Incident(
        incident_id="INC-customer_sync-run_002",
        title="Data Incident on customer_sync",
        pipeline_name="customer_sync",
        run_id="run_002",
        severity=Severity.HIGH.value,
        status=IncidentStatus.RESOLVED.value,
        symptoms=["Freshness SLA breached"],
        evidence_items=[],
        root_cause="Upstream CRM API maintenance window delayed data extraction by 6.5 hours.",
    )

    report = generate_incident_report(incident)
    assert "**Confirmed Cause**: Upstream CRM API maintenance window" in report
    assert "Pending Investigation" not in report
