"""
Scenario definitions and execution engine for incident demonstrations.
Connects ingestion -> detection -> incident management -> lineage investigation -> AI synthesis.
"""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from incident_investigator.ai.models import AIInvestigationReport
from incident_investigator.ai.synthesizer import AIIncidentSynthesizer
from incident_investigator.dependency.loader import load_dependency_graph_from_json
from incident_investigator.detection.quality import check_data_freshness, check_duplicate_keys, check_null_columns
from incident_investigator.detection.volume import PipelineRun, detect_volume_anomaly
from incident_investigator.incident.builder import build_incident_from_findings
from incident_investigator.incident.models import Incident
from incident_investigator.incident.report import generate_incident_report
from incident_investigator.ingestion.pipeline_log_reader import read_pipeline_run_from_json
from incident_investigator.investigation.investigator import investigate_incident
from incident_investigator.investigation.models import InvestigationResult


@dataclass
class Scenario:
    """Metadata describing a demonstration scenario."""
    id: str
    number: int
    title: str
    category: str
    summary: str
    run_file: str
    batch_file: Optional[str] = None


@dataclass
class ScenarioExecutionResult:
    """Outcome of running a complete end-to-end incident investigation scenario."""
    scenario: Scenario
    run: PipelineRun
    findings: List[str]
    incident: Optional[Incident]
    investigation: Optional[InvestigationResult]
    ai_report: Optional[AIInvestigationReport]
    markdown_report: str


AVAILABLE_SCENARIOS: List[Scenario] = [
    Scenario(
        id="scenario_volume_drop",
        number=1,
        title="Critical Ingestion Volume Drop (-38% Record Loss)",
        category="Volume Anomaly",
        summary="High-throughput orders ingestion pipeline experiences a sudden 3.8M record loss.",
        run_file="orders_run_001.json",
    ),
    Scenario(
        id="scenario_data_quality",
        number=2,
        title="Silver Layer Quality Failure (Duplicate Keys & Nulls)",
        category="Data Quality",
        summary="Deduplication and cleaning pipeline processes records containing duplicate primary keys and null customer IDs.",
        run_file="cleaning_run_002.json",
        batch_file="orders_batch_sample.json",
    ),
    Scenario(
        id="scenario_freshness_sla",
        number=3,
        title="Gold Revenue Mart Freshness SLA Breach (10h Lag)",
        category="Freshness / SLA",
        summary="Financial revenue data mart suffers upstream delays, breaching the 4-hour freshness SLA.",
        run_file="revenue_mart_run_003.json",
    ),
    Scenario(
        id="scenario_healthy_run",
        number=4,
        title="Healthy Pipeline Run (100% Volume, Zero Violations)",
        category="Baseline / Healthy",
        summary="Demonstrates that the deterministic engine does not create false-positive incidents when checks pass.",
        run_file="healthy_run_004.json",
    ),
]


def execute_scenario(
    scenario: Scenario,
    data_dir: Optional[Path] = None,
    ai_synthesizer: Optional[AIIncidentSynthesizer] = None,
) -> ScenarioExecutionResult:
    """
    Executes a scenario using the real application pipeline without mocked business logic.
    """
    base_data_dir = data_dir or Path("data")
    runs_dir = base_data_dir / "raw" / "pipeline_runs"
    deps_file = base_data_dir / "fixtures" / "pipeline_dependencies.json"

    run_path = runs_dir / scenario.run_file
    if not run_path.exists():
        raise FileNotFoundError(f"Scenario run log file not found: {run_path}")

    # 1. Ingestion
    run = read_pipeline_run_from_json(run_path)
    findings: List[str] = []

    # 2. Dependency Graph Loading
    dep_graph = None
    if deps_file.exists():
        dep_graph = load_dependency_graph_from_json(deps_file)

    incident: Optional[Incident] = None

    # 3. Detectors & Incident Building
    if scenario.id == "scenario_volume_drop":
        vol_result = detect_volume_anomaly(run, threshold_percentage=10.0)
        findings.append(vol_result.message)
        incident = build_incident_from_findings(run=run, volume_result=vol_result)

    elif scenario.id == "scenario_data_quality":
        batch_path = runs_dir / str(scenario.batch_file)
        with open(batch_path, "r", encoding="utf-8") as f:
            records = json.load(f)

        dup_res = check_duplicate_keys(records, primary_key_columns=["order_id"])
        null_res = check_null_columns(records, columns=["customer_id"], max_null_percentage=5.0)

        findings.append(dup_res.message)
        findings.append(null_res.message)

        incident = build_incident_from_findings(
            run=run,
            quality_results=[dup_res, null_res],
            affected_assets=["silver_orders", "gold_daily_revenue", "executive_sales_dashboard"],
        )

    elif scenario.id == "scenario_freshness_sla":
        with open(run_path, "r", encoding="utf-8") as f:
            raw_meta = json.load(f)

        fresh_res = check_data_freshness(
            latest_event_time=raw_meta["latest_event_time"],
            pipeline_execution_time=raw_meta["pipeline_execution_time"],
            max_delay_hours=float(raw_meta.get("max_delay_hours", 4.0)),
        )
        findings.append(fresh_res.message)

        incident = build_incident_from_findings(
            run=run,
            quality_results=[fresh_res],
            affected_assets=["gold_daily_revenue", "executive_sales_dashboard"],
        )

    elif scenario.id == "scenario_healthy_run":
        vol_result = detect_volume_anomaly(run, threshold_percentage=10.0)
        findings.append(vol_result.message)
        incident = build_incident_from_findings(run=run, volume_result=vol_result)

    # 4. Investigation & AI Synthesis
    investigation = None
    ai_report = None
    markdown_lines = []

    if incident is not None:
        investigation = investigate_incident(incident, dep_graph)
        synthesizer = ai_synthesizer or AIIncidentSynthesizer()
        ai_report = synthesizer.synthesize(investigation)

        # Build comprehensive markdown report
        markdown_lines.append(generate_incident_report(incident))
        markdown_lines.append("\n---\n")
        markdown_lines.append(ai_report.to_markdown())
    else:
        markdown_lines.append(f"# Pipeline Run Report: {run.pipeline_name} ({run.run_id})\n")
        markdown_lines.append(f"**Status**: `{run.status}` | **Actual Records**: `{run.actual_record_count:,}`")
        markdown_lines.append("\n## Validation Outcome\nAll deterministic checks passed. No incident opened.")

    return ScenarioExecutionResult(
        scenario=scenario,
        run=run,
        findings=findings,
        incident=incident,
        investigation=investigation,
        ai_report=ai_report,
        markdown_report="\n".join(markdown_lines),
    )
