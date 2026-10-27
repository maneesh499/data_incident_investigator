"""
Loads and validates pipeline dependency metadata from JSON files or Python dictionaries.
"""

import json
from pathlib import Path
from typing import Any, Dict, Union

from incident_investigator.dependency.graph import DependencyGraph
from incident_investigator.dependency.models import (
    Asset,
    InvalidDependencyError,
)


def load_dependency_graph_from_dict(data: Dict[str, Any]) -> DependencyGraph:
    """
    Parses a dictionary into a validated DependencyGraph.
    
    Expected format:
    {
        "assets": [
            {"asset_id": "...", "name": "...", "asset_type": "...", "metadata": {...}}
        ],
        "dependencies": [
            {"upstream": "...", "downstream": "...", "metadata": {...}}
        ]
    }
    """
    if not isinstance(data, dict):
        raise ValueError("Dependency data must be a dictionary.")

    if "assets" not in data or not isinstance(data["assets"], list):
        raise ValueError("Missing or invalid 'assets' array in dependency data.")

    if "dependencies" not in data or not isinstance(data["dependencies"], list):
        raise ValueError("Missing or invalid 'dependencies' array in dependency data.")

    graph = DependencyGraph()

    # 1. Parse and register all assets
    for raw_asset in data["assets"]:
        if not isinstance(raw_asset, dict):
            raise ValueError(f"Each asset entry must be a dictionary, got: {type(raw_asset)}")

        for required_key in ("asset_id", "name", "asset_type"):
            if required_key not in raw_asset or not raw_asset[required_key]:
                raise ValueError(f"Asset entry missing required field '{required_key}': {raw_asset}")

        asset = Asset(
            asset_id=str(raw_asset["asset_id"]),
            name=str(raw_asset["name"]),
            asset_type=str(raw_asset["asset_type"]),
            metadata=dict(raw_asset.get("metadata", {})),
        )
        graph.add_asset(asset)

    # 2. Parse and register all dependencies
    for raw_dep in data["dependencies"]:
        if not isinstance(raw_dep, dict):
            raise ValueError(f"Each dependency entry must be a dictionary, got: {type(raw_dep)}")

        # Support both 'upstream'/'downstream' and 'from'/'to' keys
        upstream_id = raw_dep.get("upstream") or raw_dep.get("from")
        downstream_id = raw_dep.get("downstream") or raw_dep.get("to")

        if not upstream_id or not downstream_id:
            raise InvalidDependencyError(
                f"Dependency entry must specify both upstream and downstream assets: {raw_dep}"
            )

        graph.add_dependency(
            upstream_asset_id=str(upstream_id),
            downstream_asset_id=str(downstream_id),
            metadata=raw_dep.get("metadata"),
        )

    # 3. Validate that the loaded graph has no cycles
    graph.validate_acyclic()

    return graph


def load_dependency_graph_from_json(file_path: Union[str, Path]) -> DependencyGraph:
    """
    Reads a JSON file from disk and parses it into a DependencyGraph.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Dependency file not found: {file_path}")

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON format in file {file_path}: {exc}") from exc

    return load_dependency_graph_from_dict(data)
