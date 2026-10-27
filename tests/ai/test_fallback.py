"""
Unit tests for DeterministicSynthesizer offline report generation.
"""

from incident_investigator.ai.fallback import DeterministicSynthesizer
from incident_investigator.dependency.models import Asset, AssetType
from incident_investigator.detection.volume import PipelineRun, VolumeAnomalyResult
from incident_investigator.incident.builder import build_incident_from_findings
from incident_investigator.investigation.investigator import investigate_incident


def test_deterministic_fallback_report_generation():
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
        message="Volume anomaly detected! Record count dropped by 38.00%.",
    )
    incident = build_incident_from_findings(run=run, volume_result=vol_result)
    assert incident is not None

    inv_result = investigate_incident(incident, dependency_graph=None)
    synthesizer = DeterministicSynthesizer()
    report = synthesizer.synthesize(inv_result)

    assert report.incident_id == "INC-orders_ingestion-run_001"
    assert report.is_fallback is True
    assert report.provider_used == "deterministic_fallback"
    assert report.root_cause_status == "UNCONFIRMED_PENDING_EVIDENCE"
    assert "EVD-001" in report.cited_evidence_ids
    assert len(report.recommended_actions) >= 2

    # Check that recommended actions contain safe, read-only suggestions
    for action in report.recommended_actions:
        assert action.priority in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
        if action.suggested_query_or_check:
            # Must NOT contain destructive keywords
            lower_cmd = action.suggested_query_or_check.lower()
            assert "drop table" not in lower_cmd
            assert "delete from" not in lower_cmd
            assert "truncate" not in lower_cmd

    # Markdown rendering test
    md = report.to_markdown()
    assert "# AI Incident Investigation Brief" in md
    assert "EVD-001" in md
    assert "Recommended Operational Actions" in md
