from __future__ import annotations

from app.agents.verifier import verify_all
from app.domain.schemas import Claim, ClaimType, ConfidenceLevel, Gap, GapType


def _gap(claims: list[Claim]) -> Gap:
    return Gap(
        gap_id="gap_1", category="Medical store", gap_type=GapType.ABSENCE, strength=0.5,
        confidence=ConfidenceLevel.MEDIUM, what_exists=claims,
    )


def test_claim_with_unknown_evidence_id_is_dropped():
    gap = _gap([Claim(claim_type=ClaimType.FACT, text="7 pharmacies exist.", evidence_ids=["E-UNKNOWN-1"])])
    [verified] = verify_all([gap], evidence_ids={"E-PLACE-1"})
    assert verified.what_exists == []
    assert verified.dropped_claim_count == 1


def test_claim_with_known_evidence_id_is_kept_and_marked_verified():
    gap = _gap([Claim(claim_type=ClaimType.FACT, text="7 pharmacies exist.", evidence_ids=["E-PLACE-1"])])
    [verified] = verify_all([gap], evidence_ids={"E-PLACE-1"})
    assert len(verified.what_exists) == 1
    assert verified.what_exists[0].verified is True
    assert verified.dropped_claim_count == 0


def test_claim_with_banned_phrase_is_dropped_even_with_valid_evidence():
    gap = _gap([Claim(claim_type=ClaimType.INTERPRETATION,
                       text="This is a guaranteed opportunity for profit.", evidence_ids=["E-PLACE-1"])])
    [verified] = verify_all([gap], evidence_ids={"E-PLACE-1"})
    assert verified.what_exists == []
    assert verified.dropped_claim_count == 1


def test_claim_with_no_evidence_ids_is_dropped():
    gap = _gap([Claim(claim_type=ClaimType.FACT, text="Something.", evidence_ids=[])])
    [verified] = verify_all([gap], evidence_ids={"E-PLACE-1"})
    assert verified.dropped_claim_count == 1
