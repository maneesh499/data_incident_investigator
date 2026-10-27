"""
Unit tests for AI providers, environment variable credentials, and MockAIProvider.
"""

import os
import pytest
from incident_investigator.ai.providers import (
    GeminiProvider,
    MockAIProvider,
    OpenAIProvider,
)


def test_mock_provider_returns_default_response():
    provider = MockAIProvider()
    response = provider.generate("test prompt", "system prompt")
    assert "executive_summary" in response
    assert "cited_evidence_ids" in response
    assert provider.last_prompt == "test prompt"
    assert provider.last_system_prompt == "system prompt"


def test_mock_provider_returns_custom_response():
    provider = MockAIProvider(custom_response='{"custom": "result"}')
    response = provider.generate("hello", "sys")
    assert response == '{"custom": "result"}'


def test_openai_provider_raises_when_api_key_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENAI_API_KEY environment variable is not set"):
        OpenAIProvider(api_key=None)


def test_gemini_provider_raises_when_api_key_missing(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY environment variable is not set"):
        GeminiProvider(api_key=None)
