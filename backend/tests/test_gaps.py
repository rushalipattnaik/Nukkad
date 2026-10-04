from __future__ import annotations

from app.analysis.conflicts import detect_conflicts
from app.analysis.demand import (
    autocomplete_need_score,
    compute_demand_index,
    extract_trend_average,
)
from app.analysis.gaps import build_category_gaps
from app.analysis.stats import supply_stats
from app.domain.schemas import GapType
from app.planner.taxonomy import BY_KEY


def test_extract_trend_average():
    timeline = [
        {"values": [{"query": "gym", "value": 10}, {"query": "dentist", "value": 40}]},
        {"values": [{"query": "gym", "value": 20}, {"query": "dentist", "value": 60}]},
    ]
    assert extract_trend_average(timeline, "gym") == 15.0
    assert extract_trend_average(timeline, "dentist") == 50.0
    assert extract_trend_average(timeline, "missing") is None


def test_autocomplete_need_score_detects_urgency_phrases():
    assert autocomplete_need_score(["medical store open 24 hours", "medical store near me", "medical store price"]) > 0
    assert autocomplete_need_score([]) is None


def test_demand_index_all_signals_missing():
    result = compute_demand_index(None, [], None)
    assert result["label"] is None
    assert result["is_regional"] is False


def test_demand_index_high_when_all_signals_strong():
    result = compute_demand_index(90.0, ["x open 24 hours", "x near me", "x home delivery"], 4.0)
    assert result["label"] == "High"
    assert result["is_regional"] is True


def test_supply_stats_weighted_rating_and_density():
    places = [
        {"rating": 5.0, "reviews": 100, "distance_km": 1.0},
        {"rating": 2.0, "reviews": 10, "distance_km": 2.0},
    ]
    stats = supply_stats(places, radius_km=3.0)
    assert stats["supply_count"] == 2
    assert stats["supply_within_radius"] == 2
    # weighted mean: (5*100 + 2*10) / 110 = 4.7272...
    assert abs(stats["mean_rating"] - 4.73) < 0.02
    assert stats["low_rating_share"] == 0.5


def test_conflict_c1_high_demand_high_saturation():
    flags = detect_conflicts(demand_label="High", supply_within_radius=12, low_rating_share=None,
                             open_in_window_share=None, review_topics=[])
    assert any(f.rule_id == "C1" for f in flags)


def test_conflict_c3_low_demand_low_supply():
    flags = detect_conflicts(demand_label="Low", supply_within_radius=1, low_rating_share=None,
                             open_in_window_share=None, review_topics=[])
    assert any(f.rule_id == "C3" for f in flags)


def test_no_conflicts_when_signals_agree():
    flags = detect_conflicts(demand_label="High", supply_within_radius=1, low_rating_share=None,
                             open_in_window_share=None, review_topics=[])
    assert flags == []


def _fake_places(n: int, rating: float = 4.5, with_hours=True) -> list[dict]:
    out = []
    for i in range(n):
        out.append({
            "_evidence_id": f"E-PLACE-{i}", "title": f"Shop {i}", "rating": rating, "reviews": 20,
            "distance_km": 0.5, "operating_hours": {"monday": "9 AM-8 PM"} if with_hours else {},
        })
    return out


def test_absence_gap_fires_on_high_demand_low_supply():
    category = BY_KEY["medical_store"]
    places = _fake_places(1)
    demand = {"label": "High", "is_regional": True, "components": {}}
    computed_ids = []

    def record_computed(title, data, derived_from):
        eid = f"E-COMPUTED-{len(computed_ids)}"
        computed_ids.append(eid)
        return eid

    cat_result, gaps = build_category_gaps(
        category=category, radius_km=3.0, places=places, reviews=[], topics=[],
        demand=demand, demand_evidence_ids=["E-TREND-1"],
        hours_stats={"total": 1, "with_hours": 1, "hours_coverage_pct": 100.0, "judgeable": 0,
                    "open_in_window": 0, "open_in_window_share": None},
        news_items=[], record_computed=record_computed,
    )
    assert any(g.gap_type == GapType.ABSENCE for g in gaps)
    absence = next(g for g in gaps if g.gap_type == GapType.ABSENCE)
    assert absence.what_exists[0].evidence_ids  # every claim must cite evidence
    assert all(eid for claim in absence.why_we_think_this for eid in claim.evidence_ids)


def test_no_absence_gap_when_supply_is_ample():
    category = BY_KEY["medical_store"]
    places = _fake_places(10)
    demand = {"label": "High", "is_regional": True, "components": {}}

    cat_result, gaps = build_category_gaps(
        category=category, radius_km=3.0, places=places, reviews=[], topics=[],
        demand=demand, demand_evidence_ids=[],
        hours_stats={"total": 10, "with_hours": 10, "hours_coverage_pct": 100.0, "judgeable": 0,
                    "open_in_window": 0, "open_in_window_share": None},
        news_items=[], record_computed=lambda t, d, f: "E-X",
    )
    assert not any(g.gap_type == GapType.ABSENCE for g in gaps)


def test_quality_gap_fires_on_low_ratings_and_complaint_topic():
    category = BY_KEY["gym"]
    places = _fake_places(5, rating=3.0)
    topics = [{"keyword": "rude staff", "mentions": 5, "_evidence_id": "E-TOPIC-1"}]
    demand = {"label": "Medium", "is_regional": False, "components": {}}

    cat_result, gaps = build_category_gaps(
        category=category, radius_km=3.0, places=places, reviews=[{"_evidence_id": "E-REVIEW-1"}],
        topics=topics, demand=demand, demand_evidence_ids=["E-AC-1"],
        hours_stats={"total": 5, "with_hours": 5, "hours_coverage_pct": 100.0, "judgeable": 5,
                    "open_in_window": 5, "open_in_window_share": 1.0},
        news_items=[], record_computed=lambda t, d, f: "E-COMPUTED-Q",
    )
    assert any(g.gap_type == GapType.QUALITY for g in gaps)


def test_service_window_gap_fires_when_few_open_in_need_window():
    category = BY_KEY["medical_store"]  # need_hours = (21, 6)
    places = _fake_places(5, with_hours=True)
    demand = {"label": "Medium", "is_regional": False, "components": {}}

    cat_result, gaps = build_category_gaps(
        category=category, radius_km=3.0, places=places, reviews=[], topics=[],
        demand=demand, demand_evidence_ids=[],
        hours_stats={"total": 5, "with_hours": 5, "hours_coverage_pct": 100.0, "judgeable": 5,
                    "open_in_window": 1, "open_in_window_share": 0.2},
        news_items=[], record_computed=lambda t, d, f: "E-COMPUTED-SW",
    )
    assert any(g.gap_type == GapType.SERVICE_WINDOW for g in gaps)


def test_every_claim_in_every_gap_has_evidence_ids():
    category = BY_KEY["medical_store"]
    places = _fake_places(1)
    demand = {"label": "High", "is_regional": True, "components": {}}

    _, gaps = build_category_gaps(
        category=category, radius_km=3.0, places=places, reviews=[], topics=[],
        demand=demand, demand_evidence_ids=["E-TREND-1"],
        hours_stats={"total": 1, "with_hours": 1, "hours_coverage_pct": 100.0, "judgeable": 0,
                    "open_in_window": 0, "open_in_window_share": None},
        news_items=[], record_computed=lambda t, d, f: "E-COMPUTED-X",
    )
    for gap in gaps:
        for field in ("what_exists", "what_customers_say", "what_people_search", "what_is_changing", "why_we_think_this"):
            for claim in getattr(gap, field):
                assert claim.evidence_ids, f"claim without evidence: {claim.text}"
