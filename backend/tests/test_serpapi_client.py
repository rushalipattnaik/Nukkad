from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from app.db.database import get_session
from app.db.models import SerpCache
from app.services.serpapi.client import SerpApiClient


def _client_with_handler(handler) -> SerpApiClient:
    transport = httpx.MockTransport(handler)
    return SerpApiClient(api_key="test-key", http_client=httpx.Client(transport=transport))


def test_write_cache_survives_a_real_unique_constraint_race(monkeypatch):
    """Reproduces the actual bug: two overlapping requests for the same
    query both check 'does this cache row exist?', both see 'no' (because
    neither has committed yet), and both try to INSERT - one wins, the
    other hits a real UNIQUE constraint violation.

    We force this deterministically: pre-insert the row (simulating the
    other request's write that already landed), then patch Session.get to
    still report "not found" for SerpCache (simulating a session that
    checked before that commit happened) so the code underneath takes the
    INSERT path straight into a genuine IntegrityError.
    """
    key = "race-key-123"
    engine = "google_maps"

    # Simulate the other, already-completed request's write.
    with get_session() as session:
        session.add(SerpCache(cache_key=key, engine=engine, params_json="{}",
                               response_json="{}", ttl_seconds=3600))

    original_get = Session.get

    def lying_get(self, entity, ident, *args, **kwargs):
        if entity is SerpCache:
            return None  # pretend the row isn't there yet, forcing an INSERT
        return original_get(self, entity, ident, *args, **kwargs)

    monkeypatch.setattr(Session, "get", lying_get)

    client = SerpApiClient(api_key="test-key")
    try:
        # Must not raise, even though this will hit a real UNIQUE
        # constraint violation under the hood.
        client._write_cache(key, engine, {"q": "x"}, {"local_results": []})
    finally:
        client.close()


def test_concurrent_identical_calls_both_still_return_usable_responses():
    """Two SerpApiClient instances hitting the exact same query - as if two
    overlapping requests each built their own client - must both get back
    a usable response regardless of which one's cache write lands."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"local_results": [{"title": "Example Salon"}]})

    client_a = _client_with_handler(handler)
    client_b = _client_with_handler(handler)
    try:
        params = {"type": "search", "q": "salon Example Town 2", "hl": "en"}
        resp_a = client_a.call("google_maps", params)
        resp_b = client_b.call("google_maps", params)
        assert resp_a.ok
        assert resp_b.ok
    finally:
        client_a.close()
        client_b.close()
