"""
Unit tests for deterministic candidate hypothesis generation.
"""

from incident_investigator.dependency.models import Asset, AssetType
from incident_investigator.dependency.graph import DependencyGraph
from incident_investigator.incident.models import Evidence, Incident, IncidentStatus, Severity
from incident_investigator.investigation.hypotheses import generate_candidate_hypotheses


def test_generate_hypotheses_from_volume_drop():
    evidence = Evidence(
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
        evidence_items=[evidence],
    )

    g = DependencyGraph()
    g.add_asset(Asset("source_orders_db", "Source DB", AssetType.SOURCE_TABLE.value))
    g.add_asset(Asset("orders_ingestion", "Ingestion", AssetType.INGESTION_PIPELINE.value))
    g.add_dependency("source_orders_db", "orders_ingestion")

    hypotheses = generate_candidate_hypotheses(incident, g)
    assert len(hypotheses) == 2

    # Hypothesis 1: Upstream under-delivered
    h1 = hypotheses[0]
    assert h1.hypothesis_id == "HYP-001"
    assert h1.category == "upstream_source"
    assert h1.evidence_ids == ["EVD-001"]
    assert h1.dependency_path == ["source_orders_db", "orders_ingestion"]

    # Hypothesis 2: Internal pipeline filter/drop
    h2 = hypotheses[1]
    assert h2.hypothesis_id == "HYP-002"
    assert h2.category == "pipeline_logic"
    assert h2.evidence_ids == ["EVD-001"]
    assert h2.dependency_path == ["orders_ingestion"]


def test_generate_hypotheses_from_quality_violations():
    ev_dup = Evidence(
        evidence_id="EVD-001",
        source="duplicate_key_check",
        description="Found 2 duplicate rows",
        severity="CRITICAL",
        observed_value=2,
        threshold=0,
    )
    ev_null = Evidence(
        evidence_id="EVD-002",
        source="null_column_check",
        description="Null rate 25%",
        severity="HIGH",
        observed_value=25.0,
        threshold=5.0,
    )
    incident = Incident(
        incident_id="INC-002",
        title="Quality Violations",
        pipeline_name="orders_cleaning",
        run_id="run_002",
        severity=Severity.CRITICAL.value,
        evidence_items=[ev_dup, ev_null],
    )

    hypotheses = generate_candidate_hypotheses(incident)
    assert len(hypotheses) == 2
    assert hypotheses[0].category == "data_quality"
    assert hypotheses[0].evidence_ids == ["EVD-001"]
    assert "duplicate" in hypotheses[0].title.lower()

    assert hypotheses[1].category == "data_quality"
    assert hypotheses[1].evidence_ids == ["EVD-002"]
    assert "null" in hypotheses[1].title.lower()


def test_generate_hypotheses_when_no_evidence_available():
    incident = Incident(
        incident_id="INC-EMPTY",
        title="Empty Incident",
        pipeline_name="mystery_pipeline",
        run_id="run_000",
        severity=Severity.LOW.value,
        evidence_items=[],
    )

    hypotheses = generate_candidate_hypotheses(incident)
    assert len(hypotheses) == 1
    assert hypotheses[0].category == "insufficient_evidence"
    assert hypotheses[0].evidence_ids == []
    assert "Insufficient" in hypotheses[0].title
