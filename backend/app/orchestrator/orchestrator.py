"""
Runs one full scan and returns the complete ScanResult. Runs synchronously
rather than over SSE - a scan takes 10-40s, and the frontend just replays
the returned `timeline` step by step for the live-feeling effect (see
TimelineView.tsx). Simpler than managing a websocket connection, at the
cost of waiting for the full result before anything shows up.

Pipeline: scope categories -> search (Trends/News/Maps/Autocomplete/Reviews)
-> classify gaps -> verify claims -> return.

`guarded_call` wraps every SerpApi call so a budget refusal or an API error
just gets logged as a warning instead of crashing the scan.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from app.analysis.gaps import build_category_gaps
from app.analysis.demand import compute_demand_index, extract_trend_average
from app.analysis.hours import hours_coverage_stats
from app.analysis.dedupe import dedupe_places
from app.agents.gap_explainer import rewrite_explanation
from app.agents.verifier import verify_all
from app.agents.voc_analyst import tag_reviews
from app.core.config import settings
from app.core.logging_utils import get_logger
from app.db.database import get_session
from app.db.models import ScanRecord
from app.domain.schemas import (
    CategoryResult, EvidenceItem, EvidenceKind, ScanPreset, ScanRequest, ScanResult,
)
from app.llm.gemini_client import GeminiClient
from app.planner.budget import BudgetManager
from app.planner.taxonomy import resolve_categories
from app.services.serpapi import engines as norm
from app.services.serpapi.client import BudgetExceeded, SerpApiClient, SerpResponse

logger = get_logger(__name__)

PRESET_CAPS = {
    ScanPreset.lite: settings.lite_scan_credits,
    ScanPreset.standard: settings.standard_scan_credits,
    ScanPreset.deep: settings.deep_scan_credits,
}
PRESET_MAX_CATEGORIES = {ScanPreset.lite: 8, ScanPreset.standard: 12, ScanPreset.deep: 15}
PRESET_DEEP_COUNT = {ScanPreset.lite: 2, ScanPreset.standard: 4, ScanPreset.deep: 6}


def _zoom_for_radius(radius_km: float) -> int:
    if radius_km <= 2:
        return 15
    if radius_km <= 5:
        return 13
    if radius_km <= 10:
        return 12
    return 11


class ScanContext:
    """Holds everything one run_scan() call needs, so the function itself
    stays readable instead of threading ten arguments through every helper."""

    def __init__(self, scan_id: str) -> None:
        self.scan_id = scan_id
        self.evidence: dict[str, EvidenceItem] = {}
        self.timeline: list[dict[str, Any]] = []
        self.warnings: list[str] = []

    def add_evidence(
        self, kind: EvidenceKind, engine: str, title: str, data: dict[str, Any],
        query: Optional[dict[str, Any]] = None, source_ref: Optional[str] = None,
        category: Optional[str] = None, lat: Optional[float] = None, lng: Optional[float] = None,
        derived_from: Optional[list[str]] = None, cache_hit: bool = False,
    ) -> str:
        eid = f"E-{kind.value}-{uuid.uuid4().hex[:10]}"
        self.evidence[eid] = EvidenceItem(
            evidence_id=eid, scan_id=self.scan_id, kind=kind, engine=engine,
            query=query or {}, title=title[:200], data=data, source_ref=source_ref,
            category=category, lat=lat, lng=lng, derived_from=derived_from or [], cache_hit=cache_hit,
        )
        return eid

    def record_computed(self, title: str, data: dict[str, Any], derived_from: list[str]) -> str:
        return self.add_evidence(EvidenceKind.COMPUTED, "nukkad_compute", title, data, derived_from=derived_from)

    def log_step(self, phase: str, label: str, detail: str = "", engine: Optional[str] = None,
                 query: Optional[dict[str, Any]] = None, result_count: Optional[int] = None,
                 status: str = "ok") -> None:
        self.timeline.append({
            "phase": phase, "label": label, "detail": detail, "engine": engine,
            "query": query, "result_count": result_count, "status": status,
            "seq": len(self.timeline),
        })


def _guarded_call(ctx: ScanContext, phase: str, label: str, client: SerpApiClient,
                   engine: str, params: dict[str, Any]) -> Optional[SerpResponse]:
    try:
        resp = client.call(engine, params)
    except BudgetExceeded as exc:
        ctx.warnings.append(str(exc))
        ctx.log_step(phase, label, detail=str(exc), engine=engine, query=params, status="budget_exceeded")
        return None
    if resp.error and not resp.empty:
        ctx.log_step(phase, label, detail=f"SerpApi error: {resp.error}", engine=engine, query=params, status="error")
        ctx.warnings.append(f"{label}: {resp.error}")
    elif resp.empty:
        ctx.log_step(phase, label, detail="No results", engine=engine, query=params, status="empty", result_count=0)
    else:
        note = " (cached)" if resp.cache_hit else ""
        ctx.log_step(phase, label + note, engine=engine, query=params, status="ok")
    return resp


def run_scan(
    request: ScanRequest,
    serp_client: Optional[SerpApiClient] = None,
    gemini_client: Optional[GeminiClient] = None,
) -> ScanResult:
    scan_id = f"scan_{uuid.uuid4().hex[:12]}"
    ctx = ScanContext(scan_id)
    owns_serp = serp_client is None
    owns_gemini = gemini_client is None
    serp_client = serp_client or SerpApiClient(settings.serpapi_api_key)
    gemini_client = gemini_client or GeminiClient()

    cap = PRESET_CAPS.get(request.preset, settings.standard_scan_credits)
    budget = BudgetManager(cap=min(cap, settings.max_scan_credits), daily_cap=settings.daily_credit_cap)
    serp_client.budget_check = budget.check
    serp_client.budget_record = budget.record

    account_before = serp_client.account()

    try:
        # ---- SCOPING ---------------------------------------------------
        max_categories = PRESET_MAX_CATEGORIES.get(request.preset, 12)
        categories = resolve_categories(request.categories)[:max_categories]

        center = (request.center_lat, request.center_lng) if request.center_lat and request.center_lng else None
        if center is None:
            geo_resp = _guarded_call(ctx, "SCOPING", f"Locate '{request.town_name}'", serp_client,
                                      "google_maps", {"type": "search", "q": request.town_name, "hl": "en"})
            if geo_resp and geo_resp.ok:
                center = norm.normalize_geocode(geo_resp.body)
            if center is None:
                ctx.warnings.append(f"Could not locate '{request.town_name}' on Google Maps.")
                return _finalize(ctx, request, scan_id, center=(0.0, 0.0), budget=budget,
                                 serp_client=serp_client, account_before=account_before, status="failed",
                                 owns_serp=owns_serp, owns_gemini=owns_gemini, gemini_client=gemini_client)

        zoom = _zoom_for_radius(request.radius_km)

        # ---- SEARCH: demand (Trends, batched 5 terms per call) ---------
        demand_by_category: dict[str, dict[str, Any]] = {}
        demand_evidence_by_category: dict[str, list[str]] = {c.key: [] for c in categories}
        terms = [c.maps_query for c in categories]
        for i in range(0, len(terms), 5):
            batch = terms[i:i + 5]
            resp = _guarded_call(ctx, "SEARCH", f"Check demand interest for {len(batch)} categories",
                                  serp_client, "google_trends",
                                  {"q": ",".join(batch), "geo": "IN", "date": "today 12-m",
                                   "data_type": "TIMESERIES", "hl": "en"})
            if not resp or not resp.ok:
                continue
            norm_trends = norm.normalize_trends_timeseries(resp.body)
            eid = ctx.add_evidence(EvidenceKind.TREND_SERIES, "google_trends",
                                    f"Search-interest trend for: {', '.join(batch)}",
                                    {"terms": batch, "points": norm_trends["points"]},
                                    query=resp.params, cache_hit=resp.cache_hit)
            for cat in categories:
                if cat.maps_query in batch:
                    avg = extract_trend_average(norm_trends["raw_timeline"], cat.maps_query)
                    if avg is not None:
                        demand_by_category[cat.key] = {"trend_avg": avg}
                    demand_evidence_by_category[cat.key].append(eid)

        # ---- SEARCH: town-level catalysts (News) ------------------------
        news_items: list[dict[str, Any]] = []
        for query in (f"{request.town_name} industrial development", f"{request.town_name} news"):
            resp = _guarded_call(ctx, "SEARCH", f"Check local catalysts: '{query}'", serp_client,
                                  "google_news", {"q": query, "gl": "in", "hl": "en"})
            if resp and resp.ok:
                for item in norm.normalize_news(resp.body)[:5]:
                    eid = ctx.add_evidence(EvidenceKind.NEWS_ITEM, "google_news", item["title"], item,
                                            source_ref=item.get("link"), query=resp.params, cache_hit=resp.cache_hit)
                    item["_evidence_id"] = eid
                    news_items.append(item)

        # ---- SEARCH: supply (coarse Maps, all selected categories) -----
        places_by_category: dict[str, list[dict[str, Any]]] = {}
        for cat in categories:
            resp = _guarded_call(ctx, "SEARCH", f"Check who already serves '{cat.label}'", serp_client,
                                  "google_maps", {"type": "search", "q": cat.maps_query,
                                                  "ll": f"@{center[0]},{center[1]},{zoom}z", "hl": "en"})
            places: list[dict[str, Any]] = []
            if resp and resp.ok:
                raw_places = norm.normalize_maps_search(resp.body, center)
                for p in raw_places:
                    eid = ctx.add_evidence(EvidenceKind.PLACE, "google_maps", p["title"], p,
                                            source_ref=None, category=cat.label, lat=p.get("lat"), lng=p.get("lng"),
                                            query=resp.params, cache_hit=resp.cache_hit)
                    p["_evidence_id"] = eid
                    places.append(p)
                if ctx.timeline:
                    ctx.timeline[-1]["result_count"] = len(places)
            places_by_category[cat.key] = dedupe_places(places)

        # ---- PRIORITIZE (no credits) ------------------------------------
        def score(cat) -> float:
            demand = demand_by_category.get(cat.key, {}).get("trend_avg")
            supply = len(places_by_category.get(cat.key, []))
            demand_component = (demand or 20.0) / 100.0
            supply_penalty = min(1.0, supply / 15.0)
            return demand_component - 0.5 * supply_penalty

        deep_count = PRESET_DEEP_COUNT.get(request.preset, 4)
        top_categories = sorted(categories, key=score, reverse=True)[:deep_count]
        top_keys = {c.key for c in top_categories}

        # ---- SEARCH: deep (Autocomplete + Reviews for top categories) --
        autocomplete_by_category: dict[str, list[str]] = {}
        reviews_by_category: dict[str, list[dict[str, Any]]] = {}
        topics_by_category: dict[str, list[dict[str, Any]]] = {}

        for cat in top_categories:
            resp = _guarded_call(ctx, "SEARCH", f"Check what people search for '{cat.label}'", serp_client,
                                  "google_autocomplete",
                                  {"q": f"{cat.maps_query} {request.town_name}", "gl": "in", "hl": "en"})
            suggestions: list[str] = []
            if resp and resp.ok:
                suggestions = norm.normalize_autocomplete(resp.body)
                if suggestions:
                    eid = ctx.add_evidence(EvidenceKind.SUGGESTION, "google_autocomplete",
                                            f"Autocomplete suggestions for '{cat.label}'",
                                            {"suggestions": suggestions}, category=cat.label,
                                            query=resp.params, cache_hit=resp.cache_hit)
                    demand_evidence_by_category[cat.key].append(eid)
                if ctx.timeline:
                    ctx.timeline[-1]["result_count"] = len(suggestions)
            autocomplete_by_category[cat.key] = suggestions

            places = places_by_category.get(cat.key, [])
            candidates = [p for p in places if p.get("data_id") and isinstance(p.get("reviews"), int)]
            if not candidates:
                continue
            busiest = max(candidates, key=lambda p: p["reviews"])

            reviews: list[dict[str, Any]] = []
            topics: list[dict[str, Any]] = []
            for label, extra in (("default (most relevant)", {}), ("lowest-rated first", {"sort_by": "ratingLow"})):
                resp = _guarded_call(ctx, "SEARCH", f"Read what customers say about '{busiest['title']}' ({label})",
                                      serp_client, "google_maps_reviews",
                                      {"data_id": busiest["data_id"], "hl": "en", **extra})
                if not resp or not resp.ok:
                    continue
                parsed = norm.normalize_reviews(resp.body)
                for r in parsed["reviews"]:
                    eid = ctx.add_evidence(EvidenceKind.REVIEW, "google_maps_reviews",
                                            f"Review of '{busiest['title']}'", r, category=cat.label,
                                            query=resp.params, cache_hit=resp.cache_hit)
                    r["_evidence_id"] = eid
                    reviews.append(r)
                if not extra:  # topics only present on the first ("default") call
                    for t in parsed["topics"]:
                        eid = ctx.add_evidence(EvidenceKind.REVIEW_TOPIC, "google_maps_reviews",
                                                f"Review topic: {t['keyword']}", t, category=cat.label,
                                                query=resp.params, cache_hit=resp.cache_hit)
                        t["_evidence_id"] = eid
                        topics.append(t)
                if ctx.timeline:
                    ctx.timeline[-1]["result_count"] = len(parsed["reviews"])

            reviews_by_category[cat.key] = reviews
            # ---- EVIDENCE EXTRACTION (LLM: theme tagging on low-rated reviews) ---
            low_rated = [r for r in reviews if isinstance(r.get("rating"), (int, float)) and r["rating"] <= 3]
            tagged, llm_used = tag_reviews(low_rated or reviews, gemini_client)
            if llm_used:
                ctx.log_step("EVIDENCE EXTRACTION", f"Tag complaint themes for '{cat.label}' (LLM)",
                             engine="gemini", result_count=len(tagged))
            theme_counts: dict[str, list[str]] = {}
            for item in tagged:
                for theme in item.get("themes", []):
                    theme_counts.setdefault(theme, []).append(item["review_id"])
            for theme, review_ids in theme_counts.items():
                source_eids = [r["_evidence_id"] for r in reviews if r["review_id"] in review_ids]
                eid = ctx.record_computed(f"Complaint theme (LLM-derived): {theme}",
                                           {"theme": theme, "mentions": len(review_ids), "source": "llm"},
                                           source_eids)
                topics.append({"keyword": theme, "mentions": len(review_ids), "_evidence_id": eid})
            topics_by_category[cat.key] = topics

        # ---- NORMALIZATION + REASONING: build gaps per category ---------
        category_results: list[CategoryResult] = []
        all_gaps = []
        for cat in categories:
            places = places_by_category.get(cat.key, [])
            demand_info = compute_demand_index(
                trend_avg=demand_by_category.get(cat.key, {}).get("trend_avg"),
                autocomplete_suggestions=autocomplete_by_category.get(cat.key, []),
                density_per_km2=(len(places) / (3.14159 * request.radius_km ** 2)) if places else None,
            )
            hstats = hours_coverage_stats(places, cat.need_hours, cat.need_days)
            cat_result_dict, gaps = build_category_gaps(
                category=cat, radius_km=request.radius_km, places=places,
                reviews=reviews_by_category.get(cat.key, []), topics=topics_by_category.get(cat.key, []),
                demand=demand_info, demand_evidence_ids=demand_evidence_by_category.get(cat.key, []),
                hours_stats=hstats, news_items=news_items if cat.key in top_keys else [],
                record_computed=ctx.record_computed,
            )
            category_results.append(CategoryResult(**cat_result_dict))
            all_gaps.extend(gaps)

        ctx.log_step("REASONING", f"Classify gaps across {len(categories)} categories",
                     result_count=len(all_gaps))

        # ---- OUTPUT: optional LLM narrative polish, then verify ----------
        llm_used_any = False
        for gap in all_gaps:
            if gap.why_we_think_this:
                original = gap.why_we_think_this[0].text
                rewritten, used = rewrite_explanation(original, gemini_client)
                gap.why_we_think_this[0].text = rewritten
                llm_used_any = llm_used_any or used

        evidence_ids = set(ctx.evidence.keys())
        all_gaps = verify_all(all_gaps, evidence_ids)
        ctx.log_step("VERIFICATION", "Check every claim against the evidence ledger",
                     result_count=sum(g.dropped_claim_count for g in all_gaps))

        return _finalize(ctx, request, scan_id, center=center, budget=budget, serp_client=serp_client,
                          account_before=account_before, status="completed",
                          category_results=category_results, gaps=all_gaps,
                          owns_serp=owns_serp, owns_gemini=owns_gemini, gemini_client=gemini_client,
                          llm_used=llm_used_any)
    finally:
        if owns_serp:
            serp_client.close()
        if owns_gemini:
            gemini_client.close()


def _finalize(
    ctx: ScanContext, request: ScanRequest, scan_id: str, center: tuple[float, float],
    budget: BudgetManager, serp_client: SerpApiClient, account_before: Optional[dict[str, Any]],
    status: str, owns_serp: bool, owns_gemini: bool, gemini_client: GeminiClient,
    category_results: Optional[list[CategoryResult]] = None, gaps: Optional[list] = None,
    llm_used: bool = False,
) -> ScanResult:
    measured = None
    account_after = serp_client.account()
    if account_before and account_after and "total_searches_left" in account_before:
        measured = account_before["total_searches_left"] - account_after.get("total_searches_left", account_before["total_searches_left"])

    result = ScanResult(
        scan_id=scan_id, town_name=request.town_name, center_lat=center[0], center_lng=center[1],
        radius_km=request.radius_km, preset=request.preset, mode=request.mode, status=status,
        budget=budget.status(measured_spent=measured), timeline=ctx.timeline,
        category_results=category_results or [], gaps=gaps or [], evidence=ctx.evidence,
        warnings=ctx.warnings, llm_used=llm_used, llm_model=gemini_client.model if llm_used else None,
    )
    _persist(result)
    return result


def _persist(result: ScanResult) -> None:
    with get_session() as session:
        session.merge(ScanRecord(
            scan_id=result.scan_id, town_name=result.town_name, center_lat=result.center_lat,
            center_lng=result.center_lng, radius_km=result.radius_km, preset=result.preset.value,
            mode=result.mode, status=result.status, result_json=result.model_dump_json(),
        ))