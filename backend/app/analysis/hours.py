"""
Parses the per-weekday hour strings SerpApi's Maps engine returns, e.g.
"10 AM-5 AM", "Open 24 hours", "Closed" (already normalized from the raw
"10 AM\u20135 AM" by engines.normalize_hour_string).

Everything downstream only sees (start, end) tuples on a 0-24 clock, with
overnight ranges pushed past 24 (22:00-05:00 -> (22.0, 29.0)) so overlap
math doesn't need special-casing. If SerpApi changes this format, only this
file needs to change.
"""
from __future__ import annotations

import re
from typing import Optional

_TIME_RE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*([AaPp][Mm])")


def _parse_clock(token: str) -> Optional[float]:
    m = _TIME_RE.search(token)
    if not m:
        return None
    hour = int(m.group(1)) % 12
    minute = int(m.group(2)) if m.group(2) else 0
    if m.group(3).lower() == "pm":
        hour += 12
    return hour + minute / 60.0


def parse_hour_string(text: str) -> list[tuple[float, float]]:
    """Returns a list of (start, end) intervals on a 0-24(+) clock.
    Unparseable or missing text returns an empty list (treated as unknown,
    not as closed)."""
    if not text:
        return []
    t = text.strip().lower()
    if "24 hours" in t or t == "open":
        return [(0.0, 24.0)]
    if "closed" in t:
        return []

    intervals: list[tuple[float, float]] = []
    # A day can have more than one range, e.g. "9 AM-1 PM, 4 PM-8 PM".
    for chunk in re.split(r",|;", text):
        parts = re.split(r"-", chunk)
        if len(parts) != 2:
            continue
        start = _parse_clock(parts[0])
        end = _parse_clock(parts[1])
        if start is None or end is None:
            continue
        if end <= start:
            end += 24.0  # crosses midnight
        intervals.append((start, end))
    return intervals


def _need_window_intervals(need_hours: tuple[int, int]) -> list[tuple[float, float]]:
    start, end = float(need_hours[0]), float(need_hours[1])
    if end <= start:
        end += 24.0
    return [(start, end)]


def _overlaps(a: tuple[float, float], b: tuple[float, float]) -> bool:
    # Compare on a doubled 48h timeline so midnight-wrapping ranges compare
    # correctly regardless of which one wraps.
    a_variants = [a, (a[0] + 24, a[1] + 24)]
    b_variants = [b, (b[0] + 24, b[1] + 24)]
    for av in a_variants:
        for bv in b_variants:
            if av[0] < bv[1] and bv[0] < av[1]:
                return True
    return False


def is_open_during_need_window(
    operating_hours: dict[str, str],
    need_hours: tuple[int, int],
    need_days: tuple[str, ...],
) -> Optional[bool]:
    """Returns True/False if we have enough hours data for the relevant
    days to judge, or None if we don't (so the caller can exclude this place
    from the coverage percentage rather than silently counting it as
    closed)."""
    need_intervals = _need_window_intervals(need_hours)
    relevant_days = [d for d in need_days if d in operating_hours]
    if not relevant_days:
        return None
    for day in relevant_days:
        day_intervals = parse_hour_string(operating_hours[day])
        for need_iv in need_intervals:
            for day_iv in day_intervals:
                if _overlaps(need_iv, day_iv):
                    return True
    return False


def hours_coverage_stats(
    places: list[dict], need_hours: tuple[int, int], need_days: tuple[str, ...]
) -> dict:
    total = len(places)
    with_hours = [p for p in places if p.get("operating_hours")]
    judgeable = []
    open_in_window = 0
    for p in with_hours:
        verdict = is_open_during_need_window(p["operating_hours"], need_hours, need_days)
        if verdict is None:
            continue
        judgeable.append(p)
        if verdict:
            open_in_window += 1
    return {
        "total": total,
        "with_hours": len(with_hours),
        "hours_coverage_pct": round(100 * len(with_hours) / total, 1) if total else None,
        "judgeable": len(judgeable),
        "open_in_window": open_in_window,
        "open_in_window_share": round(open_in_window / len(judgeable), 3) if judgeable else None,
    }
