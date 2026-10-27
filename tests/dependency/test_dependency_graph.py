"""
Unit tests for DependencyGraph operations: lookups, multi-level tracing, impact analysis, and cycle detection.
"""

import pytest
from incident_investigator.dependency.models import (
    Asset,
    AssetNotFoundError,
    AssetType,
    CyclicDependencyError,
    DuplicateAssetError,
    InvalidDependencyError,
)
from incident_investigator.dependency.graph import DependencyGraph


@pytest.fixture
def sample_graph() -> DependencyGraph:
    """
    Creates a sample linear and branching DAG:
    source_db -> ingestion -> bronze_layer -> silver_layer -> gold_mart -> dashboard
                                           -> audit_mart
    """
    g = DependencyGraph()
    assets = [
        Asset("source_db", "Source Database", AssetType.SOURCE_TABLE.value),
        Asset("ingestion", "Ingestion Pipeline", AssetType.INGESTION_PIPELINE.value),
        Asset("bronze_layer", "Bronze Storage", AssetType.STORAGE_CONTAINER.value),
        Asset("silver_layer", "Silver Delta Table", AssetType.TABLE.value),
        Asset("gold_mart", "Gold Sales Mart", AssetType.DATA_MART.value),
        Asset("audit_mart", "Audit Log Mart", AssetType.DATA_MART.value),
        Asset("dashboard", "Sales BI Dashboard", AssetType.DASHBOARD.value),
    ]
    for a in assets:
        g.add_asset(a)

    g.add_dependency("source_db", "ingestion")
    g.add_dependency("ingestion", "bronze_layer")
    g.add_dependency("bronze_layer", "silver_layer")
    g.add_dependency("silver_layer", "gold_mart")
    g.add_dependency("silver_layer", "audit_mart")
    g.add_dependency("gold_mart", "dashboard")
    return g


def test_duplicate_asset_registration_raises_error():
    g = DependencyGraph()
    g.add_asset(Asset("a1", "Asset 1", "table"))
    with pytest.raises(DuplicateAssetError, match="already registered"):
        g.add_asset(Asset("a1", "Asset 1 duplicate", "table"))


def test_invalid_dependency_references_raise_error():
    g = DependencyGraph()
    g.add_asset(Asset("a1", "Asset 1", "table"))

    with pytest.raises(InvalidDependencyError, match="upstream asset 'unknown' does not exist"):
        g.add_dependency("unknown", "a1")

    with pytest.raises(InvalidDependencyError, match="downstream asset 'unknown' does not exist"):
        g.add_dependency("a1", "unknown")

    with pytest.raises(InvalidDependencyError, match="Self-dependency not allowed"):
        g.add_dependency("a1", "a1")


def test_direct_upstream_and_downstream_lookups(sample_graph: DependencyGraph):
    # bronze_layer direct upstream is ingestion
    upstreams = sample_graph.get_direct_upstream("bronze_layer")
    assert len(upstreams) == 1
    assert upstreams[0].asset_id == "ingestion"

    # silver_layer direct downstreams are gold_mart and audit_mart
    downstreams = sample_graph.get_direct_downstream("silver_layer")
    assert [d.asset_id for d in downstreams] == ["audit_mart", "gold_mart"]


def test_transitive_upstream_tracing(sample_graph: DependencyGraph):
    # dashboard's ancestors: gold_mart, silver_layer, bronze_layer, ingestion, source_db
    ancestors = sample_graph.get_transitive_upstream("dashboard")
    ancestor_ids = [a.asset_id for a in ancestors]

    assert "gold_mart" in ancestor_ids
    assert "silver_layer" in ancestor_ids
    assert "bronze_layer" in ancestor_ids
    assert "ingestion" in ancestor_ids
    assert "source_db" in ancestor_ids
    assert len(ancestor_ids) == 5


def test_transitive_downstream_and_impact_analysis(sample_graph: DependencyGraph):
    # If ingestion pipeline fails, all downstream assets are affected
    affected = sample_graph.get_affected_assets("ingestion")
    affected_ids = [a.asset_id for a in affected]

    assert affected_ids == [
        "bronze_layer",
        "silver_layer",
        "audit_mart",
        "gold_mart",
        "dashboard",
    ]


def test_find_dependency_path(sample_graph: DependencyGraph):
    path = sample_graph.find_dependency_path("source_db", "dashboard")
    assert path == ["source_db", "ingestion", "bronze_layer", "silver_layer", "gold_mart", "dashboard"]

    # No reverse path
    assert sample_graph.find_dependency_path("dashboard", "source_db") is None


def test_cycle_detection_in_simple_loop():
    g = DependencyGraph()
    g.add_asset(Asset("node_a", "Node A", "table"))
    g.add_asset(Asset("node_b", "Node B", "table"))

    g.add_dependency("node_a", "node_b")
    g.add_dependency("node_b", "node_a")  # Creates cycle A -> B -> A

    with pytest.raises(CyclicDependencyError, match="Cycle detected in dependency graph: node_a -> node_b -> node_a"):
        g.validate_acyclic()


def test_cycle_detection_in_multi_node_loop():
    g = DependencyGraph()
    g.add_asset(Asset("n1", "N1", "table"))
    g.add_asset(Asset("n2", "N2", "table"))
    g.add_asset(Asset("n3", "N3", "table"))

    g.add_dependency("n1", "n2")
    g.add_dependency("n2", "n3")
    g.add_dependency("n3", "n1")  # Creates cycle n1 -> n2 -> n3 -> n1

    with pytest.raises(CyclicDependencyError, match="Cycle detected in dependency graph"):
        g.validate_acyclic()


def test_lookup_missing_asset_raises_error(sample_graph: DependencyGraph):
    with pytest.raises(AssetNotFoundError, match="Asset 'non_existent' not found"):
        sample_graph.get_direct_upstream("non_existent")

    with pytest.raises(AssetNotFoundError, match="Asset 'non_existent' not found"):
        sample_graph.get_direct_downstream("non_existent")
