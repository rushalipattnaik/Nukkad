"""
Rephrases the "why we think this" sentence that analysis/gaps.py already
produces, since the deterministic version reads a bit mechanical. The
rewrite can't introduce a new fact or number - we check every number in the
output also appears in the original, and throw the rewrite away otherwise.
"""
from __future__ import annotations

import re

from app.core.security import enforce_language_guardrail
from app.llm.gemini_client import GeminiClient, GeminiUnavailable

SCHEMA = {
    "type": "object",
    "properties": {"rewritten": {"type": "string"}},
    "required": ["rewritten"],
}

SYSTEM = (
    "You rephrase a factual, already-verified sentence about local market conditions in India so it "
    "reads naturally, for a small-business owner. Rules: do not add any new fact, number, or claim "
    "that is not already in the original sentence. Do not claim anything is guaranteed, risk-free, "
    "or certain to succeed. Never suggest a specific business is a good or bad investment - only "
    "describe the pattern in the evidence. Keep it to one or two sentences. Return JSON only."
)

_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?%?")


def _numbers_in(text: str) -> set[str]:
    return set(_NUMBER_RE.findall(text))


def rewrite_explanation(original_text: str, client: GeminiClient | None) -> tuple[str, bool]:
    """Returns (final_text, llm_used). Falls back to original_text on any
    failure, guardrail violation, or numeric mismatch."""
    if not original_text or not client or not client.configured:
        return original_text, False

    try:
        data = client.generate_json(SYSTEM, f"Original sentence: {original_text}", SCHEMA)
        candidate = str(data.get("rewritten", "")).strip()
    except GeminiUnavailable:
        return original_text, False

    if not candidate or len(candidate) > 600:
        return original_text, False

    _, banned_hits = enforce_language_guardrail(candidate)
    if banned_hits:
        return original_text, False

    if not _numbers_in(candidate).issubset(_numbers_in(original_text)):
        return original_text, False  # LLM introduced a number we can't verify

    return candidate, True
