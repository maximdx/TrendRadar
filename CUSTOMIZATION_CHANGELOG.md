# Customization Changelog

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
