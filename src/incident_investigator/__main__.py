"""
Entry point for executing the Data Incident Investigator CLI via:
    python -m incident_investigator
"""

import sys
from pathlib import Path

_src_dir = str(Path(__file__).resolve().parent.parent)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from incident_investigator.cli.runner import IncidentInvestigatorCLI


def main() -> None:
    # If a scenario number is provided as a command-line argument, run it directly
    cli = IncidentInvestigatorCLI()
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        cli.print_banner()
        cli.run_scenario_by_number(int(sys.argv[1]))
    else:
        cli.start_interactive_loop()


if __name__ == "__main__":
    main()
