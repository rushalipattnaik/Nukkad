"""
Thin wrapper around SerpApi's search endpoint. Checks our own cache first,
asks the budget manager for permission, retries on 5xx/timeouts (not on
4xx - no point burning a credit on the same bad request), and caches
successful responses per the engine's TTL.

A SerpApi-side error ("no results" etc) doesn't raise - it comes back as
SerpResponse.error so a bad category doesn't take down the whole scan.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

import httpx

from app.core.config import settings
from app.core.logging_utils import get_logger, redact
from app.db.database import get_session
from app.db.models import SerpCache

logger = get_logger(__name__)

SERP_SEARCH_URL = "https://serpapi.com/search.json"
SERP_ACCOUNT_URL = "https://serpapi.com/account.json"


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class SerpResponse:
    engine: str
    params: dict[str, Any]
    body: dict[str, Any]
    cache_hit: bool = False
    http_status: Optional[int] = None
    error: Optional[str] = None
    empty: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None


def _cache_key(engine: str, params: dict[str, Any]) -> str:
    clean = {k: v for k, v in params.items() if k not in ("api_key",)}
    blob = json.dumps(clean, sort_keys=True, default=str)
    return hashlib.sha256(f"{engine}:{blob}".encode("utf-8")).hexdigest()


class SerpApiClient:
    def __init__(
        self,
        api_key: str,
        budget_check: Optional[Callable[[str], None]] = None,
        budget_record: Optional[Callable[[str, bool], None]] = None,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        """
        budget_check(engine): called BEFORE a real (non-cached) network call.
            Should raise BudgetExceeded if the call must not proceed.
        budget_record(engine, cache_hit): called AFTER the call completes,
            so the caller can update counted/measured spend and the timeline.
        """
        self.api_key = api_key
        self.budget_check = budget_check
        self.budget_record = budget_record
        self.http = http_client or httpx.Client(
            timeout=httpx.Timeout(settings.http_timeout_s, connect=10.0),
            headers={"User-Agent": "nukkad/0.1"},
        )

    def close(self) -> None:
        self.http.close()

    # ------------------------------------------------------------------
    def _ttl_for(self, engine: str) -> int:
        return {
            "google_maps": settings.cache_ttl_maps_s,
            "google_maps_reviews": settings.cache_ttl_reviews_s,
            "google_trends": settings.cache_ttl_trends_s,
            "google_news": settings.cache_ttl_news_s,
            "google_autocomplete": settings.cache_ttl_autocomplete_s,
        }.get(engine, 3600)

    def _read_cache(self, key: str) -> Optional[dict[str, Any]]:
        with get_session() as session:
            row = session.get(SerpCache, key)
            if not row:
                return None
            age = time.time() - row.fetched_at.timestamp()
            if age > row.ttl_seconds:
                return None
            try:
                return json.loads(row.response_json)
            except (ValueError, TypeError):
                return None

    def _write_cache(self, key: str, engine: str, params: dict[str, Any], body: dict[str, Any]) -> None:
        clean_params = {k: v for k, v in params.items() if k != "api_key"}
        with get_session() as session:
            row = session.get(SerpCache, key)
            payload = json.dumps(body, default=str)
            if row:
                row.response_json = payload
                row.engine = engine
                row.params_json = json.dumps(clean_params, default=str)
                row.ttl_seconds = self._ttl_for(engine)
            else:
                session.add(
                    SerpCache(
                        cache_key=key,
                        engine=engine,
                        params_json=json.dumps(clean_params, default=str),
                        response_json=payload,
                        ttl_seconds=self._ttl_for(engine),
                    )
                )

    # ------------------------------------------------------------------
    def call(self, engine: str, params: dict[str, Any]) -> SerpResponse:
        full_params = {**params, "engine": engine}
        key = _cache_key(engine, full_params)

        cached = self._read_cache(key)
        if cached is not None:
            if self.budget_record:
                self.budget_record(engine, True)
            return SerpResponse(engine=engine, params=params, body=cached, cache_hit=True)

        if self.budget_check:
            self.budget_check(engine)  # may raise BudgetExceeded

        attempt = 0
        last_exc: Optional[Exception] = None
        status: Optional[int] = None
        body: dict[str, Any] = {}
        while attempt <= settings.http_retries:
            attempt += 1
            try:
                resp = self.http.get(SERP_SEARCH_URL, params={**full_params, "api_key": self.api_key})
                status = resp.status_code
                try:
                    parsed = resp.json()
                    body = parsed if isinstance(parsed, dict) else {}
                except ValueError:
                    body = {}
                if status >= 500:
                    last_exc = RuntimeError(f"HTTP {status}")
                    time.sleep(min(2 ** attempt, 8))
                    continue
                break
            except httpx.HTTPError as exc:  # noqa: PERF203 - retry loop is intentional
                last_exc = exc
                time.sleep(min(2 ** attempt, 8))
                continue

        if self.budget_record:
            self.budget_record(engine, False)

        if status is None:
            msg = redact(str(last_exc) if last_exc else "unknown network error")
            logger.warning("SerpApi call failed for %s: %s", engine, msg)
            return SerpResponse(engine=engine, params=params, body={}, http_status=None, error=msg)

        error = body.get("error") if isinstance(body.get("error"), str) else None
        empty = bool(error and "any results" in error.lower())

        if status == 200 and error is None:
            self._write_cache(key, engine, full_params, body)

        return SerpResponse(engine=engine, params=params, body=body, http_status=status, error=error, empty=empty)

    def account(self) -> Optional[dict[str, Any]]:
        """Free call, never counted against the budget."""
        try:
            resp = self.http.get(SERP_ACCOUNT_URL, params={"api_key": self.api_key})
            if resp.status_code != 200:
                return None
            return resp.json()
        except (httpx.HTTPError, ValueError):
            return None