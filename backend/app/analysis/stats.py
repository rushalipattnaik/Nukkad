from __future__ import annotations

import math
from typing import Optional


def supply_stats(places: list[dict], radius_km: float) -> dict:
    total = len(places)
    within_radius = [p for p in places if (p.get("distance_km") is None or p["distance_km"] <= radius_km)]
    rated = [p["rating"] for p in places if isinstance(p.get("rating"), (int, float))]
    weights = [p.get("reviews") or 1 for p in places if isinstance(p.get("rating"), (int, float))]
    mean_rating: Optional[float] = None
    if rated:
        weighted_sum = sum(r * w for r, w in zip(rated, weights))
        mean_rating = round(weighted_sum / sum(weights), 2) if sum(weights) else round(sum(rated) / len(rated), 2)
    low_rating_share = round(sum(1 for r in rated if r < 4.0) / len(rated), 3) if rated else None
    area_km2 = math.pi * radius_km ** 2
    density = round(len(within_radius) / area_km2, 3) if area_km2 else None
    return {
        "supply_count": total,
        "supply_within_radius": len(within_radius),
        "mean_rating": mean_rating,
        "low_rating_share": low_rating_share,
        "density_per_km2": density,
    }
