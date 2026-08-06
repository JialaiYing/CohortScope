# Phase 3 — Interpretable feature shortlist (O03)

**Task:** T031 · **Role:** features · **Date:** 2026-08-06  
**Status:** **LOCKED** (D29 / human 2026-08-06) — Wave B extract implemented (`features.py` → `data/features/features_v1.csv`)  
**Inputs:** D05, D12, D27; `results/phase2_features_signoff.md`; `results/qc_preprocess_v1/geometry_note.md`

---

## Verdict

| Topic | Choice |
|---|---|
| v1 column count | **8** named scalars (no vectors / histograms exported) |
| Families | Brushstroke (3) · Texture (3) · Palette (2) |
| Pixel source | **Branch H only** — `data/preprocessed/preprocess_v1/rgb/{object_number}.png` |
| Not used | Branch C (224 / ImageNet), raw JPEG re-decode with different policy, any learned head |
| Join key | `object_number` |
| Thresholds / z-scores | **Out of scope** — Statistics (Phase 4) |

Kitchen-sink rejected: no full Haralick bank, no multi-radius LBP dump, no wavelet coefficient grids, no region masks, no CNN activations as “interpretable.”

---

## 1. Proposed shortlist (O03)

Every column is one scalar per painting. One-line curator meaning in the Meaning column.

### Brushstroke / edge structure

| Column | Meaning |
|---|---|
| `grad_mag_mean` | Average edge strength (Sobel) — overall surface “busy-ness” |
| `grad_mag_std` | Spread of edge strength — smooth passages vs local impasto/edge clusters |
| `grad_orient_entropy` | How evenly stroke/edge directions are spread — ordered vs chaotic |

### Texture (classical, grayscale from Branch H RGB)

| Column | Meaning |
|---|---|
| `laplacian_var` | High-frequency energy (Laplacian variance) — fine grain vs flat paint |
| `lbp_entropy` | Local Binary Pattern histogram entropy — micro-texture complexity |
| `glcm_contrast` | Gray-level co-occurrence contrast — local tonal jumps |

### Palette (color space converted inside the extractor, not in preprocess)

| Column | Meaning |
|---|---|
| `lab_chroma_mean` | Mean Lab chroma `√(a*²+b*²)` — how colorful vs muted overall |
| `hue_circ_std` | Circular std of hue, chroma-weighted — palette coherence vs scattered hues |

**Fixed compute recipe (to freeze at human lock, implement in T032):**

| Op family | Locked defaults (proposed) |
|---|---|
| Grayscale | Luminance from RGB (`0.2989 R + 0.5870 G + 0.1140 B`) for texture/brushstroke |
| Sobel | 3×3; magnitude = `√(Gx²+Gy²)`; orientation in `[0, π)` (unsigned) |
| Orientation hist | 8 bins over `[0, π)`; Shannon entropy on normalized counts |
| Laplacian | 3×3 kernel; variance of response image |
| LBP | Uniform LBP, radius=1, P=8; entropy of histogram |
| GLCM | Grayscale quantized to 32 levels; distance=1; average contrast over angles `{0°, 45°, 90°, 135°}` |
| Lab / hue | sRGB→Lab; `lab_chroma_mean` from Lab chroma; `hue_circ_std` from Lab hue `atan2(b*, a*)` (chroma-weighted; chroma &lt; 5 ignored). **Not HSV** (shortlist draft once mentioned HSV; shipped recipe is Lab-only). |

Exact library calls may vary; **parameters above are the contract**, not interchangeable per image.

---

## 2. Input geometry (D27 honesty)

Branch H is **identity** on Phase 1 IIIF JPEGs. Acquisition uses **width=1500** (`full/1500,`), not always long-edge 1500:

| Case | N (scored) | Implication |
|---|---:|---|
| Wide works (long edge = 1500) | 5 | Matches D12 wording |
| Tall works (width=1500, height &gt; 1500) | 20 | More pixels vertically; absolute HF energy can track height |

**Features policy:** do **not** resize/crop/pad Branch H to force long-edge 1500. Document the confound; let Phase 4 cohort z-scoring absorb scale mix within Rembrandt oils. Do **not** retune features after peeking at validation (SK-A-3934).

Optional future Data re-acquire with true long-edge is out of Features scope (D27).

---

## 3. Explicitly rejected for v1 (scope creep)

| Rejected | Why |
|---|---|
| Full Haralick set (energy, homogeneity, correlation, …) | Redundant with `glcm_contrast`; kitchen sink |
| Multi-radius / multi-P LBP or LBP histogram vectors | High-dim; hard to narrate; entropy scalar is enough |
| Discrete wavelet packet banks / coefficient maps | Prior-art adjacent; Literature owns honesty (T034); defer unless T043 fails |
| Gabor filter banks | Same — many knobs, weak curator story per band |
| Local patch CNN / Gram / style matrices | Not hand-built; CV owns embeddings (D05/D13) |
| Segmentation / face / figure masks | Non-deterministic composition; L6 risk |
| Per-channel RGB means/stds as extra columns | Mostly lighting/scan; chroma + hue already cover palette intent |
| ImageNet-normalized 224 features | Wrong path (Branch C); T023 forbids |
| Any feature fitted or selected using validation/ambiguous ranks | L6 |

Adding columns after lock requires human reopen of O03 — not silent expansion in T032.

---

## 4. Matrix / hand-off contract (for Stats T035 / T033)

| Item | Spec |
|---|---|
| Rows | Same scored set as preprocess: `cohort` ∪ `validation` ∪ `ambiguous` (N=25) |
| Columns | `object_number` + the 8 feature columns above |
| Missing | Fail the row in a failure log; do not impute |
| Fit | **None** in Features — no cohort mean/std here |
| Export (T033) | e.g. `data/features/features_v1.parquet` or `.csv` + short feature dictionary mirroring §1 |
| Decomposability | Each column name must appear as a possible “driver” string in Phase 4 narratives |

---

## 5. Open for human lock

1. Approve the **8-column** table in §1 (names + meanings)?  
2. Approve locked compute defaults in §1 (LBP r=1, GLCM 32-level, etc.)?  
3. Any column to drop/swap before Wave B?

**No extraction code until this memo is human-approved** (O03 → then record lock in `docs/decisions.md`).
