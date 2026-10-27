"""
Primary entry point for incident investigation, impact analysis, and hypothesis evaluation.
"""

from typing import List, Optional
from incident_investigator.dependency.graph import DependencyGraph
from incident_investigator.dependency.models import Asset
from incident_investigator.incident.models import Incident
from incident_investigator.investigation.evaluator import evaluate_hypotheses
from incident_investigator.investigation.hypotheses import generate_candidate_hypotheses
from incident_investigator.investigation.models import InvestigationResult


def investigate_incident(
    incident: Incident,
    dependency_graph: Optional[DependencyGraph] = None,
) -> InvestigationResult:
    """
    Investigates an incident by tracing its upstream/downstream lineage, identifying
    potentially affected assets, generating candidate hypotheses, and evaluating them
    strictly against verified evidence.
    
    In accordance with investigation safety rules:
    - Does NOT modify the incident's root_cause attribute.
    - Explicitly sets root_cause_confirmed = False.
    - Documents evidence gaps and limitations.
    
    Args:
        incident: The Incident object to investigate.
        dependency_graph: Optional DependencyGraph representing data platform lineage.
        
    Returns:
        InvestigationResult: Structured outcome containing lineage, evaluated hypotheses,
        affected assets, and evidence gaps.
    """
    asset_id = incident.pipeline_name
    upstream_assets: List[Asset] = []
    downstream_assets: List[Asset] = []
    affected_assets: List[Asset] = []
    evidence_gaps: List[str] = []

    # 1. Lineage and impact tracing
    if dependency_graph is None:
        evidence_gaps.append(
            "Dependency graph was not provided; lineage and impact analysis could not be conducted."
        )
    elif not dependency_graph.has_asset(asset_id):
        evidence_gaps.append(
            f"Asset '{asset_id}' is not registered in the provided dependency graph."
        )
    else:
        upstream_assets = dependency_graph.get_transitive_upstream(asset_id)
        downstream_assets = dependency_graph.get_transitive_downstream(asset_id)
        # All downstream assets in lineage are potentially affected
        affected_assets = dependency_graph.get_affected_assets(asset_id)

    # 2. Check for empty evidence
    if not incident.evidence_items:
        evidence_gaps.append("Incident contains no structured evidence items to evaluate.")

    # 3. Generate candidate hypotheses
    candidate_hypotheses = generate_candidate_hypotheses(incident, dependency_graph)

    # 4. Evaluate hypotheses against evidence
    evaluated_hypotheses = evaluate_hypotheses(candidate_hypotheses, incident, dependency_graph)

    # 5. Collect specific missing evidence items from evaluated hypotheses
    for hyp in evaluated_hypotheses:
        for missing in hyp.missing_evidence:
            if missing not in evidence_gaps:
                evidence_gaps.append(missing)

    # 6. Generate summary narrative
    supported_count = sum(1 for h in evaluated_hypotheses if h.status == "SUPPORTED")
    contradicted_count = sum(1 for h in evaluated_hypotheses if h.status == "CONTRADICTED")
    insufficient_count = sum(1 for h in evaluated_hypotheses if h.status == "INSUFFICIENT_EVIDENCE")

    summary = (
        f"Investigated incident {incident.incident_id} on pipeline '{asset_id}'. "
        f"Identified {len(upstream_assets)} upstream dependencies and {len(affected_assets)} "
        f"potentially affected downstream assets. Evaluated {len(evaluated_hypotheses)} candidate "
        f"hypotheses ({supported_count} supported, {contradicted_count} contradicted, "
        f"{insufficient_count} with insufficient evidence). Root cause remains UNCONFIRMED pending "
        f"additional upstream telemetry."
    )

    return InvestigationResult(
        incident_id=incident.incident_id,
        incident=incident,
        investigated_asset_id=asset_id,
        upstream_assets=upstream_assets,
        downstream_assets=downstream_assets,
        affected_assets=affected_assets,
        hypotheses=evaluated_hypotheses,
        evidence_gaps=evidence_gaps,
        root_cause_confirmed=False,  # Unconfirmed without external definitive proof
        summary=summary,
    )
