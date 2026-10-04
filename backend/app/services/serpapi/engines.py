"""
Turns raw SerpApi response bodies into plain dicts with a stable shape,
since not every optional field comes back on every request.

Field names match SerpApi's documented response as of Sept 2026 - if they
change something, this is the one file to update.
"""
from __future__ import annotations

import math
import re
from typing import Any, Optional

from app.core.security import sanitize_text

_NON_ASCII_SPACE = re.compile(r"[\u202f\u00a0]")  # narrow no-break space, no-break space


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def normalize_hour_string(s: str) -> str:
    """SerpApi hour strings can contain narrow no-break spaces and an
    en/em-dash. Normalize to plain ASCII-ish text for robust parsing."""
    s = _NON_ASCII_SPACE.sub(" ", s)
    s = s.replace("\u2013", "-").replace("\u2014", "-").replace("\u22c5", "|")
    return s.strip()


def normalize_place(raw: dict[str, Any], center: tuple[float, float]) -> Optional[dict[str, Any]]:
    if not isinstance(raw, dict) or not raw.get("title"):
        return None
    coords = raw.get("gps_coordinates") or {}
    lat, lng = coords.get("latitude"), coords.get("longitude")
    distance_km = None
    if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
        distance_km = round(haversine_km(center[0], center[1], lat, lng), 3)

    hours_raw = raw.get("operating_hours")
    hours: dict[str, str] = {}
    if isinstance(hours_raw, dict):
        for day, val in hours_raw.items():
            if isinstance(val, str):
                hours[day.lower()] = normalize_hour_string(val)

    place_id = raw.get("data_id") or raw.get("place_id") or raw.get("data_cid")
    if not place_id:
        return None

    return {
        "place_id": str(place_id),
        "data_id": raw.get("data_id"),
        "title": sanitize_text(raw.get("title"), 200),
        "lat": lat,
        "lng": lng,
        "distance_km": distance_km,
        "rating": raw.get("rating") if isinstance(raw.get("rating"), (int, float)) else None,
        "reviews": raw.get("reviews") if isinstance(raw.get("reviews"), int) else None,
        "type": sanitize_text(raw.get("type"), 80) if raw.get("type") else None,
        "types": [sanitize_text(t, 80) for t in (raw.get("types") or []) if isinstance(t, str)],
        "address": sanitize_text(raw.get("address"), 300),
        "open_state_text": sanitize_text(raw.get("open_state") or raw.get("hours"), 120),
        "operating_hours": hours,
        "unclaimed_listing": bool(raw.get("unclaimed_listing")),
    }


def normalize_maps_search(body: dict[str, Any], center: tuple[float, float]) -> list[dict[str, Any]]:
    rows = body.get("local_results")
    if not isinstance(rows, list):
        return []
    out = []
    for raw in rows:
        norm = normalize_place(raw, center)
        if norm:
            out.append(norm)
    return out


def normalize_geocode(body: dict[str, Any]) -> Optional[tuple[float, float]]:
    place = body.get("place_results")
    if isinstance(place, dict):
        coords = place.get("gps_coordinates") or {}
        lat, lng = coords.get("latitude"), coords.get("longitude")
        if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
            return (lat, lng)
    return None


def normalize_review(raw: dict[str, Any]) -> Optional[dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    snippet = raw.get("snippet")
    extracted = raw.get("extracted_snippet") or {}
    text = extracted.get("original") if isinstance(extracted, dict) else None
    text = text or snippet
    rating = raw.get("rating")
    return {
        "review_id": raw.get("review_id") or raw.get("link"),
        "rating": rating if isinstance(rating, (int, float)) else None,
        "text": sanitize_text(text, 2000) if text else "",
        "iso_date": raw.get("iso_date"),
        "source": raw.get("source") if isinstance(raw.get("source"), str) else "Google",
        # Reviewer identity is intentionally dropped - never stored, never
        # sent to the LLM. Only non-identifying stats are kept.
        "reviewer_is_local_guide": bool(((raw.get("user") or {}).get("local_guide"))),
    }


def normalize_reviews(body: dict[str, Any]) -> dict[str, Any]:
    reviews_raw = body.get("reviews")
    reviews = []
    if isinstance(reviews_raw, list):
        for r in reviews_raw:
            norm = normalize_review(r)
            if norm and norm["text"]:
                reviews.append(norm)
    topics_raw = body.get("topics")
    topics = []
    if isinstance(topics_raw, list):
        for t in topics_raw:
            if isinstance(t, dict) and t.get("keyword"):
                topics.append({
                    "keyword": sanitize_text(t.get("keyword"), 60),
                    "mentions": t.get("mentions") if isinstance(t.get("mentions"), int) else 0,
                })
    return {"reviews": reviews, "topics": topics}


def normalize_trends_timeseries(body: dict[str, Any]) -> dict[str, Any]:
    timeline = ((body.get("interest_over_time") or {}).get("timeline_data")) or []
    points = timeline if isinstance(timeline, list) else []
    return {"points": len(points), "raw_timeline": points}


def normalize_trends_geo_map(body: dict[str, Any]) -> list[dict[str, Any]]:
    rows = body.get("compared_breakdown_by_region") or body.get("interest_by_region") or []
    out = []
    if isinstance(rows, list):
        for r in rows:
            if isinstance(r, dict) and r.get("location"):
                out.append({
                    "location": sanitize_text(r.get("location"), 80),
                    "values": r.get("values") if isinstance(r.get("values"), list) else [],
                })
    return out


def normalize_related_queries(body: dict[str, Any]) -> dict[str, list[str]]:
    related = body.get("related_queries") or {}
    if not isinstance(related, dict):
        return {"rising": [], "top": []}

    def extract(key: str) -> list[str]:
        rows = related.get(key) or []
        return [sanitize_text(r.get("query"), 100) for r in rows if isinstance(r, dict) and r.get("query")]

    return {"rising": extract("rising"), "top": extract("top")}


def normalize_autocomplete(body: dict[str, Any]) -> list[str]:
    rows = body.get("suggestions") or []
    out = []
    if isinstance(rows, list):
        for r in rows:
            if isinstance(r, dict) and r.get("value"):
                out.append(sanitize_text(r.get("value"), 120))
    return out


def normalize_news(body: dict[str, Any]) -> list[dict[str, Any]]:
    rows = body.get("news_results") or []
    out = []
    if isinstance(rows, list):
        for r in rows:
            if not isinstance(r, dict) or not r.get("title"):
                continue
            source = r.get("source")
            source_name = source.get("name") if isinstance(source, dict) else source
            out.append({
                "title": sanitize_text(r.get("title"), 200),
                "source": sanitize_text(source_name, 80) if source_name else None,
                "link": r.get("link") if isinstance(r.get("link"), str) else None,
                "date": r.get("published_at") or r.get("date"),
                "snippet": sanitize_text(r.get("snippet"), 400) if r.get("snippet") else "",
            })
    return out
