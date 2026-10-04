# SerpApi integration detail

Every SerpApi call in this project goes through exactly one place:
`backend/app/services/serpapi/client.py` (`SerpApiClient.call`). Normalization
for each engine lives in `backend/app/services/serpapi/engines.py`. This
document describes each engine call the way it's actually used in
`backend/app/orchestrator/orchestrator.py`.

## 1. `google_maps` - town geocoding

- **Input:** `{"type": "search", "q": "<town name>", "hl": "en"}`
- **Output used:** `place_results.gps_coordinates` → `(lat, lng)`
- **Why it matters:** every subsequent Maps call needs a center point.
- **Transformation:** `normalize_geocode()` extracts just the coordinate pair.
- **On failure:** the scan is marked `status="failed"` with a warning
  explaining the town could not be located - it does not crash and does not
  fall back to a guessed coordinate.

## 2. `google_maps` - supply per category

- **Input:** `{"type": "search", "q": "<category>", "ll": "@lat,lng,{zoom}z", "hl": "en"}`, one call per category in the scan's taxonomy.
- **Output used:** `local_results[]` - title, `data_id`/`place_id`, `gps_coordinates`, `rating`, `reviews`, `type`, and (when present) `operating_hours` (a per-weekday string).
- **Why it matters:** this is the ground-truth supply signal, and - critically - the **only free source of opening hours**, which the service-window gap depends on entirely.
- **Transformation:** `normalize_maps_search()` → `normalize_place()` per result, then `analysis/dedupe.py` collapses duplicate `place_id`s across any repeated calls, keeping the record closest to the town centre.
- **How it's used:** feeds `analysis/stats.py` (density, rating stats) and `analysis/hours.py` (need-window coverage) directly; every place becomes a `PLACE` evidence item.
- **On failure:** that category is skipped for this run and a warning is recorded - it is **never** treated as "zero supply" (a failed call and a category with no competitors must never look the same to the gap logic).

## 3. `google_trends` - demand interest

- **Input:** `{"q": "term1,term2,...(up to 5)", "geo": "IN", "date": "today 12-m", "data_type": "TIMESERIES", "hl": "en"}`, batched across all categories in groups of 5.
- **Output used:** `interest_over_time.timeline_data[].values[]`, matched back to each category's term by `analysis/demand.py:extract_trend_average()`.
- **Why `geo=IN` and not a state code:** state-level Trends granularity for small Indian towns was not verified as reliably present at the time this was built (see the verification approach in `scripts/verify_api_setup.py`). Country-level Trends is a real, if coarser, regional signal, and the demand composite explicitly discloses `is_regional=True` whenever this signal contributes - it is never silently presented as town-level.
- **On failure:** that batch's categories get `trend_avg=None`; demand falls back to the Autocomplete and review-density components only.

## 4. `google_news` - local catalysts

- **Input:** two town-level queries: `"<town> industrial development"` and `"<town> news"`.
- **Output used:** `news_results[]` - title, source, link, date, snippet.
- **Why it matters:** a rising local catalyst (a new highway, a college, an industrial estate) is qualitative evidence for "why now", attached to the top-scoring categories' gaps.
- **Transformation:** `normalize_news()` tolerates `source` being either a plain string or an object (SerpApi's News engine returns an object).
- **On failure:** the "what is changing" section is simply empty for that scan - no fabricated catalysts.

## 5. `google_autocomplete` - need signals

- **Input:** `{"q": "<category> <town name>", "gl": "in", "hl": "en"}`, only for the top-scoring categories selected for the "deep" phase.
- **Output used:** `suggestions[].value`.
- **Why it matters:** phrases like "open 24 hours", "near me", "home delivery" are a local, town-specific need signal that Trends (regional) cannot provide.
- **Transformation:** `analysis/demand.py:autocomplete_need_score()` counts how many suggestions contain a need-bearing keyword.
- **On failure:** skipped, with a small confidence penalty recorded.

## 6. `google_maps_reviews` - customer pain

- **Input:** two calls per top-scoring category, against the single busiest place (most reviews) found in that category's supply scan:
  - default: `{"data_id": "...", "hl": "en"}` - returns SerpApi's own `topics` (keyword + mention count), computed by Google itself, at no extra reasoning cost.
  - `{"data_id": "...", "hl": "en", "sort_by": "ratingLow"}` - biases the returned reviews toward complaints, which is what the LLM-based Voice-of-Customer agent tags for additional themes.
- **Output used:** `reviews[].{rating, snippet/extracted_snippet, iso_date, review_id}`, `topics[].{keyword, mentions}`.
- **Why it matters:** this is the only signal behind the quality gap and the only place customer sentiment enters the pipeline.
- **Privacy:** reviewer name, profile link, and contributor ID are **never stored or sent to the LLM** - `normalize_review()` drops them entirely, keeping only non-identifying stats (e.g. "local guide: true").
- **On failure:** that category's quality gap is skipped; the "what customers say" section stays empty and is disclosed as missing information rather than guessed at.

## Caching

Two layers exist:
1. **SerpApi's own cache** (~1 hour, per their documentation) - free and automatic on their side.
2. **Our own SQLite cache** (`serp_cache` table, `backend/app/db/models.py`), keyed by `engine + sorted params` (never the API key), with per-engine TTLs (Maps/Reviews 7 days, Trends 30 days, News 24 hours, Autocomplete 7 days). This is what lets repeated development, testing, and demo runs avoid re-spending credits across sessions and days, not just within one hour.

Every cache hit is counted separately from "counted" (attempted, billable) calls, and both numbers are shown in the UI's budget meter.
