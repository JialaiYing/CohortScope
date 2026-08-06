# Phase 2 preprocess — Features brushstroke / texture sign-off

**Task:** T023 · **Role:** features · **Date:** 2026-08-05  
**Inputs reviewed:** `results/phase2_preprocess_design.md` (T020), `results/phase2_preprocess_stats_memo.md` (T024)  
**Scope:** Design review only — no feature extraction code

---

## Verdict

| Field | Value |
|---|---|
| Decision | **Approve** |
| Design under review | T020 two-branch preprocess (`preprocess_v1`) |
| Brushstroke / texture survival | Branch H (identity long-edge 1500 RGB uint8) is appropriate |
| Palette survival | Intact — no color transfer, CLAHE, histogram match, or cohort-fitted normalize on Branch H |
| Blocking changes before Wave B? | **None** |

CV’s Branch H is stronger for handcrafted signal than Stats T024’s letterbox preference for the feature path. Features explicitly endorses **no pad / no crop / native aspect at D12 resolution** for interpretable features. Letterbox remains a Stats concern for any shared square cache; it must **not** be applied to the handcrafted cache.

---

## 1. What we approve

| Element | Features stance |
|---|---|
| Shared decode (RGB, EXIF once, no Lab/HSV in cache) | Approve — Features will convert to Lab/HSV **inside T032** from RGB uint8 |
| Branch H: identity geometry, long edge 1500, uint8 H×W×3 | **Approve — this is the Phase 3 interpretable input** |
| Branch H: lossless PNG cache | Approve — avoids extra JPEG generation loss; same decode as CNN branch |
| Branch C: Resize(256)+CenterCrop(224)+ImageNet mean/std | Approve **for embeddings only** — Features will not consume this path |
| Forbidden list §3 (denoise, sharpen, CLAHE, hist-match, color transfer, corpus pixel fit, content crop, aug) | Approve — necessary and sufficient for planned O03 families |
| Scored worklist N=25 (`cohort` ∪ `validation` ∪ `ambiguous`) | Approve (selection only; no label-dependent ops) |
| Deterministic `preprocess_v1` recipe + manifest | Approve |

---

## 2. Ops that would harm handcrafted features

Do **not** add any of these to Branch H (or to a shared cache that Features would read):

| Harmful op | Why it breaks O03-style stats |
|---|---|
| Denoise / bilateral / NL-means / blur | Kills high-frequency energy (`laplacian_var`, LBP, GLCM contrast) |
| Sharpen / unsharp mask | Invents edges → fake `grad_mag_*` / orientation signal |
| CLAHE / histogram equalization / heavy per-image contrast stretch | Rewrites local gradients and tonal co-occurrence |
| Histogram matching / color transfer / auto white-balance / cohort color ref | Contaminates `lab_chroma_mean`, `hue_circ_std` |
| Stretch-to-square (anisotropic resize) | Couples aspect ratio to stroke orientation entropy — indefensible |
| Center crop / saliency crop on the **handcrafted** path | Drops margin strokes; aspect-correlated missing mass |
| Letterbox / constant pad on the **handcrafted** path | Dilutes global palette stats in proportion to pad fraction; unnecessary if Branch H stays native aspect |
| Extra downscale below long-edge ~1500 | Erases brushstroke-scale detail D12 paid for |
| JPEG “cleanup” re-encode | Extra quantization noise / blur on texture |
| Fitting mean/std / PCA on corpus pixels for preprocess | Leakage (L6) + changes absolute color/texture baselines |
| Running interpretable features on Branch C (224 / ImageNet-normalized) | Wrong scale, wrong crop, wrong color space for curator-facing texture/palette |

T020 §3 already forbids the dangerous ops. This section is the Features rationale for keeping that list closed in Wave B.

---

## 3. Resolution for Phase 3 interpretable features

| Consumer | Spatial / dtype target | Source |
|---|---|---|
| Hand-built texture / brushstroke / palette (T032–T033) | **RGB uint8, native aspect, long edge 1500** (D12) | Branch H only: `data/preprocessed/preprocess_v1/rgb/{object_number}.png` |
| ResNet50 embeddings (T030) | 3×224×224 ImageNet-normalized float32 | Branch C — **out of Features scope** |

**May differ from ResNet input?** Yes — required. Square 224 center crops are a poor default for stroke-scale and full-field palette statistics.

**Join key:** `object_number` (same as SQLite `works` and `data/images/`).

**Note on O03:** Shortlist remains open (T031). This sign-off does not lock columns; it only locks that whatever ships must be computable from Branch H without further destructive preprocess.

---

## 4. Stats T024 alignment (geometry)

| Stats T024 ask | Features response |
|---|---|
| No stretch | Agree — reject |
| Letterbox for hand-built before CNN crop | **Decline for Branch H** — identity-at-1500 is better for palette + full-field texture; pad would dilute globals |
| Published ImageNet constants only on CNN path | Agree — Features never needs those constants on Branch H |
| No per-image hist-eq in shared cache | Agree — default avoid |

No design change requested to T020. CV and Features are aligned; Stats letterbox applies if anyone later proposes a **single** square cache for both signals — we recommend against that for v1.

---

## 5. Soft asks for Wave B / T022 (non-blocking)

1. **Consumer contract in code comments / README of `preprocess.py`:** Features reads Branch H PNGs only.  
2. **QC (T022):** Keep the planned 100% crop of a high-detail region on Branch H (T020 §6.1). Features will use that grid at T025/T032 readiness — not to retune ops on validation.  
3. **Do not** introduce mild auto-WB / percentile clip without reopening this sign-off.

---

## 6. Hand-off

| Who | Action |
|---|---|
| **Human** | May lock T020 for Wave B from a Features perspective (this file = T023 done) |
| **CV (T021–T022)** | Implement as designed; Branch H identity-at-1500 |
| **Features** | Next: T031 O03 shortlist confirm at Phase 3 gate; then T032–T033 on Branch H |
| **Review (T025)** | Confirm Branch H outputs match this contract after Wave B |

**Wave B blocker from Features:** cleared.
