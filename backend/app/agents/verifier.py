"""
Checks every claim before it reaches the report: it needs at least one
evidence_id that actually exists in this scan's ledger, and its text has to
clear the banned-phrase guardrail in core/security.py. Anything that fails
gets dropped (not rewritten), and the count is kept per gap so the UI can
show "N claims removed, unverifiable".
"""
from __future__ import annotations

from app.core.security import enforce_language_guardrail
from app.domain.schemas import Claim, Gap


def _verify_claim_list(claims: list[Claim], evidence_ids: set[str]) -> tuple[list[Claim], int]:
    kept: list[Claim] = []
    dropped = 0
    for claim in claims:
        if not claim.evidence_ids or not all(eid in evidence_ids for eid in claim.evidence_ids):
            dropped += 1
            continue
        _, banned = enforce_language_guardrail(claim.text)
        if banned:
            dropped += 1
            continue
        claim.verified = True
        kept.append(claim)
    return kept, dropped


def verify_gap(gap: Gap, evidence_ids: set[str]) -> Gap:
    total_dropped = 0
    for field_name in ("what_exists", "what_customers_say", "what_people_search",
                       "what_is_changing", "why_we_think_this"):
        claims = getattr(gap, field_name)
        kept, dropped = _verify_claim_list(claims, evidence_ids)
        setattr(gap, field_name, kept)
        total_dropped += dropped
    gap.dropped_claim_count = total_dropped
    return gap


def verify_all(gaps: list[Gap], evidence_ids: set[str]) -> list[Gap]:
    return [verify_gap(g, evidence_ids) for g in gaps]
