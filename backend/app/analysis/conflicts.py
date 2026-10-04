"""
Plain comparisons between already-computed numbers - no LLM involved in
deciding whether a conflict exists. See docs/gap-methodology.md for the
full rule table.
"""
from __future__ import annotations

from app.domain.schemas import ConflictFlag

HOURS_COMPLAINT_KEYWORDS = ("closing", "closed", "hours", "timing", "availability", "open")


def detect_conflicts(
    *,
    demand_label: str | None,
    supply_within_radius: int,
    low_rating_share: float | None,
    open_in_window_share: float | None,
    review_topics: list[dict],
) -> list[ConflictFlag]:
    flags: list[ConflictFlag] = []

    if demand_label == "High" and supply_within_radius >= 10:
        flags.append(ConflictFlag(
            rule_id="C1",
            label="High demand, high saturation",
            explanation=(
                f"Demand looks High while {supply_within_radius} places already serve this area. "
                "The opportunity, if any, is more likely about a specific unmet need than about a raw shortage."
            ),
            confidence_delta=-0.05,
            validate_next=["Check whether existing places are differentiated, full, or turning customers away"],
        ))

    if demand_label == "High" and low_rating_share is not None and low_rating_share >= 0.40:
        flags.append(ConflictFlag(
            rule_id="C2",
            label="High demand, poor satisfaction",
            explanation=(
                f"Demand looks High, and {round(low_rating_share * 100)}% of rated places score under 4.0. "
                "This usually points to a quality gap rather than an absence gap."
            ),
            confidence_delta=0.0,
            validate_next=["Read the lowest-rated reviews to see whether the complaints are addressable"],
        ))

    if demand_label == "Low" and supply_within_radius <= 2:
        flags.append(ConflictFlag(
            rule_id="C3",
            label="Low supply, low demand",
            explanation=(
                "Both supply and demand signals are low. The absence of this category may simply be "
                "justified by low local need, not an opportunity."
            ),
            confidence_delta=-0.10,
            validate_next=["Validate demand independently (ask around) before treating this as a gap"],
        ))

    if open_in_window_share is not None and open_in_window_share >= 0.5:
        complaint_mentions = sum(
            t.get("mentions", 0) for t in review_topics
            if any(k in str(t.get("keyword", "")).lower() for k in HOURS_COMPLAINT_KEYWORDS)
        )
        if complaint_mentions >= 3:
            flags.append(ConflictFlag(
                rule_id="C4",
                label="Listing hours and reviews disagree",
                explanation=(
                    "Maps' own hours data suggests most places ARE open during the need window, but "
                    "customer reviews repeatedly mention hours/availability problems. Listed hours may "
                    "not reflect what actually happens."
                ),
                confidence_delta=-0.10,
                validate_next=["Call ahead or visit in person to confirm actual opening hours"],
            ))

    return flags
