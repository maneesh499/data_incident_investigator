"""
Interactive CLI Runner and terminal presenter for the Data Incident Investigator platform.
Provides a clear, human-readable console interface for reviewing incident scenarios.
"""

from pathlib import Path
import sys
from typing import Optional, TextIO

from incident_investigator.ai.synthesizer import AIIncidentSynthesizer
from incident_investigator.cli.scenarios import (
    AVAILABLE_SCENARIOS,
    Scenario,
    ScenarioExecutionResult,
    execute_scenario,
)


class IncidentInvestigatorCLI:
    """
    Console user interface for browsing scenarios, running investigation pipelines,
    and inspecting root-cause findings.
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        ai_synthesizer: Optional[AIIncidentSynthesizer] = None,
        stdout: Optional[TextIO] = None,
    ) -> None:
        self.data_dir = data_dir or Path("data")
        self.ai_synthesizer = ai_synthesizer or AIIncidentSynthesizer()
        self.out = stdout or sys.stdout

    def print_banner(self) -> None:
        self.out.write("\n" + "=" * 78 + "\n")
        self.out.write("  DATA INCIDENT INVESTIGATOR  |  Root-Cause Analysis Platform\n")
        self.out.write("  Deterministic Validation  *  Dependency Tracing  *  AI Synthesis\n")
        self.out.write("=" * 78 + "\n")

    def print_menu(self) -> None:
        self.out.write("\nAvailable Demonstration Scenarios:\n")
        self.out.write("-" * 78 + "\n")
        for s in AVAILABLE_SCENARIOS:
            self.out.write(f"  [{s.number}] {s.title}\n")
            self.out.write(f"      Category: {s.category}\n")
            self.out.write(f"      Summary:  {s.summary}\n")
        self.out.write("  [0] Exit\n")
        self.out.write("-" * 78 + "\n")

    def display_execution_result(self, result: ScenarioExecutionResult) -> None:
        """Formats and prints the complete investigation lifecycle to stdout."""
        s = result.scenario
        run = result.run
        incident = result.incident

        self.out.write("\n" + "#" * 78 + "\n")
        self.out.write(f"  SCENARIO {s.number}: {s.title.upper()}\n")
        self.out.write("#" * 78 + "\n\n")

        # 1. Ingestion & Execution Metadata
        self.out.write("1. PIPELINE EXECUTION INGESTION\n")
        self.out.write(f"   Pipeline:         {run.pipeline_name}\n")
        self.out.write(f"   Run ID:           {run.run_id}\n")
        self.out.write(f"   Execution Status: {run.status}\n")
        self.out.write(f"   Actual Records:   {run.actual_record_count:,}\n")
        if run.expected_record_count is not None:
            self.out.write(f"   Expected Records: {run.expected_record_count:,}\n")
        self.out.write("\n")

        # 2. Deterministic Detector Findings
        self.out.write("2. DETERMINISTIC DETECTOR FINDINGS\n")
        for finding in result.findings:
            self.out.write(f"   [*] {finding}\n")
        self.out.write("\n")

        # If healthy run with no incident
        if incident is None:
            self.out.write("3. INCIDENT STATUS\n")
            self.out.write("   [OK] All data-quality and volume thresholds satisfied.\n")
            self.out.write("   [OK] Zero incidents opened. Safe for downstream consumption.\n\n")
            return

        # 3. Incident Summary
        self.out.write("3. STANDARDIZED INCIDENT RECORD\n")
        self.out.write(f"   Incident ID:     {incident.incident_id}\n")
        self.out.write(f"   Severity:        {incident.severity}\n")
        self.out.write(f"   Status:          {incident.status}\n")
        self.out.write(f"   Root Cause:      {incident.root_cause or 'UNCONFIRMED (Strict Causality)'}\n")
        self.out.write("   Evidence Items Recorded:\n")
        for ev in incident.evidence_items:
            self.out.write(f"     - [{ev.evidence_id}] ({ev.severity}) {ev.source}: {ev.description}\n")
        self.out.write("\n")

        # 4. Dependency Mapping & Impact Tracing
        inv = result.investigation
        if inv is not None:
            self.out.write("4. DEPENDENCY & BLAST-RADIUS ANALYSIS\n")
            self.out.write(f"   Target Asset:    {inv.investigated_asset_id}\n")
            up_names = [f"{a.name} ({a.asset_id})" for a in inv.upstream_assets]
            down_names = [f"{a.name} ({a.asset_id})" for a in inv.downstream_assets]
            affected_names = [f"{a.name} ({a.asset_id})" for a in inv.affected_assets]

            self.out.write(f"   Direct Upstream:   {', '.join(up_names) if up_names else 'None (Source Asset)'}\n")
            self.out.write(f"   Direct Downstream: {', '.join(down_names) if down_names else 'None (Terminal Consumer)'}\n")
            self.out.write(f"   Potentially Affected Assets ({len(inv.affected_assets)} total):\n")
            for aff in inv.affected_assets:
                self.out.write(f"     -> [{aff.asset_type.upper()}] {aff.name} ({aff.asset_id})\n")
            self.out.write("\n")

            # 5. Causal Hypotheses
            self.out.write("5. EVIDENCE-BASED HYPOTHESIS EVALUATION\n")
            for h in inv.hypotheses:
                self.out.write(f"   [{h.status}] {h.title} ({h.hypothesis.hypothesis_id})\n")
                self.out.write(f"      Citing Evidence: {', '.join(h.hypothesis.evidence_ids) or 'None'}\n")
                self.out.write(f"      Evaluation:      {h.explanation}\n")
                if h.missing_evidence:
                    self.out.write(f"      Missing Proof:   {', '.join(h.missing_evidence)}\n")
            self.out.write("\n")

        # 6. AI Synthesis Brief
        ai = result.ai_report
        if ai is not None:
            self.out.write("6. AI INVESTIGATION SYNTHESIS BRIEF\n")
            self.out.write(f"   Provider:         {ai.provider_used}\n")
            self.out.write(f"   Fallback Mode:    {ai.is_fallback}\n")
            self.out.write(f"   Confidence Score: {int(ai.confidence_score * 100)}%\n")
            self.out.write(f"   Executive Summary:\n     {ai.executive_summary}\n\n")
            self.out.write("   Recommended Operational Actions:\n")
            for act in ai.recommended_actions:
                cmd_part = f" | Command: `{act.suggested_query_or_check}`" if act.suggested_query_or_check else ""
                self.out.write(f"     [{act.priority}] {act.action_id} on `{act.target_asset}`: {act.description}{cmd_part}\n")
            self.out.write("\n")

    def save_markdown_report(self, result: ScenarioExecutionResult) -> Path:
        """Saves the generated markdown report to data/incidents/."""
        inc_dir = self.data_dir / "incidents"
        inc_dir.mkdir(parents=True, exist_ok=True)
        filename = f"report_{result.scenario.id}.md"
        report_path = inc_dir / filename
        report_path.write_text(result.markdown_report, encoding="utf-8")
        return report_path

    def run_scenario_by_number(self, scenario_number: int, save_report: bool = True) -> Optional[ScenarioExecutionResult]:
        """Programmatic execution of a scenario by number."""
        matched = [s for s in AVAILABLE_SCENARIOS if s.number == scenario_number]
        if not matched:
            self.out.write(f"[!] Invalid scenario number: {scenario_number}. Please select 1-{len(AVAILABLE_SCENARIOS)}.\n")
            return None

        scenario = matched[0]
        result = execute_scenario(scenario, data_dir=self.data_dir, ai_synthesizer=self.ai_synthesizer)
        self.display_execution_result(result)

        if save_report and result.incident is not None:
            saved_path = self.save_markdown_report(result)
            self.out.write(f"[+] Saved comprehensive Markdown report to: {saved_path}\n")

        return result

    def start_interactive_loop(self) -> None:
        """Starts the interactive CLI session."""
        self.print_banner()
        while True:
            self.print_menu()
            try:
                choice = input("\nEnter scenario number (0 to exit): ").strip()
            except (EOFError, KeyboardInterrupt):
                self.out.write("\nExiting. Goodbye!\n")
                break

            if choice in ("0", "q", "quit", "exit"):
                self.out.write("\nExiting Data Incident Investigator. Goodbye!\n")
                break

            if not choice.isdigit():
                self.out.write(f"\n[!] Please enter a valid number (1-{len(AVAILABLE_SCENARIOS)}) or 0 to exit.\n")
                continue

            num = int(choice)
            self.run_scenario_by_number(num)


def main() -> None:
    cli = IncidentInvestigatorCLI()
    cli.start_interactive_loop()
