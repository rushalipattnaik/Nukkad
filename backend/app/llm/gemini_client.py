"""
Small Gemini REST client, used only for structured JSON output (review
tagging and gap narration). No tools, no SerpApi access - just a schema-
constrained generateContent call.

If GEMINI_API_KEY/GEMINI_MODEL aren't set, or a call fails, callers fall
back to their deterministic path (see agents/voc_analyst.py and
agents/gap_explainer.py).
"""
from __future__ import annotations

import json
from typing import Any, Optional

import httpx

from app.core.config import settings
from app.core.logging_utils import get_logger, redact

logger = get_logger(__name__)

GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiUnavailable(RuntimeError):
    pass


class GeminiClient:
    def __init__(self, api_key: str | None = None, model: str | None = None,
                 http_client: Optional[httpx.Client] = None) -> None:
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.gemini_model
        self.http = http_client or httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0))

    def close(self) -> None:
        self.http.close()

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.model)

    def generate_json(self, system: str, user: str, schema: dict[str, Any]) -> dict[str, Any]:
        """Returns parsed JSON matching `schema`, or raises GeminiUnavailable."""
        if not self.configured:
            raise GeminiUnavailable("Gemini is not configured (missing API key or model).")

        last_error: str | None = None
        for schema_field in ("responseJsonSchema", "responseSchema"):
            payload = {
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {
                    "temperature": 0,
                    "responseMimeType": "application/json",
                    schema_field: schema,
                },
            }
            try:
                resp = self.http.post(
                    f"{GEMINI_BASE}/models/{self.model}:generateContent",
                    headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
                    json=payload,
                )
            except httpx.HTTPError as exc:
                last_error = redact(f"{type(exc).__name__}: {exc}")
                continue

            if resp.status_code != 200:
                try:
                    msg = resp.json().get("error", {}).get("message", "")
                except ValueError:
                    msg = resp.text[:200]
                last_error = redact(f"HTTP {resp.status_code}: {msg}")
                if resp.status_code == 400 and schema_field == "responseJsonSchema":
                    continue  # try the older field name
                logger.warning("Gemini call failed: %s", last_error)
                raise GeminiUnavailable(last_error)

            try:
                body = resp.json()
                parts = (((body.get("candidates") or [{}])[0].get("content") or {}).get("parts")) or []
                text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
                return json.loads(text)
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                last_error = f"could not parse Gemini response: {exc}"
                continue

        raise GeminiUnavailable(last_error or "Gemini call failed for an unknown reason")
