# Methodensammlung Implementation Notes

## Detected stack

- Repository root contained no existing app scaffold, no package manager manifest, and no framework routing setup.
- Available implementation assets were:
  - `Methodensammlung_SSOT_v2_1.xlsx`
  - Stitch HTML/PNG mockup exports
  - `methodensammlung_stitch/polarstern_aurora/DESIGN.md`
  - `scripts/build_methodensammlung_ssot.py`
- Local runtimes confirmed during inspection:
  - `node v25.8.1`
  - `python3 3.9.6`

## Chosen implementation path

- Static single-page app with native ES modules and hash routing.
- Build-time workbook export using Python stdlib only.
- Generated outputs:
  - `data/methodensammlung.json`
  - `src/generated/methodensammlung-data.js`
- Shared selector layer in `src/data-model.js` centralizes:
  - finder intent hydration
  - search ranking
  - collection/vector browsing
  - method detail hydration
  - composer block hydration
  - active session hydration

## Aesthetic direction

- Direction: editorial nocturne with warm Aurora bleed.
- Anchors from `DESIGN.md` kept intact:
  - Aurora palette
  - intentional asymmetry
  - no-line rule
  - Chau Philomene One only for expressive moments
  - Roboto for functional UI
  - layered paper/glass surfaces instead of hard dividers
- Because the repository contained no real media library, the implementation uses text-first gradient panels rather than stock imagery.

## Data handling notes

- Workbook remains the canonical content source.
- Mockups only shaped layout, hierarchy, and interaction patterns.
- Workbook relations are preserved as separate sheets in the generated bundle.
- Stable IDs remain intact across methods, variants, collections, vectors, and composer references.
- Heuristic fields remain visible as heuristic or soft-cue usage only; no heuristic value is reframed as verified truth.

## Fallback behavior

- Missing duration:
  - duration chips stay hidden on cards and detail pages
  - composer totals only sum grounded or manually entered durations
  - active session timer starts in manual mode when no duration is grounded
- Missing notes / risks:
  - related panels collapse completely
- Missing media:
  - gradient editorial placeholders only
- Sparse metadata:
  - cards show only available chips
  - library and finder remain search-first rather than forcing exhaustive filters

## Open issues / limitations

- This repository still has no pre-existing backend, so drafts and live notes persist locally in `localStorage`.
- The current implementation uses hash routing because no server/router framework existed in the checkout.
- Only a small subset of methods has grounded duration in the workbook, so composer totals are frequently partial by design.
- The active-session timer is intentionally lightweight and local; there is no cross-device sync layer in scope.
