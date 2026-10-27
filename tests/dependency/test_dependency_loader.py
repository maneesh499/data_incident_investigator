"""
Unit tests for loading dependency graphs from JSON files and Python dictionaries.
"""

from pathlib import Path
import pytest
from incident_investigator.dependency.loader import (
    load_dependency_graph_from_dict,
    load_dependency_graph_from_json,
)
from incident_investigator.dependency.models import CyclicDependencyError, InvalidDependencyError


def test_load_dependency_graph_from_json_fixture():
    fixture_path = Path("data/fixtures/pipeline_dependencies.json")
    graph = load_dependency_graph_from_json(fixture_path)

    assert graph.has_asset("source_orders_db")
    assert graph.has_asset("orders_ingestion")
    assert graph.has_asset("gold_daily_revenue")
    assert len(graph.get_all_assets()) == 8

    # Verify downstream path from orders_ingestion
    affected = graph.get_affected_assets("orders_ingestion")
    affected_ids = [a.asset_id for a in affected]
    assert "bronze_orders" in affected_ids
    assert "silver_orders" in affected_ids
    assert "executive_sales_dashboard" in affected_ids


def test_load_dependency_graph_from_dict_valid():
    data = {
        "assets": [
            {"asset_id": "raw_users", "name": "Raw Users", "asset_type": "source_table"},
            {"asset_id": "clean_users", "name": "Clean Users", "asset_type": "table"},
        ],
        "dependencies": [
            {"upstream": "raw_users", "downstream": "clean_users"}
        ],
    }
    graph = load_dependency_graph_from_dict(data)
    assert graph.has_asset("raw_users")
    assert graph.has_asset("clean_users")
    assert graph.get_direct_downstream("raw_users")[0].asset_id == "clean_users"


def test_load_missing_file_raises_error():
    with pytest.raises(FileNotFoundError, match="Dependency file not found"):
        load_dependency_graph_from_json("non_existent_file.json")


def test_load_malformed_json_raises_error(tmp_path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{ unquoted json: bad }")
    with pytest.raises(ValueError, match="Invalid JSON format"):
        load_dependency_graph_from_json(bad_file)


def test_load_missing_required_fields_raises_error():
    # Missing assets key
    with pytest.raises(ValueError, match="Missing or invalid 'assets' array"):
        load_dependency_graph_from_dict({"dependencies": []})

    # Missing dependencies key
    with pytest.raises(ValueError, match="Missing or invalid 'dependencies' array"):
        load_dependency_graph_from_dict({"assets": []})

    # Asset entry missing asset_id
    with pytest.raises(ValueError, match="Asset entry missing required field 'asset_id'"):
        load_dependency_graph_from_dict({
            "assets": [{"name": "No ID", "asset_type": "table"}],
            "dependencies": [],
        })


def test_load_graph_with_cycle_fails_validation():
    cyclic_data = {
        "assets": [
            {"asset_id": "p1", "name": "P1", "asset_type": "pipeline"},
            {"asset_id": "p2", "name": "P2", "asset_type": "pipeline"},
        ],
        "dependencies": [
            {"upstream": "p1", "downstream": "p2"},
            {"upstream": "p2", "downstream": "p1"},
        ],
    }
    with pytest.raises(CyclicDependencyError, match="Cycle detected"):
        load_dependency_graph_from_dict(cyclic_data)
