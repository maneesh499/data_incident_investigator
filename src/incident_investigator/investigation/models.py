"""
Data models for root-cause hypothesis generation, transparent evaluation, and investigation results.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from incident_investigator.dependency.models import Asset
from incident_investigator.incident.models import Incident


class HypothesisStatus(str, Enum):
    """
    Evaluation status of a candidate root-cause hypothesis based strictly on verified evidence.
    """
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass
class CandidateHypothesis:
    """
    Represents a plausible explanation generated from symptoms, evidence, and lineage.
    Note: A candidate hypothesis is an exploratory thesis, NEVER an assumed root cause.
    """
    hypothesis_id: str
    title: str
    description: str
    category: str  # "upstream_source", "data_quality", "freshness_sla", "pipeline_logic"
    evidence_ids: List[str] = field(default_factory=list)
    dependency_path: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "evidence_ids": list(self.evidence_ids),
            "dependency_path": list(self.dependency_path) if self.dependency_path else None,
        }


@dataclass
class EvaluatedHypothesis:
    """
    Outcome of evaluating a candidate hypothesis against the actual evidence set.
    """
    hypothesis: CandidateHypothesis
    status: str
    explanation: str
    missing_evidence: List[str] = field(default_factory=list)

    @property
    def hypothesis_id(self) -> str:
        return self.hypothesis.hypothesis_id

    @property
    def title(self) -> str:
        return self.hypothesis.title

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis": self.hypothesis.to_dict(),
            "status": self.status,
            "explanation": self.explanation,
            "missing_evidence": list(self.missing_evidence),
        }


@dataclass
class InvestigationResult:
    """
    Comprehensive result of an incident investigation connecting lineage, evidence, and hypotheses.
    In accordance with investigation rules, root_cause_confirmed is strictly False unless
    conclusive external proof is provided.
    """
    incident_id: str
    incident: Incident
    investigated_asset_id: str
    upstream_assets: List[Asset] = field(default_factory=list)
    downstream_assets: List[Asset] = field(default_factory=list)
    affected_assets: List[Asset] = field(default_factory=list)
    hypotheses: List[EvaluatedHypothesis] = field(default_factory=list)
    evidence_gaps: List[str] = field(default_factory=list)
    root_cause_confirmed: bool = False
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "investigated_asset_id": self.investigated_asset_id,
            "upstream_assets": [a.to_dict() for a in self.upstream_assets],
            "downstream_assets": [a.to_dict() for a in self.downstream_assets],
            "affected_assets": [a.to_dict() for a in self.affected_assets],
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "evidence_gaps": list(self.evidence_gaps),
            "root_cause_confirmed": self.root_cause_confirmed,
            "summary": self.summary,
        }
