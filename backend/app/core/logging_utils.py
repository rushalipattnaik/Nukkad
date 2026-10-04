"""
Basic logging setup that redacts anything that looks like an API key
before it hits stdout.
"""
from __future__ import annotations

import logging
import re
import sys

from app.core.config import settings

_REDACT_PATTERNS = [
    re.compile(r"(api_key=)[^&\s\"']+", re.IGNORECASE),
    re.compile(r"(x-goog-api-key['\"]?\s*[:=]\s*['\"]?)[^\s,'\"]+", re.IGNORECASE),
]


def redact(text: str) -> str:
    out = text
    for key in (settings.serpapi_api_key, settings.gemini_api_key):
        if key:
            out = out.replace(key, "REDACTED")
    for pattern in _REDACT_PATTERNS:
        out = pattern.sub(r"\1REDACTED", out)
    return out


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact(str(record.msg))
        except Exception:  # noqa: BLE001 - logging must never crash the app
            pass
        return True


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        handler.addFilter(RedactingFilter())
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG if settings.env == "development" else logging.INFO)
        logger.propagate = False
    return logger
