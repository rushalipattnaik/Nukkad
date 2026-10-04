from __future__ import annotations

from typing import Any


def dedupe_places(all_places: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Multiple grid-cell calls for the same category will re-return the
    same nearby places. Dedupe by place_id, keeping the record closest to
    the town centre (smallest distance_km) since it's likely the most
    representative fetch."""
    best: dict[str, dict[str, Any]] = {}
    for p in all_places:
        pid = p.get("place_id")
        if not pid:
            continue
        current = best.get(pid)
        if current is None:
            best[pid] = p
            continue
        cur_d = current.get("distance_km")
        new_d = p.get("distance_km")
        if new_d is not None and (cur_d is None or new_d < cur_d):
            best[pid] = p
    return list(best.values())
