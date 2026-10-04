"""
Central configuration. Everything comes from environment variables (see
.env.example at the project root). Nothing here is a secret default.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env explicitly rather than relying on python-dotenv's directory
# search, since where this app is launched from can vary (uvicorn from
# backend/, pytest from backend/, or a script from the project root).
# backend/.env (if present) takes priority; otherwise fall back to the
# project root's .env two levels up from this file.
_backend_env = Path(__file__).resolve().parent.parent.parent / ".env"
_root_env = Path(__file__).resolve().parent.parent.parent.parent / ".env"
if _backend_env.exists():
    load_dotenv(_backend_env)
elif _root_env.exists():
    load_dotenv(_root_env)


def _bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _int(name: str, default: int) -> int:
    val = os.getenv(name)
    try:
        return int(val) if val is not None else default
    except ValueError:
        return default


def _list(name: str, default: list[str]) -> list[str]:
    val = os.getenv(name)
    if not val:
        return default
    return [item.strip() for item in val.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    # --- Secrets (never logged, never sent to the frontend) ---
    serpapi_api_key: str = field(default_factory=lambda: os.getenv("SERPAPI_API_KEY", "").strip())
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", "").strip())
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "").strip())

    # --- App ---
    env: str = field(default_factory=lambda: os.getenv("NUKKAD_ENV", "development"))
    database_url: str = field(default_factory=lambda: os.getenv("NUKKAD_DATABASE_URL", "sqlite:///./nukkad.db"))
    allowed_origins: list[str] = field(
        default_factory=lambda: _list("NUKKAD_ALLOWED_ORIGINS", ["http://localhost:5173"])
    )

    # --- Credit / budget controls (see docs/credit-strategy.md) ---
    daily_credit_cap: int = field(default_factory=lambda: _int("NUKKAD_DAILY_CREDIT_CAP", 300))
    max_scan_credits: int = field(default_factory=lambda: _int("NUKKAD_MAX_SCAN_CREDITS", 150))
    lite_scan_credits: int = field(default_factory=lambda: _int("NUKKAD_LITE_SCAN_CREDITS", 40))
    standard_scan_credits: int = field(default_factory=lambda: _int("NUKKAD_STANDARD_SCAN_CREDITS", 90))
    deep_scan_credits: int = field(default_factory=lambda: _int("NUKKAD_DEEP_SCAN_CREDITS", 150))

    # --- HTTP behaviour toward SerpApi / Gemini ---
    http_timeout_s: float = field(default_factory=lambda: float(os.getenv("NUKKAD_HTTP_TIMEOUT_S", "25")))
    http_retries: int = field(default_factory=lambda: _int("NUKKAD_HTTP_RETRIES", 2))
    cache_ttl_maps_s: int = field(default_factory=lambda: _int("NUKKAD_CACHE_TTL_MAPS_S", 7 * 24 * 3600))
    cache_ttl_reviews_s: int = field(default_factory=lambda: _int("NUKKAD_CACHE_TTL_REVIEWS_S", 7 * 24 * 3600))
    cache_ttl_trends_s: int = field(default_factory=lambda: _int("NUKKAD_CACHE_TTL_TRENDS_S", 30 * 24 * 3600))
    cache_ttl_news_s: int = field(default_factory=lambda: _int("NUKKAD_CACHE_TTL_NEWS_S", 24 * 3600))
    cache_ttl_autocomplete_s: int = field(default_factory=lambda: _int("NUKKAD_CACHE_TTL_AUTOCOMPLETE_S", 7 * 24 * 3600))

    # --- Rate limiting (in-process, no Redis needed) ---
    rate_limit_per_minute: int = field(default_factory=lambda: _int("NUKKAD_RATE_LIMIT_PER_MINUTE", 20))
    scan_rate_limit_per_hour: int = field(default_factory=lambda: _int("NUKKAD_SCAN_RATE_LIMIT_PER_HOUR", 6))

    demo_mode_only: bool = field(default_factory=lambda: _bool("NUKKAD_DEMO_MODE_ONLY", False))


settings = Settings()


def require_serpapi_key() -> str:
    if not settings.serpapi_api_key:
        raise RuntimeError(
            "SERPAPI_API_KEY is not set. Copy .env.example to .env at the project "
            "root and add your key."
        )
    return settings.serpapi_api_key
