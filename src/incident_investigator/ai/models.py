"""
Data models for AI-assisted investigation reporting, structured recommendations, and provider results.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RecommendedAction:
    """
    A concrete, safe operational recommendation for an on-call engineer.
    Contains read-only diagnostic suggestions; NEVER executes destructive remediation.
    """
    action_id: str
    priority: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    action_type: str  # "investigate_upstream", "inspect_pipeline_logs", "profile_data_quality", "notify_stakeholders"
    description: str
    target_asset: str
    suggested_query_or_check: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "priority": self.priority,
            "action_type": self.action_type,
            "description": self.description,
            "target_asset": self.target_asset,
            "suggested_query_or_check": self.suggested_query_or_check,
        }


@dataclass
class AIInvestigationReport:
    """
    Structured AI-generated investigation brief grounded in deterministic evidence.
    """
    incident_id: str
    executive_summary: str
    root_cause_status: str  # "UNCONFIRMED_PENDING_EVIDENCE" or "CONFIRMED"
    hypotheses_analysis: str
    cited_evidence_ids: List[str] = field(default_factory=list)
    confidence_score: float = 0.0  # 0.0 to 1.0
    recommended_actions: List[RecommendedAction] = field(default_factory=list)
    is_fallback: bool = False
    provider_used: str = "deterministic_fallback"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "executive_summary": self.executive_summary,
            "root_cause_status": self.root_cause_status,
            "hypotheses_analysis": self.hypotheses_analysis,
            "cited_evidence_ids": list(self.cited_evidence_ids),
            "confidence_score": self.confidence_score,
            "recommended_actions": [act.to_dict() for act in self.recommended_actions],
            "is_fallback": self.is_fallback,
            "provider_used": self.provider_used,
        }

    def to_markdown(self) -> str:
        """Renders an executive markdown brief for dashboards and runbooks."""
        lines = [
            f"# AI Incident Investigation Brief: `{self.incident_id}`",
            "",
            f"**Provider**: `{self.provider_used}` | **Fallback Mode**: `{self.is_fallback}` | **Confidence**: `{int(self.confidence_score * 100)}%`",
            f"**Root Cause Status**: `{self.root_cause_status}`",
            "",
            "## Executive Summary",
            self.executive_summary,
            "",
            "## Causal Hypotheses Assessment",
            self.hypotheses_analysis,
            "",
            f"**Cited Evidence IDs**: {', '.join(f'`{eid}`' for eid in self.cited_evidence_ids) if self.cited_evidence_ids else 'None'}",
            "",
            "## Recommended Operational Actions",
        ]
        if self.recommended_actions:
            lines.append("| Priority | Action ID | Target Asset | Action Summary | Diagnostic Command / Query |")
            lines.append("|---|---|---|---|---|")
            for a in self.recommended_actions:
                cmd = f"`{a.suggested_query_or_check}`" if a.suggested_query_or_check else "N/A"
                lines.append(f"| **{a.priority}** | {a.action_id} | `{a.target_asset}` | {a.description} | {cmd} |")
        else:
            lines.append("No immediate actions recommended.")
        lines.append("")
        return "\n".join(lines)
