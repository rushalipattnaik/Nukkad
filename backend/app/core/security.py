"""
Security helpers shared across the app: stripping control characters from
external text before it's stored or shown, catching any "guaranteed
profit"-style language that shouldn't have gotten past the prompts, and
making sure we only ever link to http(s) URLs.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

BANNED_PHRASES = [
    "guaranteed opportunity",
    "guaranteed demand",
    "guaranteed profit",
    "guaranteed success",
    "guaranteed to succeed",
    "best business to start",
    "will definitely succeed",
    "will succeed",
    "risk-free",
    "sure shot",
    "cannot fail",
    "can't fail",
]

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def sanitize_text(text: object, limit: int = 4000) -> str:
    """Make untrusted text safe to store/display. Never executes it as HTML/JS."""
    if text is None:
        return ""
    s = str(text)
    s = _CONTROL_CHARS.sub(" ", s)
    return s[:limit]


def enforce_language_guardrail(text: str) -> tuple[str, list[str]]:
    """Returns (possibly-flagged text, list of phrases found). We do not try to
    cleverly rewrite the sentence (that risks inventing a new claim); instead
    the caller should drop or replace the offending claim entirely."""
    lowered = text.lower()
    found = [p for p in BANNED_PHRASES if p in lowered]
    return text, found


def is_safe_external_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)
