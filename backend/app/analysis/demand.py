"""
Demand index: a composite of up to three optional signals -
Trends interest (regional, country-level by default), Autocomplete
need-phrases (local, tied to the town name in the query), and review-volume
density (local, from Maps). Missing signals are just excluded rather than
zeroed out.

This is a heuristic, not a real demand model, so `is_regional` flags
whether the Trends component contributed - the UI uses it to disclose when
a reading isn't purely local.
"""
from __future__ import annotations

from typing import Any, Optional

NEED_SIGNAL_KEYWORDS = [
    "open now", "open 24", "24 hours", "near me", "home delivery",
    "night", "emergency", "online", "delivery", "book appointment",
]


def extract_trend_average(raw_timeline: list[dict[str, Any]], term: str) -> Optional[float]:
    """raw_timeline entries look like {"values": [{"query": "...", "value": N}, ...]}.
    Returns the mean value for the given term across all timeline points, or
    None if the term never appears (e.g. Trends returned nothing usable)."""
    values: list[float] = []
    term_lower = term.strip().lower()
    for point in raw_timeline:
        for v in point.get("values", []) if isinstance(point, dict) else []:
            if not isinstance(v, dict):
                continue
            q = str(v.get("query", "")).strip().lower()
            val = v.get("extracted_value", v.get("value"))
            if q == term_lower and isinstance(val, (int, float)):
                values.append(float(val))
    if not values:
        return None
    return sum(values) / len(values)


def autocomplete_need_score(suggestions: list[str]) -> Optional[float]:
    if not suggestions:
        return None
    hits = sum(1 for s in suggestions if any(k in s.lower() for k in NEED_SIGNAL_KEYWORDS))
    return min(1.0, hits / max(3, len(suggestions)))


def review_density_score(density_per_km2: Optional[float]) -> Optional[float]:
    if density_per_km2 is None:
        return None
    # Heuristic reference point: 5 reviewed places per km^2 reads as "High"
    # local review activity in a small town context. This constant is a
    # design choice, documented here rather than hidden in a magic number.
    return min(1.0, density_per_km2 / 5.0)


def compute_demand_index(
    trend_avg: Optional[float],
    autocomplete_suggestions: list[str],
    density_per_km2: Optional[float],
) -> dict[str, Any]:
    components: dict[str, Optional[float]] = {
        "trend": (trend_avg / 100.0) if trend_avg is not None else None,
        "autocomplete_need": autocomplete_need_score(autocomplete_suggestions),
        "review_density": review_density_score(density_per_km2),
    }
    available = {k: v for k, v in components.items() if v is not None}
    if not available:
        return {"label": None, "score": None, "is_regional": False, "components": components}

    score = sum(available.values()) / len(available)
    if score < 0.30:
        label = "Low"
    elif score < 0.60:
        label = "Medium"
    else:
        label = "High"
    is_regional = components["trend"] is not None
    return {"label": label, "score": round(score, 3), "is_regional": is_regional, "components": components}
