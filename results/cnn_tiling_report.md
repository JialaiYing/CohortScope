# Tiling report (`cnn_tiles_v1` / D36)

**Design:** [`results/phase10_tile_embedding_design.md`](phase10_tile_embedding_design.md) · **Generated:** `2026-08-23T20:15:44.216461+00:00`

Every tile covers the same physical area of canvas, so one pixel means the same distance on every painting. No feature, embedding, or score is computed here.

## Parameters (pre-registered; not tunable)

| Parameter | Value |
|---|---|
| resolution floor | **0.2 mm/px** (O07) |
| tile size | 44.8 mm × 44.8 mm = 224 × 224 px |
| edge inset | 5% of each edge |
| tiles per work | 20, non-overlapping |
| selection | evenly spaced over the row-major grid; deterministic, no RNG |

## Eligibility

| Group | eligible | considered |
|---|---:|---:|
| cohort | 16 | 23 |
| pupil — Tier 1 | 36 | 67 |
| pupil — Tier 2 | 7 | 16 |
| validation | 1 | 1 |
| ambiguous | 1 | 1 |
| **total** | **61** | **108** |

1,220 tiles written, 10.6 MB.

## Below floor

Works the published imagery cannot support at this floor. They are reported as unanswerable rather than scored on inadequate pixels.

| Reason | N |
|---|---:|
| native resolution coarser than 0.2 mm/px | 44 |
| fewer than 20 tiles of 44.8 mm fit inside the inset | 3 |

### Cohort works excluded (7 of 23)

These are firm Rembrandts that any later fit on this recipe cannot use.

| object | native mm/px | title |
|---|---:|---|
| `SK-A-3981` | 0.363 | Stilleven met pauwen |
| `SK-A-3137` | 0.334 | De verloochening van Petrus |
| `SK-C-5` | 0.310 | Officieren en andere schutters van wijk II in Amsterdam, onder leiding |
| `SK-C-6` | 0.256 | De waardijns van het Amsterdamse lakenbereidersgilde, bekend als ‘De S |
| `SK-C-216` | 0.219 | Portret van een paar als Isaak en Rebekka, bekend als 'De Joodse bruid |
| `SK-A-4885` | 0.207 | Portrait of Johannes Wtenbogaert |
| `SK-A-3982` | 0.015 | Portret van Dr. Ephraïm Bueno |

## Verification

Every tile is requested as an IIIF region of `tile_side_native_px` square, served at 224 px, so the realized resolution is 44.8 mm ÷ 224 px = **0.200 mm/px for every work**, independent of painting size. That is the property the fixed-1500 pipeline lacked.

Per-work detail: `results/qc_cnn_tiles_v1/coverage.csv`. Fetch failures: `results/qc_cnn_tiles_v1/failures.csv`.
