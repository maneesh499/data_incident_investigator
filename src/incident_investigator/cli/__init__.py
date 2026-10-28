"""
CLI demonstration package.
"""

from incident_investigator.cli.scenarios import (
    AVAILABLE_SCENARIOS,
    Scenario,
    ScenarioExecutionResult,
    execute_scenario,
)
from incident_investigator.cli.runner import IncidentInvestigatorCLI, main

__all__ = [
    "AVAILABLE_SCENARIOS",
    "IncidentInvestigatorCLI",
    "Scenario",
    "ScenarioExecutionResult",
    "execute_scenario",
    "main",
]
