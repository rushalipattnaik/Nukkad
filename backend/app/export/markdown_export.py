from __future__ import annotations

from app.domain.schemas import ScanResult


def to_markdown(result: ScanResult) -> str:
    lines: list[str] = []
    lines.append(f"# Nukkad opportunity memo - {result.town_name}")
    lines.append("")
    lines.append(f"*Scan ID: `{result.scan_id}` - radius {result.radius_km:.1f} km - preset {result.preset.value} - "
                 f"generated {result.created_at.isoformat()}*")
    lines.append("")
    lines.append("> Nukkad detects local market gaps by comparing what a town has, what people are searching "
                 "for, what customers complain about, and what is changing - then produces evidence-backed "
                 "**opportunity hypotheses**, never a guarantee of success.")
    lines.append("")
    if result.warnings:
        lines.append("## Data limitations")
        for w in result.warnings:
            lines.append(f"- {w}")
        lines.append("")

    if not result.gaps:
        lines.append("No opportunity hypotheses met the evidence thresholds for this scan.")
        return "\n".join(lines)

    lines.append("## Opportunity hypotheses")
    for gap in sorted(result.gaps, key=lambda g: g.strength, reverse=True):
        lines.append("")
        lines.append(f"### {gap.category} - {gap.gap_type.value.replace('_', ' ').title()} gap "
                     f"(confidence: {gap.confidence.value})")
        for section_title, claims in (
            ("What exists", gap.what_exists),
            ("What customers say", gap.what_customers_say),
            ("What people search", gap.what_people_search),
            ("What is changing", gap.what_is_changing),
            ("Why we think this", gap.why_we_think_this),
        ):
            if not claims:
                continue
            lines.append(f"**{section_title}:**")
            for claim in claims:
                cites = ", ".join(claim.evidence_ids)
                lines.append(f"- {claim.text} _[{cites}]_")
        if gap.conflicts:
            lines.append("**Signals disagree:**")
            for c in gap.conflicts:
                lines.append(f"- {c.label}: {c.explanation}")
        if gap.missing_information:
            lines.append("**Missing information:**")
            for m in gap.missing_information:
                lines.append(f"- {m}")
        if gap.validate_next:
            lines.append("**Validate next:**")
            for v in gap.validate_next:
                lines.append(f"- {v}")
        if gap.dropped_claim_count:
            lines.append(f"*{gap.dropped_claim_count} claim(s) removed by the verifier as unverifiable.*")

    lines.append("")
    lines.append("---")
    lines.append(f"Budget used: {result.budget.counted_spent} of {result.budget.cap} planned SerpApi searches "
                 f"({result.budget.cache_hits} served from cache).")
    return "\n".join(lines)
