"""
Convenience launcher for the Data Incident Investigator interactive CLI.
Allows running:
    python run_demo.py
    python run_demo.py 1
"""

import sys
from pathlib import Path

# Add src to sys.path so it works seamlessly from repository root
sys.path.insert(0, str(Path(__file__).parent / "src"))

from incident_investigator.cli.runner import IncidentInvestigatorCLI


def main() -> None:
    cli = IncidentInvestigatorCLI()
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        cli.print_banner()
        cli.run_scenario_by_number(int(sys.argv[1]))
    else:
        cli.start_interactive_loop()


if __name__ == "__main__":
    main()
