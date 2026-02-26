# Customization Changelog

## 2026-02-26

### Cross-source duplicate dedupe in keyword stats
- Added cross-source dedupe for keyword-stat news records in `trendradar/core/analyzer.py`.
- Dedupe keys now prefer normalized URL signature (`get_url_signature`) and fall back to normalized title signatures.
- Duplicate records are merged into one item while preserving multi-source attribution:
  - keeps `source_names` list and joins them into `source_name` for display
  - keeps `is_new` if either side is new
  - fills missing `url`, `mobileUrl`, `published_at`, and `rank_timeline` from the duplicate record when needed
- Added replacement priority when duplicate items conflict:
  - better best rank first
  - then higher observed count
  - then longer title
- Added dedupe log output for daily processing:
  - `跨源去重：合并 X 条重复新闻`

## 2026-02-22

### Newsletter list time display (customizable)
- Added `display.time_display_mode` to `config.yaml`:
  - `hidden`
  - `observed`
  - `publish`
  - `publish_or_observed`
- Added `display.show_observation_count` to control repeat-count display in list items.
- Wired the setting into both:
  - notification/newsletter list rendering
  - HTML report hotlist and standalone hotlist rendering
- Config editor (`docs/assets/script.js`) now exposes both controls in the `display` module.

### Hotlist publish-time delivery (strict publish-first)
- Added `published_at` persistence for hotlist items in storage schema and read/write path.
- Crawler now keeps publish-time related fields from API payload (`pubDate`, `extra.date`, etc.).
- Added runtime publish-time enrichment for hotlist list items:
  - If source payload has no publish time, fetch from article URL metadata (`meta`, JSON-LD, `<time datetime>`)
  - Cache results in `output/news/publish_time_cache.db` to avoid repeated crawling
- Added `display.publish_time_enrich` config options:
  - `enabled`
  - `max_fetch_per_run`
  - `request_timeout`
  - `max_workers`
  - `miss_ttl_hours`

## 2026-02-20

### HTML report UX
- Added foldable keyword sections for hotlist groups.
- Added global fold controls (collapse/expand all groups).
- Added outline navigation generated from report sections.
- Added floating side outline navigation on wide screens with responsive fallback.

### Fold behavior robustness
- Standardized collapsed/expanded state handling via CSS class toggle.
- Synced fold icon (`▾`/`▸`) and accessibility attributes (`aria-expanded`, `aria-hidden`).
- Hardened click handling for cross-browser target edge cases.

### Export behavior
- Updated image export flow to temporarily expand folded sections before capture.
- Hid outline panel during export and restored UI state after export.

### Time/count display configuration
- Added `HTML_TIME_DISPLAY_MODE` with modes:
  - `hidden`
  - `observed`
  - `publish`
  - `publish_or_observed`
- Added `HTML_SHOW_OBSERVATION_COUNT` to toggle repeat-count display.
- Current default in customized renderer: `HTML_TIME_DISPLAY_MODE=hidden`.

### Notes
- Publish timestamps currently require source data to provide publish-time fields.
- RSS sections already provide publish timestamps.
