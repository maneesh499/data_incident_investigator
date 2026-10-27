"""
Incident builder: aggregates detector findings into structured incidents with explicit severity rules.
"""

from typing import List, Optional, Sequence
from incident_investigator.detection.volume import PipelineRun, VolumeAnomalyResult
from incident_investigator.detection.quality import QualityCheckResult
from incident_investigator.incident.models import Evidence, Incident, IncidentStatus, Severity

SEVERITY_ORDER = {
    Severity.CRITICAL.value: 4,
    Severity.HIGH.value: 3,
    Severity.MEDIUM.value: 2,
    Severity.LOW.value: 1,
    Severity.INFO.value: 0,
}


def determine_severity(evidence_items: Sequence[Evidence]) -> str:
    """
    Assigns overall incident severity based on the highest severity among all collected evidence.
    Rule: CRITICAL > HIGH > MEDIUM > LOW > INFO. Defaults to LOW if no evidence exists.
    """
    if not evidence_items:
        return Severity.LOW.value

    highest_score = -1
    highest_severity = Severity.LOW.value

    for ev in evidence_items:
        score = SEVERITY_ORDER.get(ev.severity.upper(), 0)
        if score > highest_score:
            highest_score = score
            highest_severity = ev.severity.upper()

    return highest_severity


def build_incident_from_findings(
    run: PipelineRun,
    volume_result: Optional[VolumeAnomalyResult] = None,
    quality_results: Optional[Sequence[QualityCheckResult]] = None,
    incident_id: Optional[str] = None,
    affected_assets: Optional[List[str]] = None,
) -> Optional[Incident]:
    """
    Evaluates detector findings and builds a standardized Incident object if any issues are detected.
    Returns None if no anomalies or quality check failures are found.
    
    Args:
        run: The PipelineRun being investigated.
        volume_result: Result from volume anomaly check (optional).
        quality_results: Sequence of results from data quality checks (optional).
        incident_id: Custom incident identifier. If not provided, generates one from pipeline and run ID.
        affected_assets: Known downstream or target data assets affected.
    """
    evidence_items: List[Evidence] = []
    symptoms: List[str] = []
    evidence_index = 1

    # 1. Process volume anomaly findings
    if volume_result and volume_result.is_anomaly:
        drop_pct = volume_result.volume_difference_percentage or 0.0
        # Explicit severity rule: Volume drops over 30% are CRITICAL; lower significant drops are HIGH
        vol_severity = Severity.CRITICAL.value if drop_pct >= 30.0 else Severity.HIGH.value
        
        evidence_items.append(
            Evidence(
                evidence_id=f"EVD-{evidence_index:03d}",
                source="volume_detector",
                description=volume_result.message,
                severity=vol_severity,
                observed_value=run.actual_record_count,
                threshold=run.expected_record_count,
                details={
                    "drop_percentage": drop_pct,
                    "actual_records": run.actual_record_count,
                    "expected_records": run.expected_record_count,
                }
            )
        )
        symptoms.append(f"Volume drop anomaly: record count dropped by {drop_pct:.2f}%")
        evidence_index += 1

    # 2. Process data-quality check findings
    if quality_results:
        for q in quality_results:
            if not q.passed:
                evidence_items.append(
                    Evidence(
                        evidence_id=f"EVD-{evidence_index:03d}",
                        source=q.check_name,
                        description=q.message,
                        severity=q.severity.upper(),
                        observed_value=q.observed_value,
                        threshold=q.threshold,
                        details=dict(q.details),
                    )
                )
                readable_name = q.check_name.replace("_", " ").title()
                symptoms.append(f"{readable_name}: {q.message}")
                evidence_index += 1

    # If no anomalies or failed checks exist, no incident needs to be opened
    if not evidence_items:
        return None

    # Calculate overall severity based on explicit hierarchy
    incident_severity = determine_severity(evidence_items)

    generated_id = incident_id or f"INC-{run.pipeline_name}-{run.run_id}"
    title = f"Data Incident on {run.pipeline_name} ({run.run_id}): {len(evidence_items)} issue(s) detected"

    return Incident(
        incident_id=generated_id,
        title=title,
        pipeline_name=run.pipeline_name,
        run_id=run.run_id,
        severity=incident_severity,
        status=IncidentStatus.OPEN.value,
        symptoms=symptoms,
        evidence_items=evidence_items,
        root_cause=None,  # Root cause must remain unassigned until evidence proves it
        affected_assets=list(affected_assets) if affected_assets else [run.pipeline_name],
    )
