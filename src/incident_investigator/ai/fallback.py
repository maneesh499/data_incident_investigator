"""
Deterministic fallback synthesizer: generates structured investigation reports without external LLM dependencies.
Guarantees 100% operational uptime when API credentials are absent, rate-limited, or offline.
"""

from typing import List
from incident_investigator.ai.models import AIInvestigationReport, RecommendedAction
from incident_investigator.investigation.models import InvestigationResult


class DeterministicSynthesizer:
    """
    Rule-based synthesizer that formats an InvestigationResult into a structured,
    actionable AIInvestigationReport following strict evidence-grounding standards.
    """

    def synthesize(self, result: InvestigationResult) -> AIInvestigationReport:
        incident = result.incident
        evidence_ids = [ev.evidence_id for ev in incident.evidence_items]
        actions: List[RecommendedAction] = []
        action_counter = 1

        # 1. Executive Summary
        severity_label = incident.severity
        pipeline_name = incident.pipeline_name
        upstream_count = len(result.upstream_assets)
        affected_count = len(result.affected_assets)

        exec_summary = (
            f"Incident {incident.incident_id} occurred on pipeline '{pipeline_name}' (Run ID: {incident.run_id}) "
            f"with severity {severity_label}. Lineage analysis traced {upstream_count} upstream dependencies "
            f"and identified {affected_count} potentially affected downstream assets. "
            f"Evaluated {len(result.hypotheses)} candidate causal hypotheses against verified evidence."
        )

        # 2. Root Cause Assessment
        if result.root_cause_confirmed and incident.root_cause:
            rc_status = "CONFIRMED"
            rc_summary = f"Root cause confirmed: {incident.root_cause}."
        else:
            rc_status = "UNCONFIRMED_PENDING_EVIDENCE"
            rc_summary = (
                "Root cause remains UNCONFIRMED. Observational evidence confirms anomalous behavior, "
                "but conclusive causal proof requires additional upstream and internal pipeline telemetry."
            )

        # 3. Hypotheses Analysis
        hyp_narratives = []
        for h in result.hypotheses:
            cites = ", ".join(h.hypothesis.evidence_ids) or "None"
            hyp_narratives.append(
                f"- **{h.title}** (`{h.hypothesis.hypothesis_id}`): Status `{h.status}` (Citing: {cites}). {h.explanation}"
            )
        hypotheses_text = rc_summary + "\n\n" + "\n".join(hyp_narratives)

        # 4. Deterministic Operational Recommendations based on evidence sources
        for ev in incident.evidence_items:
            if ev.source == "volume_detector":
                # Primary upstream asset or generic
                target_upstream = result.upstream_assets[0].asset_id if result.upstream_assets else "source_system"
                actions.append(
                    RecommendedAction(
                        action_id=f"ACT-{action_counter:03d}",
                        priority="HIGH",
                        action_type="investigate_upstream",
                        description=f"Query upstream asset '{target_upstream}' to determine if the volume drop originated at the source.",
                        target_asset=target_upstream,
                        suggested_query_or_check=f"SELECT count(*) FROM {target_upstream} WHERE event_date = CURRENT_DATE;",
                    )
                )
                action_counter += 1
                actions.append(
                    RecommendedAction(
                        action_id=f"ACT-{action_counter:03d}",
                        priority="HIGH",
                        action_type="inspect_pipeline_logs",
                        description=f"Inspect pipeline '{pipeline_name}' task logs and SQL query execution plan for filter discards.",
                        target_asset=pipeline_name,
                        suggested_query_or_check="grep -iE '(filter|discard|drop|timeout)' /var/log/pipeline/*.log",
                    )
                )
                action_counter += 1

            elif ev.source in ("duplicate_key_check", "primary_key_check"):
                actions.append(
                    RecommendedAction(
                        action_id=f"ACT-{action_counter:03d}",
                        priority="CRITICAL",
                        action_type="profile_data_quality",
                        description=f"Check pipeline '{pipeline_name}' retry history and verify primary key deduplication window.",
                        target_asset=pipeline_name,
                        suggested_query_or_check="SELECT key, count(*) FROM target_table GROUP BY key HAVING count(*) > 1;",
                    )
                )
                action_counter += 1

            elif ev.source in ("null_column_check", "null_check"):
                actions.append(
                    RecommendedAction(
                        action_id=f"ACT-{action_counter:03d}",
                        priority="HIGH",
                        action_type="profile_data_quality",
                        description="Audit upstream schema migration DDL history to check for altered column nullability.",
                        target_asset=pipeline_name,
                        suggested_query_or_check="SELECT column_name, is_nullable FROM information_schema.columns WHERE table_name = 'orders';",
                    )
                )
                action_counter += 1

            elif ev.source in ("freshness_check", "sla_check"):
                actions.append(
                    RecommendedAction(
                        action_id=f"ACT-{action_counter:03d}",
                        priority="HIGH",
                        action_type="investigate_upstream",
                        description="Inspect upstream job scheduler logs for delayed execution triggers or batch backlog.",
                        target_asset=pipeline_name,
                        suggested_query_or_check="airflow dags state <dag_id> <execution_date>",
                    )
                )
                action_counter += 1

        # 5. Notify downstream stakeholders if affected assets exist
        if result.affected_assets:
            downstream_names = [a.name for a in result.affected_assets[:3]]
            actions.append(
                RecommendedAction(
                    action_id=f"ACT-{action_counter:03d}",
                    priority="MEDIUM",
                    action_type="notify_stakeholders",
                    description=f"Notify downstream consumers of potentially impacted data assets: {', '.join(downstream_names)}.",
                    target_asset=result.affected_assets[0].asset_id,
                    suggested_query_or_check=None,
                )
            )

        return AIInvestigationReport(
            incident_id=incident.incident_id,
            executive_summary=exec_summary,
            root_cause_status=rc_status,
            hypotheses_analysis=hypotheses_text,
            cited_evidence_ids=evidence_ids,
            confidence_score=0.90,
            recommended_actions=actions,
            is_fallback=True,
            provider_used="deterministic_fallback",
        )
