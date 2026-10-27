"""
Unit tests for deterministic hypothesis evaluation against evidence.
Verifies strict causal standards, relevance-based contradiction, and missing evidence handling.
"""

from incident_investigator.incident.models import Evidence, Incident, Severity
from incident_investigator.investigation.evaluator import evaluate_hypotheses, evaluate_hypothesis
from incident_investigator.investigation.models import (
    CandidateHypothesis,
    HypothesisStatus,
)


def test_volume_drop_alone_does_not_claim_pipeline_logic_supported():
    """
    Requirement 2 & 3:
    In the scenario where record count falls from 10,000,000 to 6,200,000,
    the aggregate volume drop verifies that an anomaly occurred, but does NOT
    prove internal pipeline extraction or filtering logic caused the drop.
    It must evaluate to INSUFFICIENT_EVIDENCE with missing execution telemetry.
    """
    volume_ev = Evidence(
        evidence_id="EVD-001",
        source="volume_detector",
        description="Volume dropped by 38.00%",
        severity="CRITICAL",
        observed_value=6200000,
        threshold=10000000,
    )
    incident = Incident(
        incident_id="INC-001",
        title="Volume Drop Incident",
        pipeline_name="orders_ingestion",
        run_id="run_001",
        severity=Severity.CRITICAL.value,
        evidence_items=[volume_ev],
    )
    candidate = CandidateHypothesis(
        hypothesis_id="HYP-002",
        title="Pipeline Extraction or Filtering Logic Dropped Records",
        description="Internal filter logic discarded records",
        category="pipeline_logic",
        evidence_ids=["EVD-001"],
    )

    evaluated = evaluate_hypothesis(candidate, incident)
    assert evaluated.status == HypothesisStatus.INSUFFICIENT_EVIDENCE.value
    assert "cannot prove internal extraction or filtering logic" in evaluated.explanation
    assert "Step-level SQL / Spark execution plan and filter discard metrics" in evaluated.missing_evidence


def test_volume_drop_alone_does_not_claim_upstream_source_supported():
    """
    Requirement 2 & 3:
    Similarly, a local volume drop (6.2M vs 10M) does NOT prove the upstream source
    under-delivered records without direct upstream telemetry.
    """
    volume_ev = Evidence(
        evidence_id="EVD-001",
        source="volume_detector",
        description="Volume dropped",
        severity="CRITICAL",
        observed_value=6200000,
        threshold=10000000,
    )
    incident = Incident(
        incident_id="INC-001",
        title="Volume Drop Incident",
        pipeline_name="orders_ingestion",
        run_id="run_001",
        severity=Severity.CRITICAL.value,
        evidence_items=[volume_ev],
    )
    candidate = CandidateHypothesis(
        hypothesis_id="HYP-001",
        title="Upstream Source Under-Delivered Records",
        description="Source system under-delivered",
        category="upstream_source",
        evidence_ids=["EVD-001"],
        dependency_path=["source_db", "orders_ingestion"],
    )

    evaluated = evaluate_hypothesis(candidate, incident)
    assert evaluated.status == HypothesisStatus.INSUFFICIENT_EVIDENCE.value
    assert "cannot prove an upstream source under-delivered" in evaluated.explanation
    assert "Upstream source database row count / CDC audit log" in evaluated.missing_evidence


def test_pipeline_logic_supported_when_direct_filter_evidence_present():
    """
    Requirement 2:
    SUPPORTED is returned when direct evidence specifically substantiates the causal claim
    (e.g., telemetry showing records discarded by a filter step).
    """
    filter_ev = Evidence(
        evidence_id="EVD-010",
        source="pipeline_filter_check",
        description="Query filter step discarded 3,800,000 records",
        severity="HIGH",
        observed_value=3800000,
        threshold=0,
        details={"filter_discard_count": 3800000},
    )
    incident = Incident(
        incident_id="INC-010",
        title="Filter Discard Incident",
        pipeline_name="orders_ingestion",
        run_id="run_010",
        severity=Severity.HIGH.value,
        evidence_items=[filter_ev],
    )
    candidate = CandidateHypothesis(
        hypothesis_id="HYP-010",
        title="Pipeline Extraction or Filtering Logic Dropped Records",
        description="Filter discarded records",
        category="pipeline_logic",
        evidence_ids=["EVD-010"],
    )

    evaluated = evaluate_hypothesis(candidate, incident)
    assert evaluated.status == HypothesisStatus.SUPPORTED.value
    assert "Directly supported by internal pipeline execution telemetry" in evaluated.explanation
    assert evaluated.missing_evidence == []


def test_upstream_source_supported_when_direct_upstream_telemetry_present():
    """
    Requirement 2:
    Direct upstream telemetry showing under-delivery specifically supports the upstream source claim.
    """
    upstream_ev = Evidence(
        evidence_id="EVD-020",
        source="upstream_source_db",
        description="Source DB emitted only 6,200,000 records",
        severity="HIGH",
        observed_value=6200000,
        threshold=10000000,
    )
    incident = Incident(
        incident_id="INC-020",
        title="Source Under-delivery",
        pipeline_name="orders_ingestion",
        run_id="run_020",
        severity=Severity.HIGH.value,
        evidence_items=[upstream_ev],
    )
    candidate = CandidateHypothesis(
        hypothesis_id="HYP-020",
        title="Upstream Source Under-Delivered Records",
        description="Source DB delivered fewer records",
        category="upstream_source",
        evidence_ids=["EVD-020"],
    )

    evaluated = evaluate_hypothesis(candidate, incident)
    assert evaluated.status == HypothesisStatus.SUPPORTED.value
    assert "Directly supported by upstream source telemetry" in evaluated.explanation


def test_zero_duplicate_rows_does_not_contradict_upstream_volume_hypothesis():
    """
    Requirement 4:
    Zero duplicate rows does NOT contradict a hypothesis about an upstream source
    under-delivering records. Irrelevant evidence results in INSUFFICIENT_EVIDENCE.
    """
    zero_dup_ev = Evidence(
        evidence_id="EVD-003",
        source="duplicate_key_check",
        description="Zero duplicate records found",
        severity="INFO",
        observed_value=0,
        threshold=0,
    )
    incident = Incident(
        incident_id="INC-003",
        title="Check Incident",
        pipeline_name="orders_ingestion",
        run_id="run_003",
        severity=Severity.LOW.value,
        evidence_items=[zero_dup_ev],
    )
    # Testing an upstream_source hypothesis against a duplicate key check
    upstream_hyp = CandidateHypothesis(
        hypothesis_id="HYP-001",
        title="Upstream Source Under-Delivered Records",
        description="Source delivered fewer records",
        category="upstream_source",
        evidence_ids=["EVD-003"],
    )

    evaluated = evaluate_hypothesis(upstream_hyp, incident)
    # Must NOT be CONTRADICTED! It is irrelevant, so INSUFFICIENT_EVIDENCE
    assert evaluated.status == HypothesisStatus.INSUFFICIENT_EVIDENCE.value
    assert "irrelevant" in evaluated.explanation.lower()


def test_contradicted_only_when_relevant_evidence_refutes_hypothesis():
    """
    Requirement 4 & 5:
    CONTRADICTED is returned only when relevant evidence genuinely refutes the specific hypothesis.
    Zero duplicate keys genuinely refutes a duplicate key hypothesis.
    """
    zero_dup_ev = Evidence(
        evidence_id="EVD-003",
        source="duplicate_key_check",
        description="Zero duplicate records found",
        severity="INFO",
        observed_value=0,
        threshold=0,
    )
    incident = Incident(
        incident_id="INC-003",
        title="Quality check",
        pipeline_name="cleaning_pipeline",
        run_id="run-3",
        severity=Severity.INFO.value,
        evidence_items=[zero_dup_ev],
    )
    dup_hyp = CandidateHypothesis(
        hypothesis_id="HYP-003",
        title="Duplicate Keys Introduced",
        description="Non-idempotent retry introduced duplicates",
        category="data_quality",
        evidence_ids=["EVD-003"],
    )

    evaluated = evaluate_hypothesis(dup_hyp, incident)
    assert evaluated.status == HypothesisStatus.CONTRADICTED.value
    assert "zero duplicate keys found" in evaluated.explanation
    assert evaluated.missing_evidence == []


def test_volume_check_showing_no_drop_contradicts_volume_drop_hypothesis():
    """
    Requirement 4:
    A volume check showing actual >= expected genuinely refutes a volume drop hypothesis.
    """
    vol_ok_ev = Evidence(
        evidence_id="EVD-005",
        source="volume_detector",
        description="Actual records 10,000 matches expected 10,000",
        severity="INFO",
        observed_value=10000,
        threshold=10000,
    )
    incident = Incident(
        incident_id="INC-005",
        title="Normal Run",
        pipeline_name="orders_ingestion",
        run_id="run-5",
        severity=Severity.INFO.value,
        evidence_items=[vol_ok_ev],
    )
    vol_hyp = CandidateHypothesis(
        hypothesis_id="HYP-005",
        title="Pipeline Extraction or Filtering Logic Dropped Records",
        description="Filter dropped records",
        category="pipeline_logic",
        evidence_ids=["EVD-005"],
    )

    evaluated = evaluate_hypothesis(vol_hyp, incident)
    assert evaluated.status == HypothesisStatus.CONTRADICTED.value
    assert "met or exceeded expected count" in evaluated.explanation
