"""
AI-assisted investigation package.
Provides structured prompt generation, evidence-grounded AI synthesis,
and offline deterministic fallback reporting.
"""

from incident_investigator.ai.models import AIInvestigationReport, RecommendedAction
from incident_investigator.ai.fallback import DeterministicSynthesizer
from incident_investigator.ai.providers import (
    AIProvider,
    GeminiProvider,
    MockAIProvider,
    OpenAIProvider,
)
from incident_investigator.ai.synthesizer import AIIncidentSynthesizer

__all__ = [
    "AIIncidentSynthesizer",
    "AIInvestigationReport",
    "AIProvider",
    "DeterministicSynthesizer",
    "GeminiProvider",
    "MockAIProvider",
    "OpenAIProvider",
    "RecommendedAction",
]
