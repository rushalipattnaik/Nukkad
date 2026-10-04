"""
Turns per-category evidence into zero or more Gap objects.

Every claim cites at least one evidence ID. Derived numbers (like "7
pharmacies") get recorded as their own COMPUTED evidence item via
`record_computed` instead of just being asserted, so the verifier can
check them against the ledger later.

Thresholds are named constants below rather than inline magic numbers.
"""
from __future__ import annotations

import uuid
from typing import Any, Callable

from app.analysis.confidence import compute_confidence
from app.analysis.conflicts import detect_conflicts
from app.analysis.stats import supply_stats
from app.domain.schemas import Claim, ClaimType, ConfidenceLevel, Gap, GapType
from app.planner.taxonomy import CategoryDef

# ---- thresholds -------------------------------------------------------
ABSENCE_DEMAND_LEVELS = {"Medium", "High"}
ABSENCE_MAX_SUPPLY_WITHIN_RADIUS = 3

QUALITY_MIN_SUPPLY = 3
QUALITY_MIN_LOW_RATING_SHARE = 0.30
QUALITY_MIN_TOPIC_MENTIONS = 3

SERVICE_WINDOW_MIN_SUPPLY = 3
SERVICE_WINDOW_MIN_JUDGEABLE = 2
SERVICE_WINDOW_MAX_OPEN_SHARE = 0.34

RecordComputed = Callable[[str, dict[str, Any], list[str]], str]


def _gap_id() -> str:
    return f"gap_{uuid.uuid4().hex[:10]}"


def build_category_gaps(
    category: CategoryDef,
    radius_km: float,
    places: list[dict],  # each has "_evidence_id"
    reviews: list[dict],  # each has "_evidence_id"
    topics: list[dict],  # each has "_evidence_id"
    demand: dict,
    demand_evidence_ids: list[str],
    hours_stats: dict,
    news_items: list[dict],  # each has "_evidence_id"
    record_computed: RecordComputed,
) -> tuple[dict[str, Any], list[Gap]]:
    stats = supply_stats(places, radius_km)
    demand_label = demand.get("label")
    demand_is_regional = bool(demand.get("is_regional"))

    conflicts = detect_conflicts(
        demand_label=demand_label,
        supply_within_radius=stats["supply_within_radius"],
        low_rating_share=stats["low_rating_share"],
        open_in_window_share=hours_stats.get("open_in_window_share"),
        review_topics=topics,
    )

    category_result = {
        "category": category.label,
        "supply_count": stats["supply_count"],
        "supply_within_radius": stats["supply_within_radius"],
        "mean_rating": stats["mean_rating"],
        "low_rating_share": stats["low_rating_share"],
        "hours_coverage_pct": hours_stats.get("hours_coverage_pct"),
        "open_in_need_window_share": hours_stats.get("open_in_window_share"),
        "demand_label": demand_label,
        "demand_is_regional": demand_is_regional,
        "evidence_ids": [p["_evidence_id"] for p in places] + demand_evidence_ids,
    }

    gaps: list[Gap] = []
    place_evidence_ids = [p["_evidence_id"] for p in places]
    review_evidence_ids = [r["_evidence_id"] for r in reviews]
    topic_evidence_ids = [t["_evidence_id"] for t in topics]
    news_evidence_ids = [n["_evidence_id"] for n in news_items]

    def confidence_for(has_reviews: bool, has_hours: bool) -> tuple[ConfidenceLevel, list[str], list[str]]:
        return compute_confidence(
            has_supply_data=stats["supply_count"] > 0,
            sample_size=stats["supply_within_radius"],
            has_demand_data=demand_label is not None,
            demand_is_regional=demand_is_regional,
            has_review_data=has_reviews,
            has_hours_data=has_hours,
            conflict_count=len(conflicts),
        )

    # ---- ABSENCE -----------------------------------------------------
    if demand_label in ABSENCE_DEMAND_LEVELS and stats["supply_within_radius"] <= ABSENCE_MAX_SUPPLY_WITHIN_RADIUS:
        supply_evidence = record_computed(
            f"{stats['supply_within_radius']} {category.label} found within {radius_km:.0f} km",
            {"count": stats["supply_within_radius"], "radius_km": radius_km},
            place_evidence_ids,
        )
        demand_evidence = record_computed(
            f"Demand signal for '{category.label}': {demand_label}",
            {"label": demand_label, "components": demand.get("components")},
            demand_evidence_ids,
        )
        level, reasons, missing = confidence_for(has_reviews=bool(reviews), has_hours=bool(hours_stats.get("with_hours")))
        gaps.append(Gap(
            gap_id=_gap_id(), category=category.label, gap_type=GapType.ABSENCE,
            strength=round(min(1.0, (ABSENCE_MAX_SUPPLY_WITHIN_RADIUS - stats["supply_within_radius"] + 1) / 4), 2),
            confidence=level, confidence_reasons=reasons, missing_information=missing,
            what_exists=[Claim(claim_type=ClaimType.COMPUTED,
                               text=f"Only {stats['supply_within_radius']} {category.label} found within {radius_km:.0f} km.",
                               evidence_ids=[supply_evidence], verified=True)],
            what_customers_say=[],
            what_people_search=[Claim(claim_type=ClaimType.COMPUTED,
                                      text=f"Demand signal for '{category.label}' looks {demand_label}.",
                                      evidence_ids=[demand_evidence], verified=True)],
            what_is_changing=[Claim(claim_type=ClaimType.FACT, text=n.get("title", ""), evidence_ids=[eid], verified=True)
                              for n, eid in zip(news_items[:2], news_evidence_ids[:2])],
            why_we_think_this=[Claim(
                claim_type=ClaimType.INTERPRETATION,
                text=(f"Demand for '{category.label}' looks {demand_label.lower()} while very few places "
                      f"currently serve this need nearby - a possible absence gap."),
                evidence_ids=[supply_evidence, demand_evidence], verified=True,
            )],
            conflicts=conflicts,
            validate_next=["Visit the area at different times to confirm the gap in person",
                          "Talk to a few residents about whether they travel elsewhere for this"],
        ))

    # ---- QUALITY -------------------------------------------------------
    complaint_topics = [t for t in topics if t.get("mentions", 0) >= QUALITY_MIN_TOPIC_MENTIONS]
    if (stats["supply_within_radius"] >= QUALITY_MIN_SUPPLY
            and stats["low_rating_share"] is not None
            and stats["low_rating_share"] >= QUALITY_MIN_LOW_RATING_SHARE
            and complaint_topics):
        quality_evidence = record_computed(
            f"{round(stats['low_rating_share'] * 100)}% of rated {category.label} score under 4.0",
            {"low_rating_share": stats["low_rating_share"], "mean_rating": stats["mean_rating"]},
            place_evidence_ids,
        )
        level, reasons, missing = confidence_for(has_reviews=True, has_hours=bool(hours_stats.get("with_hours")))
        top_topic = max(complaint_topics, key=lambda t: t.get("mentions", 0))
        gaps.append(Gap(
            gap_id=_gap_id(), category=category.label, gap_type=GapType.QUALITY,
            strength=round(min(1.0, stats["low_rating_share"] + 0.2), 2),
            confidence=level, confidence_reasons=reasons, missing_information=missing,
            what_exists=[Claim(claim_type=ClaimType.COMPUTED,
                               text=f"{stats['supply_within_radius']} {category.label} exist within {radius_km:.0f} km.",
                               evidence_ids=[e for e in place_evidence_ids[:5]] or [quality_evidence], verified=True)],
            what_customers_say=[Claim(
                claim_type=ClaimType.INTERPRETATION,
                text=f"Repeated complaints about '{top_topic['keyword']}' ({top_topic['mentions']} mentions in low-rated reviews).",
                evidence_ids=[t["_evidence_id"] for t in complaint_topics][:3], verified=True,
            )],
            what_people_search=[],
            what_is_changing=[Claim(claim_type=ClaimType.FACT, text=n.get("title", ""), evidence_ids=[eid], verified=True)
                              for n, eid in zip(news_items[:2], news_evidence_ids[:2])],
            why_we_think_this=[Claim(
                claim_type=ClaimType.INTERPRETATION,
                text=(f"Existing {category.label} are established, but {round(stats['low_rating_share'] * 100)}% "
                      f"of rated places score under 4.0 with recurring complaints about "
                      f"'{top_topic['keyword']}' - a possible quality gap rather than an absence gap."),
                evidence_ids=[quality_evidence] + [t["_evidence_id"] for t in complaint_topics][:2], verified=True,
            )],
            conflicts=conflicts,
            validate_next=["Read the full lowest-rated reviews for these places",
                          "Check whether the complaints describe a fixable, specific problem"],
        ))

    # ---- SERVICE_WINDOW --------------------------------------------------
    open_share = hours_stats.get("open_in_window_share")
    if (stats["supply_within_radius"] >= SERVICE_WINDOW_MIN_SUPPLY
            and hours_stats.get("judgeable", 0) >= SERVICE_WINDOW_MIN_JUDGEABLE
            and open_share is not None and open_share <= SERVICE_WINDOW_MAX_OPEN_SHARE
            and category.need_hours != (0, 23)):
        window_evidence = record_computed(
            f"Only {round(open_share * 100)}% of {category.label} are open {category.need_window}",
            {"open_in_window_share": open_share, "judgeable": hours_stats["judgeable"],
             "need_window": category.need_window},
            place_evidence_ids,
        )
        level, reasons, missing = confidence_for(has_reviews=bool(reviews), has_hours=True)
        gaps.append(Gap(
            gap_id=_gap_id(), category=category.label, gap_type=GapType.SERVICE_WINDOW,
            strength=round(min(1.0, (SERVICE_WINDOW_MAX_OPEN_SHARE - open_share + 0.2) / 0.5), 2),
            confidence=level, confidence_reasons=reasons, missing_information=missing,
            what_exists=[Claim(claim_type=ClaimType.COMPUTED,
                               text=f"{stats['supply_within_radius']} {category.label} exist within {radius_km:.0f} km.",
                               evidence_ids=place_evidence_ids[:5] or [window_evidence], verified=True)],
            what_customers_say=[Claim(claim_type=ClaimType.INTERPRETATION, text=t["keyword"],
                                      evidence_ids=[t["_evidence_id"]], verified=True)
                                for t in complaint_topics[:2]],
            what_people_search=[],
            what_is_changing=[],
            why_we_think_this=[Claim(
                claim_type=ClaimType.COMPUTED,
                text=(f"Businesses exist, but only {round(open_share * 100)}% are open {category.need_window} - "
                      f"a possible service-window gap."),
                evidence_ids=[window_evidence], verified=True,
            )],
            conflicts=conflicts,
            validate_next=[f"Call ahead to confirm which {category.label} are genuinely open {category.need_window}"],
        ))

    return category_result, gaps
