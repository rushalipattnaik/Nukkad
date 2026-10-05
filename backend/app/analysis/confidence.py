from __future__ import annotations

from app.domain.schemas import ConfidenceLevel


def compute_confidence(
    *,
    has_supply_data: bool,
    sample_size: int,
    has_demand_data: bool,
    demand_is_regional: bool,
    has_review_data: bool,
    has_hours_data: bool,
    conflict_count: int,
) -> tuple[ConfidenceLevel, list[str], list[str]]:
    """Returns (level, reasons_supporting_the_level, missing_information)."""
    score = 0.0
    reasons: list[str] = []
    missing: list[str] = []

    if has_supply_data and sample_size >= 5:
        score += 0.30
        reasons.append(f"Supply data available for {sample_size} places")
    elif has_supply_data:
        score += 0.15
        reasons.append(f"Only {sample_size} places found nearby - a small sample")
        missing.append("Few places were found; try a wider radius for a firmer read")
    else:
        missing.append("No usable supply (Maps) data")

    if has_demand_data:
        if demand_is_regional:
            score += 0.15
            reasons.append("Demand signal available, but partly regional (country-level Trends)")
            missing.append("Demand includes a country-level Trends signal, not town-level")
        else:
            score += 0.25
            reasons.append("Demand signal available from local sources")
    else:
        missing.append("No demand signal (Trends/Autocomplete) could be retrieved")

    if has_review_data:
        score += 0.20
        reasons.append("Customer review data available")
    else:
        missing.append("No review data available for this category")

    if has_hours_data:
        score += 0.15
        reasons.append("Opening-hours data available for at least some places")
    else:
        missing.append("Opening-hours data was not available")

    if conflict_count == 0:
        score += 0.10
        reasons.append("No conflicting signals detected")
    else:
        score -= 0.05 * conflict_count
        reasons.append(f"{conflict_count} conflicting signal(s) detected - see 'Signals disagree'")

    score = max(0.0, min(1.0, score))
    if score >= 0.65:
        level = ConfidenceLevel.HIGH
    elif score >= 0.35:
        level = ConfidenceLevel.MEDIUM
    else:
        level = ConfidenceLevel.LOW
    return level, reasons, missing