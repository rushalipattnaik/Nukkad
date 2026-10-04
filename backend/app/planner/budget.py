"""
Gates every SerpApi call against two limits: the per-scan cap (set by the
Lite/Standard/Deep preset) and a global daily cap (NUKKAD_DAILY_CREDIT_CAP),
the latter persisted in `daily_credit_usage` so it survives a restart.

Cache hits don't count against either. We don't actually know SerpApi's
exact billing rules for errored/edge-case calls, so a call is "counted" the
moment it's attempted and not served from cache - better to overcount than
blow through a plan.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.core.logging_utils import get_logger
from app.db.database import get_session
from app.db.models import DailyCreditUsage
from app.domain.schemas import BudgetLine, BudgetStatus
from app.services.serpapi.client import BudgetExceeded

logger = get_logger(__name__)


def _today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class BudgetManager:
    def __init__(self, cap: int, daily_cap: int) -> None:
        self.cap = cap
        self.daily_cap = daily_cap
        self.counted_spent = 0
        self.cache_hits = 0
        self.refused_calls = 0
        self._lines: dict[str, BudgetLine] = {}

    # -- called by SerpApiClient -----------------------------------------
    def check(self, engine: str) -> None:
        if self.counted_spent >= self.cap:
            self.refused_calls += 1
            raise BudgetExceeded(f"Per-scan credit cap ({self.cap}) reached; refusing further '{engine}' calls.")
        if self._daily_used() >= self.daily_cap:
            self.refused_calls += 1
            raise BudgetExceeded(f"Daily credit cap ({self.daily_cap}) reached; refusing further '{engine}' calls.")

    def record(self, engine: str, cache_hit: bool) -> None:
        line = self._lines.setdefault(engine, BudgetLine(label=engine, planned_calls=0))
        if cache_hit:
            self.cache_hits += 1
        else:
            self.counted_spent += 1
            line.used_calls += 1
            self._increment_daily()

    # -- daily cap persistence --------------------------------------------
    def _daily_used(self) -> int:
        with get_session() as session:
            row = session.get(DailyCreditUsage, _today_key())
            return row.counted_calls if row else 0

    def _increment_daily(self) -> None:
        with get_session() as session:
            row = session.get(DailyCreditUsage, _today_key())
            if row:
                row.counted_calls += 1
            else:
                session.add(DailyCreditUsage(day=_today_key(), counted_calls=1))

    # -- reporting ----------------------------------------------------------
    def status(self, measured_spent: int | None = None) -> BudgetStatus:
        return BudgetStatus(
            cap=self.cap,
            counted_spent=self.counted_spent,
            measured_spent=measured_spent,
            cache_hits=self.cache_hits,
            lines=list(self._lines.values()),
            refused_calls=self.refused_calls,
        )
