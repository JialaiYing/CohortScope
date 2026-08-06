# Phase 2 review (Wave C / T025)

**Role:** Code Reviewer  
**Date:** 2026-08-06  
**Artifacts reviewed:** `preprocess.py`, `data/preprocessed/preprocess_v1/` (+ `manifest.json`, `rgb/`, `cnn/`), `results/qc_preprocess_v1/`, T020/T023/T024 memos, D12–D13, D19–D21, D26  

---

## Verdict (orchestrator)

**PASS with patches**

Wave B implements the locked `preprocess_v1` two-branch recipe (D26). Cache is complete (25/25 RGB + CNN; excluded absent). Stats P1–P7 structural leakage checks pass for this phase. QC grid is honesty-compatible (fixed aspect sampling; no val-driven retune).

No **must-fix** leakage or ops defects. **Should-fix** is mainly honesty about geometry: Branch H is identity on Phase 1 JPEGs, but those JPEGs are **width=1500** IIIF (not true long-edge 1500 for tall portraits). Document before Phase 3; do **not** reopen ops from validation looks.

---

## 1. Ops vs D26 / T020 (two-branch contract)

| Contract | Design (D26) | Implementation | Result |
|---|---|---|---|
| Shared decode | Load → EXIF transpose → RGB | `decode_rgb` | **OK** |
| Branch H | Identity geometry, uint8 RGB, lossless PNG | Save decoded RGB as PNG; no resize/crop/pad | **OK** (identity) |
| Branch C | `Resize(256)` + `CenterCrop(224)` + ImageNet normalize | `CNN_TRANSFORM` matches; fixed mean/std | **OK** |
| Worklist | `cohort` ∪ `validation` ∪ `ambiguous` from SQLite | `load_scored_works` filters splits | **OK** |
| Skip `excluded` | Yes | Not in query; absent from cache | **OK** |
| Features reads H only | T023 contract | No Branch C consumption in Features code (none yet); soft comment ask below | **OK** / note |
| No Phase 3 embeddings | Phase 2 only | No ResNet forward in `preprocess.py` | **OK** |
| Scope | No Gradio/FastAPI/DINOv2/finetune | Absent | **OK** |

**Stats T024 letterbox vs locked D26:** T024 preferred letterbox for a shared square path; human locked T020/D26 (identity H + published center-crop C). Features T023 explicitly declined letterbox on H. Review judges against **D26**, not the superseded letterbox preference. **No stretch** anywhere — satisfied.

Spot-check tensors: all CNN caches `(3, 224, 224)` float32; sample densities look ImageNet-normalized (values outside `[0,1]`).

QC grid visual: Branch H ≈ raw IIIF framing; Branch C denorm shows expected center square — labeled “viz only.”

---

## 2. Stats P1–P7 leakage checklist

| # | Check | Status | Evidence |
|---|---|---|---|
| P1 | Finite, deterministic ops; identical across splits | **PASS** | Same `decode_rgb` + `CNN_TRANSFORM` for all scored IDs; no split-conditional ops |
| P2 | No corpus-estimated mean/std/PCA/hist ref | **PASS** | Only published ImageNet constants; no pixel aggregation over the set |
| P3 | Published constants written in design/code/manifest | **PASS** | mean/std in `preprocess.py` + `manifest.json` |
| P4 | No stretch; geometry policy locked | **PASS** (under D26) | Identity H; published Resize/CenterCrop C. Letterbox not used (by lock, not by omission) |
| P5 | No threshold / fusion / flags in preprocess | **PASS** | Outputs pixels/tensors + QC only |
| P6 | No val/ambiguous-driven parameter choice (L6) | **PASS** | Recipe locked pre-Wave B; QC sampling by aspect quantiles among cohort, not scores |
| P7 | Recipe-keyed cache; no silent mix | **PASS** | Path `preprocess_v1/`; manifest `recipe_id`; `--force` overwrites same recipe only |

**L6 residual:** With validation N=1, any future “tweak crop so SK-A-3934 looks stranger” would fail P6. Ops are locked — do not reopen from T043 peeks.

---

## 3. Cache / manifest completeness

| Check | Result |
|---|---|
| `# rgb PNG == # cnn .pt == 25` | **Yes** (25 / 25 / 25) |
| Sets equal `manifest.object_numbers` | **Yes** |
| Match SQLite scored splits | **Yes** (23 cohort + 1 validation + 1 ambiguous) |
| Excluded (5) absent from cache | **Yes** |
| Manifest fields (recipe, cnn params, versions, splits) | **Present** |

---

## 4. QC honesty

| Item | Finding |
|---|---|
| `failures.csv` | 25 rows, all `ok=true`; **0 failures** — claim confirmed |
| `before_after_grid.png` | 4 cohort (aspect-quantile pick) + SK-A-3934 + SK-A-4096; L→R raw \| H \| C denorm |
| Used to retune on validation? | **No evidence** — sampling is aspect-based; recipe matches locked design |
| Detail 100% crop (T020 §6.1 / T023 soft ask) | **Not present** — thumbnails only; non-blocking |

---

## 5. Geometry honesty (main should-fix)

Branch H correctly copies source JPEG geometry (`src_eq_png` for all 25). However, Phase 1 IIIF URL uses `full/{edge},` (**width** = 1500), not true **long-edge** 1500:

| | N |
|---|---:|
| Long edge == 1500 (typically landscape / wide) | 5 |
| Long edge > 1500 (tall portraits; width=1500) | 20 |

Examples: SK-A-3934 PNG `1500×1854`; SK-A-5033 `1500×2349`; SK-A-1935 `1500×1056` (long=1500).

**Impact:** Not leakage. Features get *more* pixels on tall works than “long-edge 1500” wording implied — brushstroke survival is fine. The mismatch is **documentation vs D12 wording**, inherited from Phase 1 acquisition, not a Wave B transform bug.

**Do not** “fix” by val-looking crops or stretching tall works down in Phase 2. Prefer: note in manifest/write-up; optional later re-acquire with true long-edge (Data / human) if judges need D12 literalism.

---

## 6. Findings ranked

### Must-fix

*(none)*

### Should-fix (T026 / docs — before Phase 3 code)

1. **Document width-1500 vs long-edge-1500** in `manifest.json` note or a short `results/qc_preprocess_v1/geometry_note.md` (and keep Features/Phase 3 consumers aware).  
2. **Consumer contract comment** in `preprocess.py` module docstring: Features reads Branch H PNGs only; Branch C is embeddings-only (T023 soft ask).  
3. **T026 cleanup:** remove any one-off review scripts; confirm QC paths are the canonical artifacts.

### Nice-to-have

1. Optional 100% detail crop strip on Branch H for Features readiness (T020 §6.1).  
2. Assert `width == 1500` (actual IIIF behavior) in preprocess sanity checks, or assert long-edge after a future re-acquire.  
3. Phase 3: Features loader refuses Branch C paths.

---

## 7. Recommendation

| Gate | Call |
|---|---|
| Phase 2 Wave B quality | **PASS** |
| Blocking defects | **None** |
| Overall for orchestrator | **PASS with patches** → **T026** (doc honesty + comment + cleanup), then Phase 3 design gate |

Do **not** start embedding/feature extraction until T026. Do **not** retune preprocess from SK-A-3934 / SK-A-4096 appearance.
