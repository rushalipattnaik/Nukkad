from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging_utils import get_logger
from app.core.rate_limit import limiter
from app.db.database import get_session
from app.db.models import SavedGap, ScanRecord
from app.domain.schemas import ScanRequest, ScanResult
from app.export.markdown_export import to_markdown
from app.orchestrator.orchestrator import PRESET_CAPS, run_scan
from app.planner.taxonomy import DEFAULT_TAXONOMY
from app.services.serpapi.client import SerpApiClient
from app.services.serpapi.engines import normalize_geocode

logger = get_logger(__name__)
router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "serpapi_configured": bool(settings.serpapi_api_key),
        "gemini_configured": bool(settings.gemini_api_key and settings.gemini_model),
    }


@router.get("/taxonomy")
def taxonomy() -> dict[str, Any]:
    return {"categories": [{"key": c.key, "label": c.label, "need_window": c.need_window} for c in DEFAULT_TAXONOMY]}


@router.get("/budget/presets")
def budget_presets() -> dict[str, Any]:
    return {
        "presets": [{"preset": p.value, "max_credits": cap} for p, cap in PRESET_CAPS.items()],
        "daily_cap": settings.daily_credit_cap,
    }


@router.get("/account")
def account() -> dict[str, Any]:
    if not settings.serpapi_api_key:
        raise HTTPException(400, "SERPAPI_API_KEY is not configured on the server.")
    client = SerpApiClient(settings.serpapi_api_key)
    try:
        data = client.account()
    finally:
        client.close()
    if not data:
        raise HTTPException(502, "Could not reach the SerpApi account endpoint.")
    # Never forward the echoed key/email to the frontend.
    data.pop("api_key", None)
    data.pop("account_email", None)
    data.pop("account_id", None)
    return data


class GeocodeRequest(BaseModel):
    town_name: str = Field(..., min_length=2, max_length=120)


@router.post("/geocode")
@limiter.limit("20/minute")
def geocode(request: Request, req: GeocodeRequest) -> dict[str, Any]:
    if not settings.serpapi_api_key:
        raise HTTPException(400, "SERPAPI_API_KEY is not configured on the server.")
    client = SerpApiClient(settings.serpapi_api_key)
    try:
        resp = client.call("google_maps", {"type": "search", "q": req.town_name, "hl": "en"})
    finally:
        client.close()
    if not resp.ok:
        raise HTTPException(502, f"SerpApi error: {resp.error}")
    center = normalize_geocode(resp.body)
    if not center:
        raise HTTPException(404, f"Could not locate '{req.town_name}'.")
    return {"lat": center[0], "lng": center[1], "cache_hit": resp.cache_hit}


@router.post("/scans", response_model=ScanResult)
@limiter.limit(f"{settings.scan_rate_limit_per_hour}/hour")
def create_scan(request: Request, req: ScanRequest) -> ScanResult:
    if not settings.serpapi_api_key:
        raise HTTPException(400, "SERPAPI_API_KEY is not configured on the server. Add it to .env and restart.")
    try:
        return run_scan(req)
    except Exception as exc:  # noqa: BLE001 - convert to a clean HTTP error
        logger.exception("Scan failed")
        raise HTTPException(500, f"Scan failed: {exc}") from exc


@router.get("/scans")
def list_scans(limit: int = 20) -> dict[str, Any]:
    with get_session() as session:
        from sqlalchemy import select

        rows = session.execute(
            select(ScanRecord).order_by(ScanRecord.created_at.desc()).limit(min(limit, 50))
        ).scalars().all()
        return {
            "scans": [
                {
                    "scan_id": r.scan_id, "town_name": r.town_name, "preset": r.preset,
                    "status": r.status, "created_at": r.created_at.isoformat(),
                }
                for r in rows
            ]
        }


@router.get("/scans/{scan_id}", response_model=ScanResult)
def get_scan(scan_id: str) -> ScanResult:
    with get_session() as session:
        row = session.get(ScanRecord, scan_id)
        if not row:
            raise HTTPException(404, "Scan not found")
        return ScanResult.model_validate_json(row.result_json)


@router.get("/scans/{scan_id}/export")
def export_scan(scan_id: str, format: str = "md") -> Response:
    with get_session() as session:
        row = session.get(ScanRecord, scan_id)
        if not row:
            raise HTTPException(404, "Scan not found")
        result = ScanResult.model_validate_json(row.result_json)
    if format != "md":
        raise HTTPException(400, "Only format=md is supported.")
    body = to_markdown(result)
    return Response(content=body, media_type="text/markdown",
                     headers={"Content-Disposition": f'attachment; filename="{scan_id}.md"'})


class SaveGapRequest(BaseModel):
    scan_id: str
    gap_id: str
    note: str = ""


@router.post("/saved")
def save_gap(req: SaveGapRequest) -> dict[str, Any]:
    with get_session() as session:
        session.add(SavedGap(scan_id=req.scan_id, gap_id=req.gap_id, note=req.note[:2000]))
    return {"saved": True}


@router.get("/saved")
def list_saved() -> dict[str, Any]:
    with get_session() as session:
        from sqlalchemy import select

        rows = session.execute(select(SavedGap).order_by(SavedGap.created_at.desc())).scalars().all()
        return {"saved": [{"id": r.id, "scan_id": r.scan_id, "gap_id": r.gap_id, "note": r.note} for r in rows]}


@router.delete("/saved/{item_id}")
def delete_saved(item_id: int) -> dict[str, Any]:
    with get_session() as session:
        row = session.get(SavedGap, item_id)
        if row:
            session.delete(row)
    return {"deleted": True}