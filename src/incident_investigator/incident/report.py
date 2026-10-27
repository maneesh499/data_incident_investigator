"""
Incident report generator: creates reproducible markdown and structured reports from Incident objects.
"""

from incident_investigator.incident.models import Incident


def generate_incident_report(incident: Incident) -> str:
    """
    Renders a reproducible, human-readable markdown incident report.
    Carefully distinguishes confirmed root cause from unconfirmed status.
    """
    lines = []
    lines.append(f"# Incident Report: {incident.incident_id}")
    lines.append("")
    lines.append(f"**Title**: {incident.title}")
    lines.append(f"**Severity**: `{incident.severity}` | **Status**: `{incident.status}`")
    lines.append(f"**Pipeline**: `{incident.pipeline_name}` | **Run ID**: `{incident.run_id}`")
    lines.append(f"**Reported At**: {incident.created_at.isoformat()}")
    if incident.affected_assets:
        lines.append(f"**Affected Assets**: {', '.join(incident.affected_assets)}")
    lines.append("")

    # Symptoms section
    lines.append("## Symptoms")
    if incident.symptoms:
        for symptom in incident.symptoms:
            lines.append(f"- {symptom}")
    else:
        lines.append("- None reported")
    lines.append("")

    # Evidence items table
    lines.append("## Observed Evidence")
    if incident.evidence_items:
        lines.append("| Evidence ID | Source | Severity | Observed | Threshold | Description |")
        lines.append("|---|---|---|---|---|---|")
        for ev in incident.evidence_items:
            obs = str(ev.observed_value)
            thresh = str(ev.threshold)
            # Escape pipe characters if any in description
            desc = ev.description.replace("|", "/")
            lines.append(f"| {ev.evidence_id} | {ev.source} | {ev.severity} | {obs} | {thresh} | {desc} |")
    else:
        lines.append("No structured evidence recorded.")
    lines.append("")

    # Root cause section
    lines.append("## Root Cause Status")
    if incident.root_cause:
        lines.append(f"**Confirmed Cause**: {incident.root_cause}")
    else:
        lines.append(
            "> [!NOTE]\n"
            "> **Pending Investigation**: No root cause has been confirmed yet. "
            "In accordance with investigative rigor, a root cause is not assumed "
            "without dependency tracing and hypothesis validation."
        )
    lines.append("")

    return "\n".join(lines)
