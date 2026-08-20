# Validation report (T043 / scores_v1)

**Recipe:** `scores_v1` · **Decision:** D30 · **Generated:** `2026-08-20T00:38:53.647585+00:00`

## Counts

| Split | N | Role |
|---|---:|---|
| cohort | 23 | fit normals (LOO self-scores) |
| validation | 1 | O04 / T043 only |
| ambiguous | 1 | exploratory; not counted |
| pupil | 83 | D32 surrogate negative class; **not** part of O04 (see `results/pupil_validation_report.md`) |

## O04 outcome (SK-A-3934)

**Result: `weak`**

| Quantity | Value |
|---|---|
| object | `SK-A-3934` |
| title | Borstbeeld van een lachende jonge man |
| combined | 0.282608 |
| z_A | 0.022581 |
| z_B | 0.260027 |
| dominant_signal | B |
| driver_A | embed_cosine_to_centroid |
| driver_B_1 | hue_circ_std |
| driver_B_2 | grad_mag_std |
| rank_combined (of 108) | 26 |
| cohort median combined | -0.116810 |
| cohort p90 | 1.886465 |
| cohort p95 (O04 bar) | 2.106898 |
| cohort p99 | 2.857533 |
| clears median | True |
| clears p90 | False |
| clears p95 | False |
| clears p99 | False |

### Rule (pre-registered; not retuned)

- **pass:** `combined` ≥ cohort p95 of LOO `combined`
- **weak:** cohort median ≤ `combined` < p95
- **fail:** `combined` < cohort median

## Ambiguous (non-counting)

| Quantity | `SK-A-4096` |
|---|---|
| title | Simson en Delila |
| combined | 2.276952 |
| z_A | 0.919501 |
| z_B | 1.357451 |
| dominant_signal | B |
| driver_A | embed_cosine_to_centroid |
| driver_B_1 | grad_mag_mean |
| driver_B_2 | glcm_contrast |
| rank_combined (of 108) | 4 |

Per D21 / O04: ambiguous outcomes do **not** confirm or refute the method.

## Limits

Validation N=1: a pass is a single-case tail hit, not a population rate; fail/weak is inconclusive for “method never works.” IIIF ~1500 px (D12/D27) is weaker than forensic brushstroke scans. Geometry: Phase 1 uses width=1500, so tall works may have long edge >1500. No AUC. Rules were not changed after seeing validation scores.

## Artifacts

- `results/scores/scores_v1.csv`
- `results/scores/fit_manifest.json`
- Design: `results/phase4_scoring_design.md`
