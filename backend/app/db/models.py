from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SerpCache(Base):
    """Our own cross-session cache. SerpApi's own cache only lasts an hour;
    this one respects the per-engine TTLs in config.py so we don't re-spend
    credits across separate scans within the same week/day/month."""

    __tablename__ = "serp_cache"

    cache_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    engine: Mapped[str] = mapped_column(String(64), index=True)
    params_json: Mapped[str] = mapped_column(Text)  # never contains api_key
    response_json: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(default=utcnow)
    ttl_seconds: Mapped[int] = mapped_column(Integer)


class ScanRecord(Base):
    """One row per scan, storing the full ScanResult as JSON for simple
    retrieval by the history and detail endpoints."""

    __tablename__ = "scans"

    scan_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    town_name: Mapped[str] = mapped_column(String(160))
    center_lat: Mapped[float] = mapped_column(Float)
    center_lng: Mapped[float] = mapped_column(Float)
    radius_km: Mapped[float] = mapped_column(Float)
    preset: Mapped[str] = mapped_column(String(20))
    mode: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="completed")
    created_at: Mapped[datetime] = mapped_column(default=utcnow, index=True)
    result_json: Mapped[str] = mapped_column(Text)  # full ScanResult, JSON-encoded


class SavedGap(Base):
    __tablename__ = "saved_gaps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scan_id: Mapped[str] = mapped_column(String(40), index=True)
    gap_id: Mapped[str] = mapped_column(String(80))
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class DailyCreditUsage(Base):
    """One row per calendar day (UTC), used to enforce NUKKAD_DAILY_CREDIT_CAP
    so a publicly-hosted demo can't silently burn through your SerpApi plan."""

    __tablename__ = "daily_credit_usage"

    day: Mapped[str] = mapped_column(String(10), primary_key=True)  # "YYYY-MM-DD"
    counted_calls: Mapped[int] = mapped_column(Integer, default=0)
