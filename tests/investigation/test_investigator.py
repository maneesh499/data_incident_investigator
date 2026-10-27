"""
Integration tests for the primary investigate_incident entry point.
"""

from pathlib import Path
from incident_investigator.dependency.loader import load_dependency_graph_from_json
from incident_investigator.detection.volume import PipelineRun, detect_volume_anomaly
from incident_investigator.detection.quality import check_duplicate_keys
from incident_investigator.incident.builder import build_incident_from_findings
from incident_investigator.investigation.investigator import investigate_incident
from incident_investigator.investigation.models import InvestigationResult


def test_end_to_end_investigation_with_real_findings():
    # 1. Load dependency graph from fixture
    graph = load_dependency_graph_from_json(Path("data/fixtures/pipeline_dependencies.json"))

    # 2. Simulate pipeline execution run with 38% volume drop
    run = PipelineRun(
        pipeline_name="orders_ingestion",
        run_id="run_001",
        status="SUCCESS",
        actual_record_count=6200000,
        expected_record_count=10000000,
    )
    vol_result = detect_volume_anomaly(run)
    assert vol_result.is_anomaly is True

    # 3. Build standardized incident using Feature C builder
    incident = build_incident_from_findings(run=run, volume_result=vol_result)
    assert incident is not None
    assert incident.root_cause is None  # Must NOT be set yet

    # 4. Investigate incident using Feature D investigator
    result = investigate_incident(incident, graph)

    assert isinstance(result, InvestigationResult)
    assert result.incident_id == "INC-orders_ingestion-run_001"
    assert result.investigated_asset_id == "orders_ingestion"

    # Upstream tracing: source_orders_db is upstream
    upstream_ids = [a.asset_id for a in result.upstream_assets]
    assert "source_orders_db" in upstream_ids

    # Downstream impact tracing: all downstream assets identified
    affected_ids = [a.asset_id for a in result.affected_assets]
    assert "bronze_orders" in affected_ids
    assert "silver_orders" in affected_ids
    assert "gold_daily_revenue" in affected_ids
    assert "executive_sales_dashboard" in affected_ids

    # Hypotheses evaluated: With only aggregate volume drop, neither upstream source nor pipeline filter
    # is falsely claimed as SUPPORTED. Both evaluate to INSUFFICIENT_EVIDENCE pending deeper telemetry.
    assert len(result.hypotheses) == 2
    for h in result.hypotheses:
        assert h.status == "INSUFFICIENT_EVIDENCE"

    # Integrity rules: Root cause is strictly NOT confirmed without external proof
    assert result.root_cause_confirmed is False
    assert incident.root_cause is None  # Original incident object remains unpolluted

    # Gaps recorded
    assert len(result.evidence_gaps) > 0
    assert any("Upstream source database" in g for g in result.evidence_gaps)
    assert any("Step-level SQL / Spark execution plan" in g for g in result.evidence_gaps)

    # Serialization test
    res_dict = result.to_dict()
    assert res_dict["incident_id"] == incident.incident_id
    assert res_dict["root_cause_confirmed"] is False
    assert len(res_dict["affected_assets"]) == len(result.affected_assets)


def test_investigation_with_direct_quality_evidence_supported():
    """When direct evidence exists for a check (e.g. duplicate keys), that hypothesis is SUPPORTED."""
    graph = load_dependency_graph_from_json(Path("data/fixtures/pipeline_dependencies.json"))

    run = PipelineRun(
        pipeline_name="orders_cleaning_pipeline",
        run_id="run_002",
        status="SUCCESS",
        actual_record_count=1000,
        expected_record_count=1000,
    )
    dup_records = [
        {"order_id": "ord_1", "item_id": "item_A"},
        {"order_id": "ord_1", "item_id": "item_A"},  # duplicate
    ]
    dup_result = check_duplicate_keys(dup_records, primary_key_columns=["order_id", "item_id"])
    assert dup_result.passed is False

    incident = build_incident_from_findings(run=run, quality_results=[dup_result])
    assert incident is not None

    result = investigate_incident(incident, graph)
    assert len(result.hypotheses) == 1
    assert result.hypotheses[0].status == "SUPPORTED"
    assert "duplicate primary key" in result.hypotheses[0].explanation


def test_investigation_without_dependency_graph():
    run = PipelineRun(
        pipeline_name="unmapped_job",
        run_id="run_999",
        status="SUCCESS",
        actual_record_count=50,
        expected_record_count=100,
    )
    vol = detect_volume_anomaly(run)
    incident = build_incident_from_findings(run=run, volume_result=vol)
    assert incident is not None

    # Call investigate_incident with graph = None
    result = investigate_incident(incident, dependency_graph=None)

    assert result.upstream_assets == []
    assert result.downstream_assets == []
    assert result.affected_assets == []
    assert any("Dependency graph was not provided" in gap for gap in result.evidence_gaps)
    assert result.root_cause_confirmed is False
