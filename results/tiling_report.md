# Tiling report (`tiles_v1` / D34)

**Design:** [`results/phase8_tiling_design.md`](phase8_tiling_design.md) · **Generated:** `2026-08-20T04:25:34.025853+00:00`

Every tile covers the same physical area of canvas, so one pixel means the same distance on every painting. No feature, embedding, or score is computed here.

## Parameters (pre-registered; not tunable)

| Parameter | Value |
|---|---|
| resolution floor | **0.2 mm/px** (O07) |
| tile size | 30 mm × 30 mm = 150 × 150 px |
| edge inset | 5% of each edge |
| tiles per work | 20, non-overlapping |
| selection | evenly spaced over the row-major grid; deterministic, no RNG |

## Eligibility

| Group | eligible | considered |
|---|---:|---:|
| cohort | 17 | 23 |
| pupil — Tier 1 | 38 | 67 |
| pupil — Tier 2 | 7 | 16 |
| validation | 1 | 1 |
| ambiguous | 1 | 1 |
| **total** | **64** | **108** |

1,280 tiles written, 5.5 MB.

## Below floor

Works the published imagery cannot support at this floor. They are reported as unanswerable rather than scored on inadequate pixels.

| Reason | N |
|---|---:|
| native resolution coarser than 0.2 mm/px | 44 |

### Cohort works excluded (6 of 23)

These are firm Rembrandts that any later fit on this recipe cannot use.

| object | native mm/px | title |
|---|---:|---|
| `SK-A-3981` | 0.363 | Stilleven met pauwen |
| `SK-A-3137` | 0.334 | De verloochening van Petrus |
| `SK-C-5` | 0.310 | Officieren en andere schutters van wijk II in Amsterdam, onder leiding |
| `SK-C-6` | 0.256 | De waardijns van het Amsterdamse lakenbereidersgilde, bekend als ‘De S |
| `SK-C-216` | 0.219 | Portret van een paar als Isaak en Rebekka, bekend als 'De Joodse bruid |
| `SK-A-4885` | 0.207 | Portrait of Johannes Wtenbogaert |

## Verification

Every tile is requested as an IIIF region of `tile_side_native_px` square, served at 150 px, so the realized resolution is 30 mm ÷ 150 px = **0.200 mm/px for every work**, independent of painting size. That is the property the fixed-1500 pipeline lacked.

Per-work detail: `results/qc_tiles_v1/coverage.csv`. Fetch failures: `results/qc_tiles_v1/failures.csv`.
