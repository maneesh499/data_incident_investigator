"""
Data models and exceptions for pipeline assets and dependency relationships.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict


class AssetType(str, Enum):
    """Categorizes the role of an asset in the data platform."""
    SOURCE_TABLE = "source_table"
    INGESTION_PIPELINE = "ingestion_pipeline"
    TRANSFORMATION_PIPELINE = "transformation_pipeline"
    STORAGE_CONTAINER = "storage_container"
    TABLE = "table"
    DATA_MART = "data_mart"
    DASHBOARD = "dashboard"
    API_SERVICE = "api_service"


class DependencyError(Exception):
    """Base exception for dependency graph operations."""
    pass


class AssetNotFoundError(DependencyError):
    """Raised when an operation references an unregistered asset ID."""
    pass


class DuplicateAssetError(DependencyError):
    """Raised when attempting to register an asset with an already existing ID."""
    pass


class InvalidDependencyError(DependencyError):
    """Raised when a dependency edge is malformed or references non-existent assets."""
    pass


class CyclicDependencyError(DependencyError):
    """Raised when a cyclic dependency (e.g., A -> B -> A) is detected in the graph."""
    pass


@dataclass(frozen=True)
class Asset:
    """
    Represents an entity in the data ecosystem (e.g. source table, pipeline, mart).
    
    Attributes:
        asset_id: Unique, stable identifier (e.g. 'source_orders_db', 'orders_ingestion').
        name: Human-readable display name.
        asset_type: Category of the asset (from AssetType or string).
        metadata: Optional dictionary with operational attributes (owner, schedule, format).
    """
    asset_id: str
    name: str
    asset_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "name": self.name,
            "asset_type": self.asset_type,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DependencyEdge:
    """
    Represents a directed data dependency between two assets.
    
    Direction convention:
        Data flows from upstream_asset_id -> downstream_asset_id.
        Therefore, downstream_asset_id DEPENDS ON upstream_asset_id.
        If upstream_asset_id fails or suffers data quality issues,
        downstream_asset_id is potentially impacted.
    """
    upstream_asset_id: str
    downstream_asset_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
