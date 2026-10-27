"""
Data models for incidents, evidence items, and statuses.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class IncidentStatus(str, Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


@dataclass
class Evidence:
    """Represents a specific, verifiable piece of evidence collected during checks."""
    evidence_id: str
    source: str
    description: str
    severity: str
    observed_value: Any
    threshold: Any
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source": self.source,
            "description": self.description,
            "severity": self.severity,
            "observed_value": self.observed_value,
            "threshold": self.threshold,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
        }


@dataclass
class Incident:
    """
    Standardized incident record capturing anomalies, evidence, and state.
    Notice: root_cause is strictly Optional to prevent claiming causes without proof.
    """
    incident_id: str
    title: str
    pipeline_name: str
    run_id: str
    severity: str
    status: str = IncidentStatus.OPEN.value
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    symptoms: List[str] = field(default_factory=list)
    evidence_items: List[Evidence] = field(default_factory=list)
    root_cause: Optional[str] = None
    affected_assets: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "title": self.title,
            "pipeline_name": self.pipeline_name,
            "run_id": self.run_id,
            "severity": self.severity,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "symptoms": list(self.symptoms),
            "evidence_items": [ev.to_dict() for ev in self.evidence_items],
            "root_cause": self.root_cause,
            "affected_assets": list(self.affected_assets),
        }
