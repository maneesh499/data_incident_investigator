"""
Generates deterministic candidate root-cause hypotheses from verified evidence and dependency lineage.
"""

from typing import List, Optional
from incident_investigator.dependency.graph import DependencyGraph
from incident_investigator.incident.models import Incident
from incident_investigator.investigation.models import CandidateHypothesis


def generate_candidate_hypotheses(
    incident: Incident,
    graph: Optional[DependencyGraph] = None,
) -> List[CandidateHypothesis]:
    """
    Extracts deterministic candidate explanations based strictly on the incident's evidence
    and graph topology. Does not invent evidence or assume confirmed causes.
    """
    hypotheses: List[CandidateHypothesis] = []

    # If the incident contains zero evidence, no valid hypothesis can be formulated
    if not incident.evidence_items:
        return [
            CandidateHypothesis(
                hypothesis_id="HYP-INSUFFICIENT-001",
                title="Insufficient Evidence for Hypothesis Formulation",
                description="No structured evidence items recorded in this incident. Cannot infer causal hypotheses.",
                category="insufficient_evidence",
                evidence_ids=[],
                dependency_path=None,
            )
        ]

    # Resolve primary upstream path if dependency graph is available
    upstream_path: Optional[List[str]] = None
    if graph and graph.has_asset(incident.pipeline_name):
        upstreams = graph.get_direct_upstream(incident.pipeline_name)
        if upstreams:
            primary_upstream = upstreams[0].asset_id
            upstream_path = graph.find_dependency_path(primary_upstream, incident.pipeline_name)

    hyp_counter = 1

    for ev in incident.evidence_items:
        if ev.source == "volume_detector":
            # Hypothesis 1: Upstream source under-delivered
            hypotheses.append(
                CandidateHypothesis(
                    hypothesis_id=f"HYP-{hyp_counter:03d}",
                    title="Upstream Source Under-Delivered Records",
                    description=(
                        f"Upstream source system may have delivered fewer records than expected, "
                        f"resulting in {ev.observed_value} records observed versus {ev.threshold} expected."
                    ),
                    category="upstream_source",
                    evidence_ids=[ev.evidence_id],
                    dependency_path=upstream_path,
                )
            )
            hyp_counter += 1

            # Hypothesis 2: Internal pipeline filtering/failure dropped records
            hypotheses.append(
                CandidateHypothesis(
                    hypothesis_id=f"HYP-{hyp_counter:03d}",
                    title="Pipeline Extraction or Filtering Logic Dropped Records",
                    description=(
                        f"Pipeline '{incident.pipeline_name}' may have encountered internal filter "
                        f"conditions, query timeouts, or partial ingestion failures during execution."
                    ),
                    category="pipeline_logic",
                    evidence_ids=[ev.evidence_id],
                    dependency_path=[incident.pipeline_name],
                )
            )
            hyp_counter += 1

        elif ev.source == "null_column_check":
            hypotheses.append(
                CandidateHypothesis(
                    hypothesis_id=f"HYP-{hyp_counter:03d}",
                    title="Null Value Violations from Source Mutation or Mapping Error",
                    description=(
                        f"Mandatory columns failed null-rate threshold ({ev.observed_value}% observed vs "
                        f"{ev.threshold}% allowed). Upstream data producer may have emitted null fields "
                        f"or column mapping failed."
                    ),
                    category="data_quality",
                    evidence_ids=[ev.evidence_id],
                    dependency_path=upstream_path,
                )
            )
            hyp_counter += 1

        elif ev.source == "duplicate_key_check":
            hypotheses.append(
                CandidateHypothesis(
                    hypothesis_id=f"HYP-{hyp_counter:03d}",
                    title="Non-Idempotent Pipeline Retry or Join Fan-Out Introduced Duplicates",
                    description=(
                        f"Observed {ev.observed_value} duplicate records on defined primary keys. "
                        f"Commonly caused by un-idempotent pipeline retries or relational join expansion."
                    ),
                    category="data_quality",
                    evidence_ids=[ev.evidence_id],
                    dependency_path=[incident.pipeline_name],
                )
            )
            hyp_counter += 1

        elif ev.source == "freshness_check":
            hypotheses.append(
                CandidateHypothesis(
                    hypothesis_id=f"HYP-{hyp_counter:03d}",
                    title="Upstream Extraction Delay or Scheduler Lag Breached SLA",
                    description=(
                        f"Data lag of {ev.observed_value} hours exceeded the SLA threshold of {ev.threshold} hours. "
                        f"Upstream batch completion delays or cron scheduler lag may have deferred pipeline trigger."
                    ),
                    category="freshness_sla",
                    evidence_ids=[ev.evidence_id],
                    dependency_path=upstream_path,
                )
            )
            hyp_counter += 1

        else:
            # Generic fallback for any other custom evidence source
            hypotheses.append(
                CandidateHypothesis(
                    hypothesis_id=f"HYP-{hyp_counter:03d}",
                    title=f"Anomaly in {ev.source.replace('_', ' ').title()}",
                    description=ev.description,
                    category="custom_check",
                    evidence_ids=[ev.evidence_id],
                    dependency_path=[incident.pipeline_name],
                )
            )
            hyp_counter += 1

    return hypotheses
