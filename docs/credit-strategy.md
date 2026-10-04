# Credit strategy

Nukkad treats SerpApi credits as a real, finite resource at every layer, not
just in the pitch deck.

## Two independent caps (`backend/app/planner/budget.py`)

1. **Per-scan cap** - chosen by the scan-depth preset (see table below).
2. **Global daily cap** (`NUKKAD_DAILY_CREDIT_CAP`, default 300) - shared
   across every scan, persisted in the `daily_credit_usage` SQLite table so
   it survives a restart. This protects your plan if the app is ever
   exposed publicly (e.g. for a judge to try live).

A cache hit never counts against either cap. A call is "counted" the moment
it is attempted and not served from cache - conservative, since SerpApi's
exact accounting for errored/edge-case calls was not independently
re-verified for this repository snapshot.

## Presets

| Preset | Default cap | Roughly |
|---|---|---|
| Lite | 40 | 8 categories, coarse only, minimal deep dive |
| Standard | 90 | 12 categories, top 4 get autocomplete + reviews |
| Deep | 150 | 15 categories, top 6 get autocomplete + reviews |

All three are configurable via `NUKKAD_LITE_SCAN_CREDITS`,
`NUKKAD_STANDARD_SCAN_CREDITS`, `NUKKAD_DEEP_SCAN_CREDITS` in `.env`, and
`NUKKAD_MAX_SCAN_CREDITS` is a hard absolute ceiling regardless of preset.

## The funnel, in call order (Standard preset)

1. **Trends** for every category, batched 5 terms per call (~3 calls) - cheap, and computed *before* deciding which categories are "top", so prioritization uses real demand data rather than a guess.
2. **News**, 2 town-level queries - cheap, shared context for all top categories.
3. **Maps supply**, one call per category (~12 calls) - this is also where opening hours come for free.
4. **Prioritize** - zero credits. A simple score `(demand / 100) - 0.5 * min(1, supply / 15)` ranks categories by demand-vs-supply mismatch.
5. **Autocomplete + Reviews**, only for the top 4 categories (~4 + 8 = 12 calls) - the expensive, high-value calls are reserved for categories that already look promising.

## Two layers of caching

1. SerpApi's own ~1-hour cache (free, automatic, on their side).
2. Nukkad's own SQLite cache (`serp_cache` table), keyed by engine + sorted
   parameters (never the API key), with per-engine TTLs from `.env`
   (Maps/Reviews 7 days, Trends 30 days, News 24 hours, Autocomplete 7
   days). This is what makes repeated development, testing, and demo runs
   cheap across sessions and days, not just within one hour.

## What the UI shows

The budget meter shows counted spend vs. cap, cache hits, and (when the
SerpApi Account API is reachable) the account's actual remaining searches -
labelled separately as "measured" vs. our own conservative "counted" number,
since the two can legitimately differ and there's no point pretending
otherwise.

## Recording a reliable demo without spending credits live

`scripts/verify_api_setup.py` records sanitized real responses to
`fixtures/serpapi/`. A natural next step (see Roadmap in the README) is a
"snapshot" scan mode that replays a recorded scan through the full pipeline
at zero credits - the `mode` field on `ScanRequest` already reserves space
for this (`"live" | "snapshot"`), though snapshot replay itself is not
wired up in this repository snapshot.
