"""
Unit and integration tests for AIIncidentSynthesizer: prompt construction, citation filtering,
safety overrides, and fallback recovery.
"""

import json
from incident_investigator.ai.models import AIInvestigationReport
from incident_investigator.ai.providers import MockAIProvider
from incident_investigator.ai.synthesizer import AIIncidentSynthesizer
from incident_investigator.detection.volume import PipelineRun, VolumeAnomalyResult
from incident_investigator.incident.builder import build_incident_from_findings
from incident_investigator.investigation.investigator import investigate_incident


def create_test_investigation():
    run = PipelineRun(
        pipeline_name="orders_ingestion",
        run_id="run_001",
        status="SUCCESS",
        actual_record_count=6200000,
        expected_record_count=10000000,
    )
    vol = VolumeAnomalyResult(
        is_anomaly=True,
        volume_difference_percentage=38.0,
        message="Volume dropped 38%",
    )
    incident = build_incident_from_findings(run=run, volume_result=vol)
    return investigate_incident(incident, dependency_graph=None)


def test_build_prompt_structure():
    inv_result = create_test_investigation()
    synthesizer = AIIncidentSynthesizer(provider=MockAIProvider())
    user_prompt, system_prompt = synthesizer.build_prompt(inv_result)

    assert "Senior Data Reliability AI Assistant" in system_prompt
    assert "GROUNDED IN EVIDENCE" in system_prompt
    assert "orders_ingestion" in user_prompt
    assert "EVD-001" in user_prompt


def test_synthesis_with_mock_provider():
    inv_result = create_test_investigation()
    synthesizer = AIIncidentSynthesizer(provider=MockAIProvider())
    report = synthesizer.synthesize(inv_result)

    assert isinstance(report, AIInvestigationReport)
    assert report.incident_id == "INC-orders_ingestion-run_001"
    assert report.is_fallback is False
    assert report.provider_used == "MockAIProvider"
    assert report.root_cause_status == "UNCONFIRMED_PENDING_EVIDENCE"
    assert report.cited_evidence_ids == ["EVD-001"]
    assert len(report.recommended_actions) == 2


def test_invented_evidence_ids_are_filtered_out():
    """
    Safety rule: If an LLM hallucinates an evidence ID (e.g. EVD-999) that does
    not exist in the incident, it is filtered out of cited_evidence_ids.
    """
    inv_result = create_test_investigation()
    # Mock LLM citing both real EVD-001 and fake EVD-999
    hallucinated_json = json.dumps({
        "executive_summary": "Summary",
        "root_cause_status": "UNCONFIRMED_PENDING_EVIDENCE",
        "hypotheses_analysis": "Analysis",
        "cited_evidence_ids": ["EVD-001", "EVD-999"],  # EVD-999 does not exist
        "confidence_score": 0.75,
        "recommended_actions": [],
    })
    synthesizer = AIIncidentSynthesizer(provider=MockAIProvider(custom_response=hallucinated_json))
    report = synthesizer.synthesize(inv_result)

    # Only real EVD-001 should remain
    assert report.cited_evidence_ids == ["EVD-001"]
    assert "EVD-999" not in report.cited_evidence_ids


def test_unconfirmed_root_cause_cannot_be_overridden_by_llm():
    """
    Safety rule: If the deterministic investigation has root_cause_confirmed = False,
    the synthesizer overrides any hallucinated 'CONFIRMED' claim back to UNCONFIRMED.
    """
    inv_result = create_test_investigation()
    assert inv_result.root_cause_confirmed is False

    premature_confirmation_json = json.dumps({
        "executive_summary": "Summary",
        "root_cause_status": "CONFIRMED",  # LLM claiming confirmed without evidence
        "hypotheses_analysis": "Upstream DB was down",
        "cited_evidence_ids": ["EVD-001"],
        "confidence_score": 0.99,
        "recommended_actions": [],
    })
    synthesizer = AIIncidentSynthesizer(provider=MockAIProvider(custom_response=premature_confirmation_json))
    report = synthesizer.synthesize(inv_result)

    assert report.root_cause_status == "UNCONFIRMED_PENDING_EVIDENCE"


def test_graceful_fallback_on_provider_exception():
    """
    When the AI provider throws an error (e.g. invalid JSON, network drop),
    synthesizer automatically engages DeterministicSynthesizer.
    """
    inv_result = create_test_investigation()
    # Malformed garbage response
    synthesizer = AIIncidentSynthesizer(provider=MockAIProvider(custom_response="Bad non-json response"))
    report = synthesizer.synthesize(inv_result)

    assert report.is_fallback is True
    assert "deterministic_fallback" in report.provider_used
    assert report.root_cause_status == "UNCONFIRMED_PENDING_EVIDENCE"
    assert "EVD-001" in report.cited_evidence_ids


def test_graceful_fallback_when_provider_is_none():
    inv_result = create_test_investigation()
    synthesizer = AIIncidentSynthesizer(provider=None)
    report = synthesizer.synthesize(inv_result)

    assert report.is_fallback is True
    assert report.provider_used == "deterministic_fallback"
