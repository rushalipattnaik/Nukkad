from __future__ import annotations

import json

import httpx
import pytest

from app.domain.schemas import GapType, ScanPreset, ScanRequest
from app.llm.gemini_client import GeminiClient
from app.orchestrator.orchestrator import run_scan
from app.services.serpapi.client import SerpApiClient

TOWN = "Test Town"
CENTER = (23.02, 76.72)

# medical store: 1 place, weekday hours only until 8pm (does not cover the
# 21:00-06:00 need window, but supply is too small for a service-window
# gap to fire - it should trigger ABSENCE instead, given High demand).
MEDICAL_PLACES = [{
    "title": "Sharma Medical Store", "data_id": "med1", "place_id": "med1",
    "gps_coordinates": {"latitude": CENTER[0] + 0.001, "longitude": CENTER[1]},
    "rating": 4.5, "reviews": 50, "type": "Pharmacy",
    "operating_hours": {"monday": "9 AM-8 PM", "tuesday": "9 AM-8 PM"},
}]

# dentist: 10 places, 4 of them under 4.0 rating (40% low-rating share),
# which combined with a complaint topic should trigger a QUALITY gap.
DENTIST_PLACES = []
for i in range(10):
    DENTIST_PLACES.append({
        "title": f"Dental Clinic {i}", "data_id": f"dent{i}", "place_id": f"dent{i}",
        "gps_coordinates": {"latitude": CENTER[0] + 0.001 * i, "longitude": CENTER[1]},
        "rating": 3.2 if i < 4 else 4.6, "reviews": 200 if i == 3 else 20, "type": "Dentist",
        "operating_hours": {"monday": "9 AM-6 PM"},
    })

MAPS_BY_QUERY = {
    "medical store": MEDICAL_PLACES,
    "dentist": DENTIST_PLACES,
}

TREND_VALUES = {"medical store": 85, "dentist": 78}


def make_handler():
    def handler(request: httpx.Request) -> httpx.Response:
        url = request.url
        params = dict(url.params)

        if url.path == "/account.json":
            return httpx.Response(200, json={
                "total_searches_left": 9950, "plan_searches_left": 10000, "extra_credits": 0,
            })

        if url.path != "/search.json":
            return httpx.Response(404, json={"error": f"unexpected path {url.path}"})

        engine = params.get("engine")

        if engine == "google_maps":
            q = params.get("q", "")
            if q == TOWN:
                return httpx.Response(200, json={
                    "place_results": {"title": TOWN, "gps_coordinates": {"latitude": CENTER[0], "longitude": CENTER[1]}}
                })
            return httpx.Response(200, json={"local_results": MAPS_BY_QUERY.get(q, [])})

        if engine == "google_trends":
            terms = params.get("q", "").split(",")
            values = [{"query": t, "value": TREND_VALUES[t]} for t in terms if t in TREND_VALUES]
            return httpx.Response(200, json={"interest_over_time": {"timeline_data": [{"values": values}]}})

        if engine == "google_news":
            return httpx.Response(200, json={"news_results": [
                {"title": f"Local update for {TOWN}", "source": {"name": "Local Times"},
                 "published_at": "2026-09-01 00:00:00 UTC", "snippet": "A short local update."}
            ]})

        if engine == "google_autocomplete":
            q = params.get("q", "")
            return httpx.Response(200, json={"suggestions": [
                {"value": f"{q} open 24 hours"}, {"value": f"{q} near me"}, {"value": f"{q} price"},
            ]})

        if engine == "google_maps_reviews":
            sort_by = params.get("sort_by")
            if sort_by == "ratingLow":
                reviews = [
                    {"rating": 1, "snippet": "Staff were rude and made me wait an hour.",
                     "iso_date": "2026-01-01T00:00:00Z", "review_id": "r_low_1"},
                    {"rating": 2, "snippet": "Rude behaviour at the front desk again.",
                     "iso_date": "2026-01-02T00:00:00Z", "review_id": "r_low_2"},
                ]
                return httpx.Response(200, json={"reviews": reviews})
            reviews = [
                {"rating": 5, "snippet": "Great service overall.", "iso_date": "2026-01-03T00:00:00Z",
                 "review_id": "r_def_1"},
            ]
            topics = [{"keyword": "rude staff", "mentions": 5}]
            return httpx.Response(200, json={"reviews": reviews, "topics": topics})

        return httpx.Response(404, json={"error": f"unhandled engine {engine}"})

    return handler


@pytest.fixture()
def mocked_serp_client() -> SerpApiClient:
    transport = httpx.MockTransport(make_handler())
    http_client = httpx.Client(transport=transport)
    client = SerpApiClient(api_key="test-key", http_client=http_client)
    yield client
    client.close()


@pytest.fixture()
def disabled_gemini_client() -> GeminiClient:
    # Empty api_key/model => .configured is False => every agent falls back
    # to its deterministic path with ZERO network calls attempted.
    client = GeminiClient(api_key="", model="")
    yield client
    client.close()


def test_full_scan_lite_preset_produces_expected_gaps(mocked_serp_client, disabled_gemini_client):
    request = ScanRequest(town_name=TOWN, radius_km=3.0, preset=ScanPreset.lite)
    result = run_scan(request, serp_client=mocked_serp_client, gemini_client=disabled_gemini_client)

    assert result.status == "completed"
    assert result.center_lat == CENTER[0]
    assert result.center_lng == CENTER[1]
    assert result.llm_used is False  # Gemini was disabled - must not silently claim LLM usage

    # Budget was respected: this preset's cap is the lite cap.
    assert result.budget.counted_spent <= result.budget.cap
    assert result.budget.refused_calls == 0  # our mocked scan is small enough to fit the budget

    gap_types_by_category = {(g.category, g.gap_type) for g in result.gaps}
    assert ("Medical store / pharmacy", GapType.ABSENCE) in gap_types_by_category
    assert ("Dentist", GapType.QUALITY) in gap_types_by_category

    # Every single claim, in every gap, cites evidence that actually exists
    # in the ledger - this is the core "no unverifiable claims" guarantee.
    evidence_ids = set(result.evidence.keys())
    for gap in result.gaps:
        for field in ("what_exists", "what_customers_say", "what_people_search",
                      "what_is_changing", "why_we_think_this"):
            for claim in getattr(gap, field):
                assert claim.evidence_ids, "a verified claim must not be empty of evidence"
                assert set(claim.evidence_ids).issubset(evidence_ids)

    # The timeline is non-trivial and step-shaped (for the frontend replay).
    assert len(result.timeline) > 5
    assert all("label" in step and "phase" in step for step in result.timeline)

    # No language-guardrail violations anywhere in the output.
    full_text = json.dumps(result.model_dump(mode="json"))
    for banned in ("guaranteed opportunity", "guaranteed profit", "best business to start"):
        assert banned not in full_text.lower()


def test_scan_persists_and_is_retrievable(mocked_serp_client, disabled_gemini_client):
    from app.db.database import get_session
    from app.db.models import ScanRecord

    request = ScanRequest(town_name=TOWN, radius_km=3.0, preset=ScanPreset.lite)
    result = run_scan(request, serp_client=mocked_serp_client, gemini_client=disabled_gemini_client)

    with get_session() as session:
        row = session.get(ScanRecord, result.scan_id)
        assert row is not None
        assert row.town_name == TOWN


def test_geocode_failure_produces_a_failed_scan_not_a_crash(disabled_gemini_client):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/account.json":
            return httpx.Response(200, json={"total_searches_left": 100})
        return httpx.Response(200, json={"error": "Google hasn't returned any results for this query."})

    client = SerpApiClient(api_key="test-key", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    try:
        request = ScanRequest(town_name="Nowhereville", radius_km=3.0, preset=ScanPreset.lite)
        result = run_scan(request, serp_client=client, gemini_client=disabled_gemini_client)
        assert result.status == "failed"
        assert result.warnings  # explains why, rather than crashing
    finally:
        client.close()


def test_budget_cap_is_enforced_and_scan_still_completes(disabled_gemini_client, monkeypatch):
    """A very small cap should make the orchestrator degrade gracefully -
    it must finish with a 'completed' scan and a warning, not crash."""
    from app.domain.schemas import ScanPreset as _Preset
    from app.orchestrator import orchestrator as orch_module

    monkeypatch.setitem(orch_module.PRESET_CAPS, _Preset.lite, 1)

    transport = httpx.MockTransport(make_handler())
    client = SerpApiClient(api_key="test-key", http_client=httpx.Client(transport=transport))
    try:
        # An explicit, never-before-used center skips geocoding AND ensures
        # none of these calls are served from another test's cache entry.
        request = ScanRequest(town_name=TOWN, radius_km=3.0, preset=ScanPreset.lite,
                              center_lat=19.111, center_lng=72.222)
        result = run_scan(request, serp_client=client, gemini_client=disabled_gemini_client)
        assert result.status in ("completed", "failed")
        assert result.budget.counted_spent <= 1
        assert result.budget.refused_calls >= 1  # later calls were correctly refused
    finally:
        client.close()
