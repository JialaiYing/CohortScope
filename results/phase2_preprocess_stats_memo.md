# Phase 2 preprocess — statistical leakage memo

**Task:** T024 · **Role:** stats · **Date:** 2026-08-05  
**Status:** proposed for human lock with CV T020 / Features T023  
**Inputs:** L6 in `results/phase1_experimental_design.md` §4; D13, D19–D21; `results/inventory.md` (cohort=23, validation=1, ambiguous=1)

---

## Verdict

| Topic | Rule |
|---|---|
| Allowed transforms | **Per-image** ops with fixed, pre-registered parameters — same code path for every split |
| Forbidden | Any **corpus fit** for preprocess (mean/std, PCA, histogram matching, crop box, etc.) on `validation`, `ambiguous`, **or** the full scored set; also forbidden to **choose** preprocess by peeking at val/ambiguous scores |
| Global constants | **Published only** (e.g. ImageNet mean/std for ResNet50). Never estimate from our Rijksmuseum corpus |
| Geometry | **Do not stretch.** Prefer **aspect-preserving letterbox** to a fixed square with a **fixed pad value** |
| Thresholds / O02–O04 | Still Phase 4. Preprocess must not invent score cutoffs or tune to SK-A-3934 |

With **validation N=1**, any preprocess tweak “to make the circle work look odd” is pure L6 leakage. Lock ops before looking at that image’s post-preprocess features/scores.

---

## 1. Allowed vs forbidden

### 1.1 Allowed (per-image, fixed recipe)

Examples CV may include in T020 — each applied independently to one image, no statistics borrowed from other works:

| Class | Examples |
|---|---|
| Decode / color space | Load RGB; drop alpha; optional fixed sRGB assumption |
| Fixed resize | Scale so long edge or short edge equals a constant *T* chosen a priori (e.g. 512, 224) |
| Letterbox / pad | Pad to *T*×*T* with a **constant** RGB (see §3) |
| Fixed crop recipe | Only if part of a **published** backbone recipe (e.g. torchvision ResNet `Resize` + `CenterCrop` sizes) — not fitted on our data |
| Clipping / dtype | Clip to [0,1] or [0,255]; cast float32 |
| Published normalize | Subtract/divide by **ImageNet** mean/std (or other constants shipped with `IMAGENET1K_V2`) |
| Deterministic cache key | Hash of ops list + params + source bytes |

Same ops list for `cohort`, `validation`, and `ambiguous`. `excluded` need not be preprocessed for scoring.

### 1.2 Forbidden (leakage / researcher degrees of freedom)

| Forbidden | Why |
|---|---|
| Mean / std / median / quantiles of pixels or features estimated on **all scored works** | Mixes val/ambiguous into the “normal” imaging pipeline (extends L1–L2 into preprocess) |
| Same estimates on **`validation` or `ambiguous` only** | Direct L6 |
| Same estimates on **`cohort` only** for preprocess whitening / reference matching | Avoid: couples geometry/color pipeline to cohort composition; keep corpus fits for **Phase 4 scoring normals**, not preprocess. Exception: none for v1 — use published or per-image only |
| Histogram matching / color transfer to a reference painting or to cohort average image | Reference choice is a fit; val must not influence it |
| Adaptive crop / attention crop / “tight bbox” fitted across the set | Can encode corpus layout; if used at all, must be purely per-image CV with fixed thresholds, not tuned on val |
| Choosing resize, pad color, denoise strength, or CLAHE by inspecting SK-A-3934 or SK-A-4096 outputs | Classic L6 peeking (N_val=1 makes this fatal) |
| Reopening D13 (backbone) because preprocess+val “looks better” with another net | L6; DINOv2 only under prior locked contingency, not val-driven |
| Heavy denoise / blur chosen to stabilize embeddings if that choice was guided by val ranks | Signal erasure + leakage |

**Boundary:** Fitting cohort normals on embeddings/hand-built features is **Phase 4 (T041)** on `split=cohort` only — not a preprocess step. Do not sneak z-scoring or PCA into the cache writer.

---

## 2. Global constants

If a transform needs a global vector/scalar:

1. Use **published** constants tied to the locked backbone (D13), e.g. ImageNet mean `(0.485, 0.456, 0.406)` and std `(0.229, 0.224, 0.225)` as used by torchvision ResNet50 `IMAGENET1K_V2`.
2. Or use a **literal fixed** constant chosen in the design doc (e.g. pad RGB = ImageNet mean, or pad = 0) — write the numbers in T020 before Wave B.
3. **Do not** compute mean/std (or PCA, whitening matrix, reference histogram) from our 23+1+1 images, even cohort-only, for preprocess.

Per-image statistics (e.g. that image’s own min/max for a display stretch) are allowed only if Features T023 agrees they do **not** wipe brushstroke/palette signal; default stats preference is **avoid** per-image histogram equalization for the shared cache.

---

## 3. Resize / crop and anomaly-score bias

### 3.1 How geometry confounds scores

| Policy | Risk to embeddings | Risk to hand-built texture/color |
|---|---|---|
| **Stretch** to square | Distorts shape; ResNet sees non-physical proportions | **Worst** — anisotropic stretch invents directional texture; brushstroke/orientation stats become aspect-ratio artifacts |
| **Center crop** to square | Drops margins; composition shifts | Loses edge strokes; portrait vs landscape paintings lose different fractions → split-correlated bias if aspect mix differs |
| **Letterbox** (aspect-preserving + pad) | Pad is non-painting; mild, **constant** effect if pad value fixed | Preserves stroke geometry; pad can dilute **global** palette stats in proportion to pad area — acceptable if documented and identical rule for all splits |

Aspect ratios among Rembrandt oils vary (inventory spans portraits, group scenes, landscapes). Stretch would systematically couple “how wide the panel is” to texture anomaly — indefensible.

### 3.2 Recommended policy (one recipe)

**Aspect-preserving letterbox to a fixed square *T*×*T*, then (for ResNet only) apply the published torchvision preprocess on that tensor/image.**

Concrete defaults for CV to lock in T020 (numbers may match backbone needs; stats cares about the *class* of op):

1. Convert to RGB.  
2. Resize so **long edge = *T*** (or short edge — pick one and freeze); **never** independent Fx/Fy scales.  
3. **Letterbox** pad to *T*×*T* with pad RGB = **ImageNet mean** (published), not a corpus gray.  
4. Embedding path: apply ResNet50 `IMAGENET1K_V2` recommended resize/crop/normalize **as published** (if that implies an extra center crop, it is still a published recipe — not fitted here).  
5. Hand-built feature path: prefer the **letterboxed *T*×*T* image before** any ImageNet center-crop so texture stats see the full painting; Features confirms in T023.

**Reject for v1:** stretch-to-square; random crop; val-tuned crop.

Document *T* and pad RGB in the preprocess design before implementation. Apply identically to cohort, validation (SK-A-3934), and ambiguous (SK-A-4096).

---

## 4. Thresholds and validation peeking (L5 / L6 reminder)

- **O02 / O04 / score thresholds:** deferred to Phase 4 design gate (T040). Preprocess outputs pixels/tensors only — **no** anomaly flags, ranks, or τ cutoffs in Phase 2.
- **QC (T022):** before/after grids and failure logs are fine. Do **not** use “does SK-A-3934 look more anomalous after op X?” as a selection criterion. QC may include that image for visual sanity only, with ops already locked.
- **Inventory reminder:** T043 success uses **validation N=1** only; ambiguous is exploratory (D21). Preprocess must not be optimized against either.

---

## 5. Checklist for CV T020 / Review T025

| # | Check |
|---|---|
| P1 | Ops list is finite, deterministic, identical across splits |
| P2 | No corpus-estimated mean/std/PCA/histogram reference in preprocess |
| P3 | ImageNet (or other published) constants only, values written in design |
| P4 | No stretch; letterbox policy locked |
| P5 | No threshold / fusion / “flagged” logic in preprocess code |
| P6 | No parameter choice justified by validation or ambiguous scores (L6) |
| P7 | Cache keyed so changing ops forces rebuild — no silent reuse of leaky caches |

---

## 6. Hand-off

| Who | Action |
|---|---|
| **CV (T020)** | Draft ops consistent with §§1–3; cite this memo for leakage constraints |
| **Features (T023)** | Confirm letterbox + *T* leave brushstroke/palette stats meaningful; reject stretch |
| **Human** | Lock preprocess design before Wave B (T021) |
| **Stats** | No scoring code this phase; O02/O04 at Phase 4 |
| **Review (T025)** | Audit P1–P7 after implementation |

**Proposed decision fragment (optional human lock):** Preprocess uses per-image ops + published ImageNet constants only; aspect-preserving letterbox (no stretch); no corpus-fitted preprocess stats; no val/ambiguous-driven op selection (L6).
