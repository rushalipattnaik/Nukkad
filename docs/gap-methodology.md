# Gap detection methodology

All thresholds below are named constants in `backend/app/analysis/gaps.py` -
nothing here is a hidden magic number. Every gap fires only when the
underlying evidence exists; the "record_computed" step means every derived
number (like "7 pharmacies") gets its own evidence ID before it can be cited.

## Unit of analysis

One **category × scanned area** (e.g. "Medical store / pharmacy" within 3 km
of the town centre). Categories come from a curated 15-entry taxonomy
(`backend/app/planner/taxonomy.py`) chosen for relevance to small Indian
towns, each with a **need window** (e.g. pharmacy → "after 9 PM") used only
by the service-window gap.

## Demand index

A composite of up to three optional components (`analysis/demand.py`):
1. Google Trends interest (regional - see `docs/serpapi-integration.md`)
2. Autocomplete need-keyword score (local)
3. Review-volume density (local)

Missing components are simply excluded from the average rather than
defaulted to zero, so a category with no Trends data isn't punished for it.
`is_regional=True` whenever the Trends component contributed, and the UI
always discloses this.

## Gap rules

| Gap | Fires when | Key evidence |
|---|---|---|
| **ABSENCE** | Demand label is Medium or High, **and** supply within the radius is ≤ 3 | Maps supply count + demand index |
| **QUALITY** | Supply within the radius is ≥ 3, **and** the low-rating share (places rated < 4.0) is ≥ 30%, **and** at least one review topic has ≥ 3 mentions | Maps ratings + review topics (native SerpApi `topics` or LLM-derived) |
| **SERVICE_WINDOW** | Supply within the radius is ≥ 3, **and** at least 2 places have judgeable hours for the relevant need-days, **and** the share open during the need window is ≤ 34%, **and** the category has a real need window (not "any time") | Maps `operating_hours`, parsed by `analysis/hours.py` |

A category can produce more than one gap type, or none at all. Every gap's
`strength` (0-1) is a simple, documented function of how far the metrics
exceed the threshold - not an LLM judgment call.

## Confidence (`analysis/confidence.py`)

Built from five factors, each contributing a fixed score component with an
explicit reason string surfaced in the UI:
1. Supply sample size
2. Whether demand data exists, and whether it's regional-only
3. Whether review data exists
4. Whether hours data exists
5. Number of detected conflicts (each one *reduces* confidence slightly)

The result is Low / Medium / High plus an explicit "missing information"
list (e.g. "Demand includes a country-level Trends signal, not town-level").

## Conflict rules (`analysis/conflicts.py`)

| ID | Pattern | What it means |
|---|---|---|
| C1 | Demand High + supply within radius ≥ 10 | The area is probably already served; any opportunity is about a specific unmet need, not raw scarcity |
| C2 | Demand High + low-rating share ≥ 40% | Points to a quality gap rather than an absence gap |
| C3 | Demand Low + supply within radius ≤ 2 | The absence may simply be justified by genuinely low local need |
| C4 | Listed hours suggest most places are open during the need window, but review topics repeatedly mention hours/availability/closing | Listed hours may not reflect what actually happens - validate in person |

Conflicts never change *which* gaps fire - they attach to a gap as a
"Signals disagree" callout with a small negative effect on confidence and an
explicit "what to validate next" suggestion. The LLM is never asked whether
a conflict exists; it may only (optionally) help phrase an explanation that
was already deterministically triggered.

## Evidence and verification

Every retrieved SerpApi item, and every number computed from it, becomes an
`EvidenceItem` with a stable ID (`backend/app/domain/schemas.py`). A `Claim`
in a gap must cite at least one evidence ID. The Verifier
(`backend/app/agents/verifier.py`) is the only path a claim can take into
the final report: it checks that every cited ID exists in that scan's
ledger and that the claim's text doesn't trip the banned-phrase language
guardrail. Anything that fails either check is dropped and counted, visibly,
as "N claims removed, unverifiable."
