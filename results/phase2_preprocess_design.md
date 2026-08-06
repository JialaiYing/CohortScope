# Phase 2 preprocess design (normalize pipeline)

**Task:** T020 · **Role:** cv · **Date:** 2026-08-05  
**Status:** **LOCKED** 2026-08-05 (human approved as-is; D26) — Wave B (`preprocess.py`, T021–T022) unlocked  
**Inputs:** D12, D13, D19–D21, D26; L6 (T017 §4); `config.py`; `results/inventory.md`; Phase 1 images at `data/images/{object_number}.jpg`  
**Peer sign-off:** Features T023 Approve; Stats T024 (per-image + published constants; Branch C published crop OK)

---

## Verdict (read this first)

| Topic | Recommendation |
|---|---|
| Goal | Reduce scan/format confounds for ResNet50; leave brushstroke/texture intact for Features |
| Lighting / color stats | **Per-image geometry + fixed ImageNet constants only** — no cohort-fitted pixel normalize |
| Two targets | **CNN:** 224×224 ImageNet tensor · **Handcrafted:** RGB uint8, long-edge **1500** (D12 as-is) |
| Who gets preprocessed | `cohort` ∪ `validation` ∪ `ambiguous` with images (**N=25**); skip `excluded` |
| Leakage (L6) | Recipe locked here from prior knowledge + ImageNet convention — **not** tuned on val/ambiguous |
| Implement | **Wave B unlocked** — T021–T022 |

---

## 1. Exact ops pipeline (order matters)

Source of truth for pixels: Phase 1 IIIF JPEGs (`IIIF_MAX_EDGE=1500`, D12). Sample check: RGB, long edge already 1500, short edge varies (~1000–2000).

### 1.1 Shared decode (all scored works)

| Step | Op | Notes |
|---:|---|---|
| 1 | Load `data/images/{object_number}.jpg` | Fail → QC failure log; do not invent pixels |
| 2 | Ensure RGB | `convert("RGB")` if mode ≠ RGB (defensive; corpus is already RGB) |
| 3 | Drop EXIF orientation if present | Apply once so layout is deterministic; then strip metadata on write |
| 4 | No further color-space convert | Stay in decoded sRGB-like RGB; do **not** go Lab/HSV for the cache |

After step 4 we branch. Same decoded RGB feeds both caches so Features and CV share one decode policy.

### 1.2 Branch H — handcrafted / texture path (Features)

| Step | Op | Notes |
|---:|---|---|
| H5 | Identity geometry | Keep native aspect; long edge remains 1500 (D12). **No** center-crop, **no** pad |
| H6 | Dtype | `uint8`, channels last, H×W×3 |
| H7 | Write cache | Lossless PNG (see §4) |

Intent: Features (T032) sees the same spatial sampling as the museum IIIF deliverable. Brushstroke / wavelet / local stats must not fight an extra downscale or crop.

### 1.3 Branch C — ResNet50 path (embeddings, Phase 3 T030)

Use torchvision **eval** transforms matching `IMAGENET1K_V2` (D13). Applied to the **same** decoded RGB as Branch H (not to a second JPEG decode with different libjpeg quirks if we can avoid it — implement from Branch H array or from PNG cache).

| Step | Op | Notes |
|---:|---|---|
| C5 | `Resize(256)` | torchvision: **shorter** side → 256; aspect preserved |
| C6 | `CenterCrop(224)` | Square 224×224 |
| C7 | `ToTensor()` | float32 CHW in **[0, 1]** |
| C8 | `Normalize(mean, std)` | **Fixed** ImageNet: mean=`(0.485, 0.456, 0.406)`, std=`(0.229, 0.224, 0.225)` |
| C9 | Write cache | `float32` tensor `3×224×224` (see §4) |

**Lighting note:** C8 is the only intensity “normalize.” It is a published constant, not estimated from Cohortscope images (aligns with Stats T024: no global fit on val/ambiguous; preprocess itself should not fit cohort pixel moments either).

### 1.4 Determinism knobs (must be fixed in code + manifest)

- Pillow / torchvision versions recorded in cache manifest
- Resize interpolation: torchvision default for `Resize` (**bilinear**); do not change per image
- Seed: N/A (no stochastic aug)
- Recipe id: `preprocess_v1` (bump if any op changes)

---

## 2. Target size(s) — CNN vs handcrafted

| Consumer | Spatial target | Why |
|---|---|---|
| ResNet50 (`BACKBONE=resnet50`, `IMAGENET1K_V2`) | **224×224** after Resize(256)+CenterCrop(224) | Matches pretrained training protocol; keeps D13 honest (no ad-hoc input size that forces finetune) |
| Hand-built texture / palette / brushstroke | **Long-edge 1500 RGB uint8** (no crop) | D12 already chose quality vs disk; further downscale or aggressive crop would erase the signal Features owns (D05) |

**May they differ?** Yes — deliberately. One square crop optimized for ImageNet priors is a poor default for stroke-scale statistics on panoramic vs tall portraits. Two caches, one `object_number` join key.

**Not chosen:** letterbox-to-224 (pads change ImageNet prior); stretch-to-224 (destroys aspect); multi-crop / ten-crop (VRAM + complexity; revisit only if T043 fails and Stats asks).

---

## 3. Deliberately will NOT do

| Forbidden op | Why |
|---|---|
| Denoise / bilateral / NL-means / JPEG re-compress “cleanup” | Erases brushstroke high frequency |
| Sharpen / unsharp mask | Fake texture; Features confound |
| Histogram matching / equalization **across** works | Cohort-global appearance leakage; L6 / palette death |
| CLAHE or heavy per-image contrast stretch | Changes local gradient stats Features will trust |
| Color transfer / white-balance fit on cohort | Researcher DOF; contaminates D05 color signal |
| Fit mean/std / PCA whitening on cohort **pixels** for preprocess | Belongs to Stats feature-space if anywhere; not in Phase 2 cache (see § Stats hand-off) |
| Saliency / face / content crop | Non-deterministic composition; validation-tuned DOF risk |
| Random aug (flip, jitter, crop) | Scoring must be deterministic |
| Finetune ResNet50 / swap to DINOv2 | D13; out of scope until ResNet50 signal fails |
| Gradio / FastAPI | D07–D08 |
| Using `validation` / `ambiguous` scores to pick resize, crop, or normalize | **L6** |
| Preprocessing `excluded` into the scored cache | Not scored (inventory); waste + confusion |

Mild per-image ops that remain **out** unless human reopens: auto white-balance, percentile clipping, frame/mat detection. Prefer documenting illumination as a limitation over “fixing” it in pixels.

---

## 4. Cache layout (deterministic, keyed by `object_number`)

```text
data/preprocessed/
  preprocess_v1/
    manifest.json          # recipe, versions, split list, created_at
    rgb/
      {object_number}.png  # Branch H — uint8 RGB, long-edge 1500
    cnn/
      {object_number}.pt   # Branch C — float32 tensor [3,224,224], ImageNet-normalized
  qc/                      # T022 outputs (or under results/; see §6)
```

**Join key:** `object_number` (e.g. `SK-A-3934`) — same as `data/images/` and SQLite `works.object_number`.

**`manifest.json` (minimum):**

- `recipe_id`: `preprocess_v1`
- `source_edge`: 1500 (D12)
- `cnn`: `{ "resize_short": 256, "crop": 224, "mean": [...], "std": [...], "weights": "IMAGENET1K_V2" }`
- `splits_included`: `["cohort","validation","ambiguous"]`
- `object_numbers`: sorted list written
- `pillow` / `torch` / `torchvision` versions
- `git` or content hash of this design memo path (optional)

**Overwrite policy:** same path → replace only if recipe_id unchanged *or* explicit `--force`; recipe bump → new `preprocess_v2/` directory (never silently mix recipes).

**Disk:** ~25 PNGs ≈ same order as current JPEGs (≲15 MB) + 25×(3×224×224×4) ≈ **15 MB** tensors — negligible vs 5 GB budget.

---

## 5. Which splits get preprocessed

| Split | N (inventory) | Preprocess? | Rationale |
|---|---:|---|---|
| `cohort` | 23 | **Yes** | Fit normals later; must have features |
| `validation` | 1 | **Yes** | Score + T043; never fit (D19–D21) |
| `ambiguous` | 1 | **Yes** | Exploratory score only (D21); never fit / never T043 |
| `excluded` | 5 | **No** | Not scored |

**Recommendation:** preprocess exactly **`cohort ∪ validation ∪ ambiguous` with non-null `image_path`** → **N=25**. Selection reads `split` from SQLite (`D22`), not from folder listing (avoids accidental `smoke_*` or excluded JPEGs).

Preprocess does **not** look at labels to change ops — only to filter the worklist (L6-safe).

---

## 6. QC plan (T022)

### 6.1 Before / after sample grid

Write under `results/qc_preprocess_v1/` (preferred for review) or `data/preprocessed/qc/`:

| Panel | Content |
|---|---|
| Before | Raw IIIF JPEG thumbnails |
| After H | Branch H PNG (should look identical aside from container) |
| After C | Branch C tensor **denormalized** to uint8 for display only (multiply std, add mean, clip) — label clearly “viz only” |

**Sample set (fixed, not chosen by score):**

- 4 cohort works spanning aspect ratios (e.g. wide landscape + tall portrait + large group + bust) — pick by `object_number` sort + aspect quantile, **not** by anomaly
- 1× `validation` (SK-A-3934)
- 1× `ambiguous` (SK-A-4096)

Grid file: `results/qc_preprocess_v1/before_after_grid.png` (+ optional per-id strips).

**Pass criteria (human / Features T023):**

- Branch H: stroke/impasto still visible at 100% crop of a high-detail region
- Branch C: denorm crop is a plausible painting center (flag if mostly frame/mat — document, do not retune on val)

### 6.2 Failure log

`results/qc_preprocess_v1/failures.csv` (or `.jsonl`):

| Column | Meaning |
|---|---|
| `object_number` | ID |
| `split` | from DB |
| `stage` | `load` \| `rgb` \| `cnn` \| `write` |
| `error` | short message |
| `ok` | true/false |

Expect **0** failures on current inventory (0 missing images). Any failure blocks “Phase 2 done” for that id until fixed or explicitly waived.

### 6.3 Sanity counts

Assert: `# rgb PNGs == # cnn tensors == 25` and sets equal `object_number` list in manifest.

---

## 7. 4 GB VRAM / Windows notes (preprocess vs later embed)

| Stage | Device | Constraint |
|---|---|---|
| Phase 2 preprocess (T021) | **CPU** | Pillow + torchvision CPU transforms; no GPU required |
| Phase 3 ResNet50 (T030) | CUDA RTX 3050 **4 GB** | `eval()` + `torch.no_grad()`; **batch_size = 1** (safe default; try 2 only if memory OK); load one backbone; no extra models |
| Mixed precision | Optional later | Not required for N=25 |
| Windows paths | Use `pathlib` | Object numbers like `SK-C-5` are fine as filenames |

Preprocess must not leave large GPU allocations; embedding script should construct model → loop → free. No DINOv2 “just to compare” on this card without dropping ResNet50 (D13).

---

## Hand-off — Stats (T024) & Features (T023)

### Stats (global vs per-image) — coordinate

| Layer | CV preprocess stance | Stats owns |
|---|---|---|
| Pixels | Per-image geometry + **fixed** ImageNet mean/std only | Confirm no cohort pixel fit in preprocess (this memo) |
| Features / scores | N/A | Cohort-only mean/std, robust scales, thresholds (L1); never val/ambiguous |
| Choosing recipe | Locked pre-val (L6) | T024 should restate: do not reopen crop/normalize from T043 |

If T024 wants a **different** global color rule, it must be proposed as a design change + human lock — not slipped into Wave B.

### Features (T023) — brushstroke check

- Review Branch H: identity-at-1500 is intentional
- Confirm forbidden list (§3) is enough for planned O03 shortlist
- Sign off before Wave B implementation

---

## Wave B implementation sketch (not started)

When human locks this memo:

1. `preprocess.py` — read SQLite splits → Branch H + C → write `data/preprocessed/preprocess_v1/`
2. T022 QC grid + failure log
3. No embedding extraction in Phase 2

---

## Human lock

Approved **as-is** 2026-08-05 → **D26**. Features T023 and Stats T024 complete with no Wave B blockers.
