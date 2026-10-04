"""
Pydantic models used across the app. These are the "shapes" that flow
between the SerpApi service, the deterministic analysis engine, the LLM
agents, the database, and the API layer.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------
class ScanPreset(str, Enum):
    lite = "lite"
    standard = "standard"
    deep = "deep"


class ScanRequest(BaseModel):
    town_name: str = Field(..., min_length=2, max_length=120)
    radius_km: float = Field(3.0, ge=1.0, le=15.0)
    preset: ScanPreset = ScanPreset.standard
    categories: Optional[list[str]] = None  # None => use the default taxonomy
    center_lat: Optional[float] = Field(None, ge=-90, le=90)
    center_lng: Optional[float] = Field(None, ge=-180, le=180)
    mode: str = Field("live", pattern="^(live|snapshot)$")
    snapshot_id: Optional[str] = None

    @field_validator("town_name")
    @classmethod
    def _clean_town(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("town_name cannot be blank")
        # Keep it to plausible place-name characters only.
        import re

        if not re.fullmatch(r"[A-Za-z0-9À-ÿ .,'()/-]{2,120}", v):
            raise ValueError("town_name contains unsupported characters")
        return v

    @field_validator("categories")
    @classmethod
    def _clean_categories(cls, v: Optional[list[str]]) -> Optional[list[str]]:
        if v is None:
            return v
        if len(v) > 30:
            raise ValueError("too many categories requested")
        return [c.strip()[:60] for c in v if c.strip()]


# ---------------------------------------------------------------------------
# Evidence
# ---------------------------------------------------------------------------
class EvidenceKind(str, Enum):
    PLACE = "PLACE"
    REVIEW = "REVIEW"
    REVIEW_TOPIC = "REVIEW_TOPIC"
    TREND_SERIES = "TREND_SERIES"
    TREND_REGION = "TREND_REGION"
    RELATED_QUERY = "RELATED_QUERY"
    SUGGESTION = "SUGGESTION"
    NEWS_ITEM = "NEWS_ITEM"
    COMPUTED = "COMPUTED"


class EvidenceItem(BaseModel):
    evidence_id: str
    scan_id: str
    kind: EvidenceKind
    engine: str  # "google_maps" | "google_maps_reviews" | ... | "nukkad_compute"
    query: dict[str, Any] = Field(default_factory=dict)
    retrieved_at: datetime = Field(default_factory=utcnow)
    cache_hit: bool = False
    title: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    source_ref: Optional[str] = None
    category: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    derived_from: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Claims / verification
# ---------------------------------------------------------------------------
class ClaimType(str, Enum):
    FACT = "FACT"
    COMPUTED = "COMPUTED"
    INTERPRETATION = "INTERPRETATION"
    UNCERTAIN = "UNCERTAIN"


class Claim(BaseModel):
    claim_type: ClaimType
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    verified: bool = False
    drop_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Gaps / conflicts
# ---------------------------------------------------------------------------
class GapType(str, Enum):
    ABSENCE = "ABSENCE"
    QUALITY = "QUALITY"
    SERVICE_WINDOW = "SERVICE_WINDOW"


class ConfidenceLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ConflictFlag(BaseModel):
    rule_id: str
    label: str
    explanation: str
    confidence_delta: float
    validate_next: list[str] = Field(default_factory=list)


class Gap(BaseModel):
    gap_id: str
    category: str
    gap_type: GapType
    strength: float = Field(ge=0.0, le=1.0)
    confidence: ConfidenceLevel
    confidence_reasons: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    what_exists: list[Claim] = Field(default_factory=list)
    what_customers_say: list[Claim] = Field(default_factory=list)
    what_people_search: list[Claim] = Field(default_factory=list)
    what_is_changing: list[Claim] = Field(default_factory=list)
    why_we_think_this: list[Claim] = Field(default_factory=list)
    conflicts: list[ConflictFlag] = Field(default_factory=list)
    validate_next: list[str] = Field(default_factory=list)
    dropped_claim_count: int = 0


class CategoryResult(BaseModel):
    category: str
    supply_count: int = 0
    supply_within_radius: int = 0
    mean_rating: Optional[float] = None
    low_rating_share: Optional[float] = None
    hours_coverage_pct: Optional[float] = None
    open_in_need_window_share: Optional[float] = None
    demand_label: Optional[str] = None
    demand_is_regional: bool = True
    prelim_score: float = 0.0
    selected_for_deep: bool = False
    evidence_ids: list[str] = Field(default_factory=list)


class BudgetLine(BaseModel):
    label: str
    planned_calls: int
    used_calls: int = 0


class BudgetStatus(BaseModel):
    cap: int
    counted_spent: int = 0
    measured_spent: Optional[int] = None
    cache_hits: int = 0
    lines: list[BudgetLine] = Field(default_factory=list)
    refused_calls: int = 0


class ScanResult(BaseModel):
    scan_id: str
    town_name: str
    center_lat: float
    center_lng: float
    radius_km: float
    preset: ScanPreset
    mode: str
    status: str = "completed"
    created_at: datetime = Field(default_factory=utcnow)
    budget: BudgetStatus
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    category_results: list[CategoryResult] = Field(default_factory=list)
    gaps: list[Gap] = Field(default_factory=list)
    evidence: dict[str, EvidenceItem] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    llm_used: bool = False
    llm_model: Optional[str] = None
