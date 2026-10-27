"""
Deterministic hypothesis evaluator based strictly on verified evidence and dependency facts.
Distinguishes between direct proof of a specific causal claim, genuine refutation (contradiction),
and missing evidence.
"""

from typing import Dict, List, Optional, Sequence, Set
from incident_investigator.dependency.graph import DependencyGraph
from incident_investigator.incident.models import Evidence, Incident
from incident_investigator.investigation.models import (
    CandidateHypothesis,
    EvaluatedHypothesis,
    HypothesisStatus,
)

# Explicit mapping of hypothesis categories to evidence sources capable of evaluating them.
# Irrelevant evidence sources cannot support or contradict a hypothesis.
RELEVANT_EVIDENCE_SOURCES: Dict[str, Set[str]] = {
    "upstream_source": {
        "upstream_source_db",
        "upstream_source_check",
        "upstream_audit",
        "source_cdc",
        "upstream_volume_check",
        "volume_detector",  # relevant for anomaly awareness, but insufficient for causal proof
    },
    "pipeline_logic": {
        "pipeline_filter_check",
        "filter_discard_check",
        "stage_metrics",
        "transformation_error",
        "volume_detector",  # relevant for volume anomaly, but insufficient for causal proof
    },
    "data_quality": {
        "duplicate_key_check",
        "primary_key_check",
        "uniqueness_check",
        "null_column_check",
        "null_check",
        "missing_value_check",
    },
    "freshness_sla": {
        "freshness_check",
        "sla_check",
        "data_freshness",
        "lag_check",
    },
}


def evaluate_hypothesis(
    hypothesis: CandidateHypothesis,
    incident: Incident,
    graph: Optional[DependencyGraph] = None,
) -> EvaluatedHypothesis:
    """
    Evaluates an individual candidate hypothesis strictly against verified evidence.
    
    Status definitions:
        - SUPPORTED: Direct, verified evidence specifically substantiates this causal claim.
          (Supporting an anomaly's existence is NOT equivalent to supporting a specific cause).
        - CONTRADICTED: Relevant, verified evidence directly refutes or disproves the hypothesis.
          (An irrelevant check, e.g. 0 duplicates, never contradicts an upstream volume claim).
        - INSUFFICIENT_EVIDENCE: The hypothesis is plausible, but required evidence to prove or disprove it is absent.
        - INCONCLUSIVE: Conflicting evidence exists, precluding a definitive ruling.
    """
    # 1. Handle missing incident or unlinked evidence
    if not incident.evidence_items or not hypothesis.evidence_ids:
        return EvaluatedHypothesis(
            hypothesis=hypothesis,
            status=HypothesisStatus.INSUFFICIENT_EVIDENCE.value,
            explanation="No evidence records available in the incident to evaluate this hypothesis.",
            missing_evidence=["Pipeline execution logs", "Data quality metrics"],
        )

    evidence_map: Dict[str, Evidence] = {ev.evidence_id: ev for ev in incident.evidence_items}
    linked_evidence = [evidence_map[eid] for eid in hypothesis.evidence_ids if eid in evidence_map]

    if not linked_evidence:
        return EvaluatedHypothesis(
            hypothesis=hypothesis,
            status=HypothesisStatus.INSUFFICIENT_EVIDENCE.value,
            explanation=f"Referenced evidence IDs {hypothesis.evidence_ids} not found in incident.",
            missing_evidence=["Referenced evidence records"],
        )

    primary_ev = linked_evidence[0]
    category = hypothesis.category

    # 2. Check evidence relevance: an irrelevant check can neither support nor contradict
    allowed_sources = RELEVANT_EVIDENCE_SOURCES.get(category, set())
    if allowed_sources and primary_ev.source not in allowed_sources:
        return EvaluatedHypothesis(
            hypothesis=hypothesis,
            status=HypothesisStatus.INSUFFICIENT_EVIDENCE.value,
            explanation=(
                f"Evidence '{primary_ev.evidence_id}' from source '{primary_ev.source}' is irrelevant "
                f"to hypothesis category '{category}'. It cannot prove or disprove this claim."
            ),
            missing_evidence=[f"Direct telemetry from {category}-relevant sources"],
        )

    # 3. Evaluate by Category with Strict Causal Rigor

    # --- CATEGORY: UPSTREAM SOURCE ---
    if category == "upstream_source":
        # Proximity in graph is NOT causation. We require direct upstream telemetry.
        is_direct_upstream_telemetry = (
            "upstream" in primary_ev.source.lower()
            and primary_ev.source != "volume_detector"
        )
        if is_direct_upstream_telemetry:
            # If direct upstream telemetry exists and shows under-delivery
            obs = primary_ev.observed_value
            thresh = primary_ev.threshold
            if isinstance(obs, (int, float)) and isinstance(thresh, (int, float)):
                if obs < thresh:
                    return EvaluatedHypothesis(
                        hypothesis=hypothesis,
                        status=HypothesisStatus.SUPPORTED.value,
                        explanation=f"Directly supported by upstream source telemetry {primary_ev.evidence_id}: {obs} delivered vs {thresh} expected.",
                        missing_evidence=[],
                    )
                else:
                    return EvaluatedHypothesis(
                        hypothesis=hypothesis,
                        status=HypothesisStatus.CONTRADICTED.value,
                        explanation=f"Directly contradicted by upstream source telemetry {primary_ev.evidence_id}: source delivered full volume ({obs} vs expected {thresh}).",
                        missing_evidence=[],
                    )

        # If only downstream volume_detector is available (e.g. 6.2M vs 10M):
        return EvaluatedHypothesis(
            hypothesis=hypothesis,
            status=HypothesisStatus.INSUFFICIENT_EVIDENCE.value,
            explanation=(
                f"Local volume anomaly is verified by evidence {primary_ev.evidence_id} "
                f"({primary_ev.observed_value} vs {primary_ev.threshold}), but local volume drop "
                f"cannot prove an upstream source under-delivered without direct source database CDC logs or query telemetry."
            ),
            missing_evidence=[
                "Upstream source database row count / CDC audit log",
                "Source API response status and payload metrics",
            ],
        )

    # --- CATEGORY: PIPELINE LOGIC (Internal Extraction / Filtering) ---
    elif category == "pipeline_logic":
        # Direct evidence of internal discard (e.g. filter metric or execution error)
        has_direct_filter_evidence = (
            primary_ev.source in ("pipeline_filter_check", "filter_discard_check", "stage_metrics", "transformation_error")
            or primary_ev.details.get("filter_discard_count", 0) > 0
            or primary_ev.details.get("discarded_records", 0) > 0
        )
        if has_direct_filter_evidence:
            discard_count = primary_ev.details.get("filter_discard_count") or primary_ev.details.get("discarded_records") or primary_ev.observed_value
            return EvaluatedHypothesis(
                hypothesis=hypothesis,
                status=HypothesisStatus.SUPPORTED.value,
                explanation=f"Directly supported by internal pipeline execution telemetry {primary_ev.evidence_id}: confirmed {discard_count} records dropped by filter/transformation logic.",
                missing_evidence=[],
            )

        # If the volume check shows actual >= expected, volume drop claim is genuinely contradicted
        actual = primary_ev.observed_value
        expected = primary_ev.threshold
        if isinstance(actual, (int, float)) and isinstance(expected, (int, float)) and actual >= expected:
            return EvaluatedHypothesis(
                hypothesis=hypothesis,
                status=HypothesisStatus.CONTRADICTED.value,
                explanation=f"Directly contradicted by volume check {primary_ev.evidence_id}: actual records ({actual}) met or exceeded expected count ({expected}).",
                missing_evidence=[],
            )

        # When only aggregate volume_detector output is available:
        # Crucial: An aggregate drop does NOT prove internal extraction/filtering caused it!
        return EvaluatedHypothesis(
            hypothesis=hypothesis,
            status=HypothesisStatus.INSUFFICIENT_EVIDENCE.value,
            explanation=(
                f"Volume drop anomaly is verified by evidence {primary_ev.evidence_id} "
                f"({actual} vs {expected}), but aggregate output counts cannot prove internal "
                f"extraction or filtering logic caused the drop without step-level discard metrics or SQL execution telemetry."
            ),
            missing_evidence=[
                "Step-level SQL / Spark execution plan and filter discard metrics",
                "Pipeline task error / exception logs",
            ],
        )

    # --- CATEGORY: DATA QUALITY ---
    elif category == "data_quality":
        # Duplicate keys check
        if primary_ev.source in ("duplicate_key_check", "primary_key_check", "uniqueness_check"):
            observed_dups = primary_ev.observed_value
            if isinstance(observed_dups, (int, float)) and observed_dups > 0:
                return EvaluatedHypothesis(
                    hypothesis=hypothesis,
                    status=HypothesisStatus.SUPPORTED.value,
                    explanation=f"Directly supported by evidence {primary_ev.evidence_id}: detected {observed_dups} duplicate primary key records in dataset.",
                    missing_evidence=["Pipeline retry history log", "Upstream join cardinality telemetry"],
                )
            elif isinstance(observed_dups, (int, float)) and observed_dups == 0:
                return EvaluatedHypothesis(
                    hypothesis=hypothesis,
                    status=HypothesisStatus.CONTRADICTED.value,
                    explanation=f"Directly contradicted by evidence {primary_ev.evidence_id}: zero duplicate keys found in dataset.",
                    missing_evidence=[],
                )

        # Null columns check
        elif primary_ev.source in ("null_column_check", "null_check", "missing_value_check"):
            observed_pct = primary_ev.observed_value
            threshold = primary_ev.threshold
            if isinstance(observed_pct, (int, float)) and isinstance(threshold, (int, float)):
                if observed_pct > threshold:
                    return EvaluatedHypothesis(
                        hypothesis=hypothesis,
                        status=HypothesisStatus.SUPPORTED.value,
                        explanation=f"Directly supported by evidence {primary_ev.evidence_id}: null rate of {observed_pct}% exceeded allowable threshold of {threshold}%.",
                        missing_evidence=["Source schema change notifications / DDL migration audit"],
                    )
                else:
                    return EvaluatedHypothesis(
                        hypothesis=hypothesis,
                        status=HypothesisStatus.CONTRADICTED.value,
                        explanation=f"Directly contradicted by evidence {primary_ev.evidence_id}: null rate of {observed_pct}% meets allowable threshold ({threshold}%).",
                        missing_evidence=[],
                    )

        # Fallback for data_quality if check wasn't directly applicable
        return EvaluatedHypothesis(
            hypothesis=hypothesis,
            status=HypothesisStatus.INSUFFICIENT_EVIDENCE.value,
            explanation=f"Evidence {primary_ev.evidence_id} is insufficient to prove or disprove data quality violation.",
            missing_evidence=["Specific column-level quality profiling telemetry"],
        )

    # --- CATEGORY: FRESHNESS SLA ---
    elif category == "freshness_sla":
        if primary_ev.source in ("freshness_check", "sla_check", "data_freshness", "lag_check"):
            observed_lag = primary_ev.observed_value
            max_delay = primary_ev.threshold
            if isinstance(observed_lag, (int, float)) and isinstance(max_delay, (int, float)):
                if observed_lag > max_delay:
                    return EvaluatedHypothesis(
                        hypothesis=hypothesis,
                        status=HypothesisStatus.SUPPORTED.value,
                        explanation=f"Directly supported by evidence {primary_ev.evidence_id}: observed data lag of {observed_lag} hours breached SLA threshold of {max_delay} hours.",
                        missing_evidence=["Upstream job execution schedule and trigger completion history"],
                    )
                else:
                    return EvaluatedHypothesis(
                        hypothesis=hypothesis,
                        status=HypothesisStatus.CONTRADICTED.value,
                        explanation=f"Directly contradicted by evidence {primary_ev.evidence_id}: observed data lag of {observed_lag} hours met SLA threshold ({max_delay} hours).",
                        missing_evidence=[],
                    )

    # Fallback for generic or unhandled categories
    return EvaluatedHypothesis(
        hypothesis=hypothesis,
        status=HypothesisStatus.INCONCLUSIVE.value,
        explanation=f"Evidence {primary_ev.evidence_id} is inconclusive to establish or refute this hypothesis.",
        missing_evidence=["Additional domain-specific telemetry"],
    )


def evaluate_hypotheses(
    hypotheses: Sequence[CandidateHypothesis],
    incident: Incident,
    graph: Optional[DependencyGraph] = None,
) -> List[EvaluatedHypothesis]:
    """
    Evaluates a sequence of candidate hypotheses against incident evidence and dependency context.
    """
    return [evaluate_hypothesis(hyp, incident, graph) for hyp in hypotheses]
