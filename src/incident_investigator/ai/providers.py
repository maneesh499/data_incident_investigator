"""
AI model provider interfaces and implementations.
Keeps API credentials strictly in environment variables, never hardcoded.
Provides MockAIProvider for deterministic unit testing.
"""

import json
import os
import urllib.error
import urllib.request
from typing import Optional, Protocol


class AIProvider(Protocol):
    """Protocol defining the interface for language model providers."""
    def generate(self, prompt: str, system_prompt: str) -> str:
        """Generates a text completion given user prompt and system instructions."""
        ...


class MockAIProvider:
    """
    Mock provider for local testing and CI/CD. Returns deterministic structured JSON
    without making network requests or requiring API keys.
    """

    def __init__(self, custom_response: Optional[str] = None) -> None:
        self.custom_response = custom_response
        self.last_prompt: Optional[str] = None
        self.last_system_prompt: Optional[str] = None

    def generate(self, prompt: str, system_prompt: str) -> str:
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt

        if self.custom_response is not None:
            return self.custom_response

        # Default structured mock JSON output adhering to schema
        return json.dumps({
            "executive_summary": "Simulated AI analysis: Significant volume drop detected during ingestion. Upstream database and internal filter logic were evaluated.",
            "root_cause_status": "UNCONFIRMED_PENDING_EVIDENCE",
            "hypotheses_analysis": "Hypothesis HYP-001 (upstream under-delivery) is plausible but lacks source database CDC evidence. Hypothesis HYP-002 (pipeline filter drop) requires step-level discard metrics.",
            "cited_evidence_ids": ["EVD-001"],
            "confidence_score": 0.88,
            "recommended_actions": [
                {
                    "action_id": "ACT-001",
                    "priority": "HIGH",
                    "action_type": "investigate_upstream",
                    "description": "Inspect upstream source PostgreSQL database row counts.",
                    "target_asset": "source_orders_db",
                    "suggested_query_or_check": "SELECT count(*) FROM orders WHERE date = CURRENT_DATE;",
                },
                {
                    "action_id": "ACT-002",
                    "priority": "HIGH",
                    "action_type": "inspect_pipeline_logs",
                    "description": "Check orchestrator logs for query timeouts or filter discards.",
                    "target_asset": "orders_ingestion",
                    "suggested_query_or_check": "grep -i 'discard' /var/log/pipeline.log",
                }
            ]
        })


class OpenAIProvider:
    """
    OpenAI provider using environment variable OPENAI_API_KEY.
    Uses the official openai SDK if installed, or falls back to standard-library REST.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini") -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")

    def generate(self, prompt: str, system_prompt: str) -> str:
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            return response.choices[0].message.content or "{}"
        except ImportError:
            # Fallback to standard library REST request if SDK is not present
            url = "https://api.openai.com/v1/chat/completions"
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"]


class GeminiProvider:
    """
    Google Gemini provider using environment variable GEMINI_API_KEY.
    Calls the Gemini REST API using Python standard library.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-1.5-flash") -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")

    def generate(self, prompt: str, system_prompt: str) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
            f"?key={self.api_key}"
        )
        combined_text = f"System Instructions:\n{system_prompt}\n\nUser Context:\n{prompt}"
        payload = {
            "contents": [
                {
                    "parts": [{"text": combined_text}]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1,
            }
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["candidates"][0]["content"]["parts"][0]["text"]
