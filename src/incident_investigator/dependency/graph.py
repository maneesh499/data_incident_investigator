"""
In-memory directed dependency graph for data pipeline assets and impact tracing.
"""

from collections import deque
from typing import Dict, List, Optional, Set
from incident_investigator.dependency.models import (
    Asset,
    AssetNotFoundError,
    CyclicDependencyError,
    DependencyEdge,
    DuplicateAssetError,
    InvalidDependencyError,
)


class DependencyGraph:
    """
    Represents a directed acyclic graph (DAG) of data assets.
    
    Data flows in the direction:
        Upstream Asset (producer) -> Downstream Asset (consumer)
    """

    def __init__(self) -> None:
        self._assets: Dict[str, Asset] = {}
        # Maps asset_id -> set of direct downstream asset_ids (children)
        self._downstream_adj: Dict[str, Set[str]] = {}
        # Maps asset_id -> set of direct upstream asset_ids (parents)
        self._upstream_adj: Dict[str, Set[str]] = {}
        self._edges: List[DependencyEdge] = []

    def add_asset(self, asset: Asset) -> None:
        """Registers a new asset in the graph."""
        if asset.asset_id in self._assets:
            raise DuplicateAssetError(f"Asset with ID '{asset.asset_id}' is already registered.")
        
        self._assets[asset.asset_id] = asset
        self._downstream_adj[asset.asset_id] = set()
        self._upstream_adj[asset.asset_id] = set()

    def has_asset(self, asset_id: str) -> bool:
        """Returns True if the asset is registered in the graph."""
        return asset_id in self._assets

    def get_asset(self, asset_id: str) -> Asset:
        """Retrieves an asset by its ID; raises AssetNotFoundError if missing."""
        if asset_id not in self._assets:
            raise AssetNotFoundError(f"Asset '{asset_id}' not found in dependency graph.")
        return self._assets[asset_id]

    def get_all_assets(self) -> List[Asset]:
        """Returns all registered assets in deterministic ID order."""
        return [self._assets[aid] for aid in sorted(self._assets.keys())]

    def add_dependency(
        self,
        upstream_asset_id: str,
        downstream_asset_id: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Creates a directed dependency edge: upstream -> downstream.
        
        Raises:
            InvalidDependencyError: If an asset does not exist or if self-dependency is attempted.
        """
        if upstream_asset_id not in self._assets:
            raise InvalidDependencyError(
                f"Cannot create dependency: upstream asset '{upstream_asset_id}' does not exist."
            )
        if downstream_asset_id not in self._assets:
            raise InvalidDependencyError(
                f"Cannot create dependency: downstream asset '{downstream_asset_id}' does not exist."
            )
        if upstream_asset_id == downstream_asset_id:
            raise InvalidDependencyError(
                f"Self-dependency not allowed: '{upstream_asset_id}' cannot depend on itself."
            )

        self._downstream_adj[upstream_asset_id].add(downstream_asset_id)
        self._upstream_adj[downstream_asset_id].add(upstream_asset_id)
        self._edges.append(
            DependencyEdge(
                upstream_asset_id=upstream_asset_id,
                downstream_asset_id=downstream_asset_id,
                metadata=metadata or {},
            )
        )

    def get_direct_upstream(self, asset_id: str) -> List[Asset]:
        """Returns the direct parent assets that this asset depends upon."""
        self._ensure_asset_exists(asset_id)
        parent_ids = sorted(self._upstream_adj[asset_id])
        return [self._assets[pid] for pid in parent_ids]

    def get_direct_downstream(self, asset_id: str) -> List[Asset]:
        """Returns the direct child assets that depend upon this asset."""
        self._ensure_asset_exists(asset_id)
        child_ids = sorted(self._downstream_adj[asset_id])
        return [self._assets[cid] for cid in child_ids]

    def get_transitive_upstream(self, asset_id: str) -> List[Asset]:
        """
        Traverses all ancestors (direct and indirect) up to root sources.
        Returns assets in breadth-first order (closest upstream parents first).
        """
        self._ensure_asset_exists(asset_id)
        visited: Set[str] = set()
        queue: deque[str] = deque([asset_id])
        result: List[Asset] = []

        while queue:
            curr = queue.popleft()
            for parent_id in sorted(self._upstream_adj[curr]):
                if parent_id not in visited:
                    visited.add(parent_id)
                    result.append(self._assets[parent_id])
                    queue.append(parent_id)

        return result

    def get_transitive_downstream(self, asset_id: str) -> List[Asset]:
        """
        Traverses all descendants (direct and indirect) down to terminal consumers.
        Returns assets in breadth-first order (immediate downstream children first).
        """
        self._ensure_asset_exists(asset_id)
        visited: Set[str] = set()
        queue: deque[str] = deque([asset_id])
        result: List[Asset] = []

        while queue:
            curr = queue.popleft()
            for child_id in sorted(self._downstream_adj[curr]):
                if child_id not in visited:
                    visited.add(child_id)
                    result.append(self._assets[child_id])
                    queue.append(child_id)

        return result

    def get_affected_assets(self, impacted_asset_id: str) -> List[Asset]:
        """
        Identifies all downstream assets potentially affected if the specified asset fails or produces bad data.
        """
        return self.get_transitive_downstream(impacted_asset_id)

    def find_dependency_path(self, source_asset_id: str, target_asset_id: str) -> Optional[List[str]]:
        """
        Finds the shortest directed path of asset IDs from source_asset_id to target_asset_id.
        Returns None if no directed path exists.
        """
        self._ensure_asset_exists(source_asset_id)
        self._ensure_asset_exists(target_asset_id)

        if source_asset_id == target_asset_id:
            return [source_asset_id]

        queue: deque[List[str]] = deque([[source_asset_id]])
        visited: Set[str] = {source_asset_id}

        while queue:
            path = queue.popleft()
            last_node = path[-1]

            for neighbor in sorted(self._downstream_adj[last_node]):
                if neighbor == target_asset_id:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(path + [neighbor])

        return None

    def validate_acyclic(self) -> None:
        """
        Checks the entire graph for cycles using 3-color DFS.
        Raises CyclicDependencyError if any cycle is detected.
        """
        # 0 = UNVISITED, 1 = VISITING (currently in recursion stack), 2 = VISITED
        state: Dict[str, int] = {aid: 0 for aid in self._assets}
        parent_map: Dict[str, Optional[str]] = {aid: None for aid in self._assets}

        for start_node in sorted(self._assets.keys()):
            if state[start_node] == 0:
                self._dfs_cycle_check(start_node, state, parent_map, [start_node])

    def _dfs_cycle_check(
        self,
        node: str,
        state: Dict[str, int],
        parent_map: Dict[str, Optional[str]],
        current_path: List[str],
    ) -> None:
        state[node] = 1  # VISITING

        for child in sorted(self._downstream_adj[node]):
            if state[child] == 1:
                # Cycle found! Extract the cycle path
                cycle_start_idx = current_path.index(child)
                cycle_path = current_path[cycle_start_idx:] + [child]
                raise CyclicDependencyError(
                    f"Cycle detected in dependency graph: {' -> '.join(cycle_path)}"
                )
            elif state[child] == 0:
                parent_map[child] = node
                self._dfs_cycle_check(child, state, parent_map, current_path + [child])

        state[node] = 2  # VISITED

    def _ensure_asset_exists(self, asset_id: str) -> None:
        if asset_id not in self._assets:
            raise AssetNotFoundError(f"Asset '{asset_id}' not found in dependency graph.")
