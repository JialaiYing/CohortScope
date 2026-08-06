# Phase 3 review (Wave C / T037)

**Role:** Code Reviewer  
**Date:** 2026-08-06  
**Artifacts reviewed:** `embed.py`, `features.py`, `data/embeddings/embed_v1/`, `data/features/`, `results/qc_embed_v1/`, `results/qc_features_v1/`, T030/T031/T035 memos, D29  

---

## Verdict (orchestrator)

**PASS**

Phase 3 Wave B meets D29 and the T035 matrix contract (M1–M6). Embedding and feature ID sets match preprocess scored N=25; Branch C vs H paths are correct; no scoring / z-scores / cohort fits in extractors. Recipe pins `embed_v1` + `features_v1` are present.

No **must-fix**. Light **should-fix** items fit **T038** cleanup and do not block Phase 4 design (T040).

---

## 1. Matrix integrity (M1–M3)

| Check | Result |
|---|---|
| Preprocess / embed / feature ID sets equal | **Yes** (sorted N=25 identical) |
| `matrix.pt` shape / dtype | `(25, 2048)` float32; all finite |
| `vectors/*.pt` count | 25; each matches matrix row (maxdiff=0 on spot IDs) |
| `features_v1.csv` | 25 rows; columns = `object_number` + 8 O03 names |
| Split counts | cohort 23 / validation 1 / ambiguous 1 |
| Excluded (5) absent | **Yes** |
| Join key | `object_number` only |

Spot paths exist for SK-A-1935, SK-A-3934, SK-A-4096 on both Branch C `.pt` and Branch H `.png`.

---

## 2. Branch contracts (D26 / D29)

| Signal | Designed input | Implementation | Result |
|---|---|---|---|
| Embeddings (`embed.py`) | Branch C `preprocess_v1/cnn/*.pt` | `load_branch_c` only; manifest `input=branch_c_pt` | **OK** |
| Features (`features.py`) | Branch H `preprocess_v1/rgb/*.png` | RGB PNG only; manifest `no_branch_c=true` | **OK** |
| Cross-read | Forbidden | No H→ResNet; no C→hand-built | **OK** |

Worklists: embed from preprocess manifest; features from SQLite scored splits — both yield the same 25 IDs (acceptable; single source would be nicer).

---

## 3. No premature scoring (M4 / T035 §4)

| Forbidden in Phase 3 | Status |
|---|---|
| Anomaly scores / ranks / flags | **Absent** |
| Cohort mean/std / z-scores / PCA / whitening | **Absent** |
| Thresholds / fusion / pass-fail | **Absent** |
| Val-driven column or backbone choice | **Absent** |
| Gradio / FastAPI / DINOv2 / finetune | **Absent** |

Allowed QC only: completeness, finite checks, L2 min/median/max logged in embed manifest — **not** used to retune on SK-A-3934. Feature CSV has no forbidden score tokens.

**M6:** Fit code does not exist in extractors — Phase 4 (T041) still owns cohort-only normals.

---

## 4. Recipe pins (M5)

| Artifact | Pin |
|---|---|
| `data/embeddings/embed_v1/manifest.json` | `recipe_id=embed_v1`, ResNet50 / `IMAGENET1K_V2`, `dim=2048`, `batch_size=1`, `preprocess_v1`, D29 |
| `data/features/manifest.json` | `recipe_id=features_v1`, 8 O03 columns, Branch H source, `no_zscore` |
| Dictionary | `features_v1_dictionary.md` present with meanings + compute defaults |

Backbone: frozen eval, `fc→Identity`, `batch_size=1`, CUDA used — matches T030.

---

## 5. QC honesty

| Log | Finding |
|---|---|
| `results/qc_embed_v1/failures.csv` | 25× `ok=true`; L2 norms recorded |
| `results/qc_features_v1/failures.csv` | 25× `ok=true`; 0 non-finite feature values |

---

## 6. Findings ranked

### Must-fix

*(none)*

### Should-fix (T038 — non-blocking)

1. **Features manifest parity** — add `design` / `decision: D29` / `matrix_contract` pointers like `embed_v1` for audit symmetry.  
2. **Hue wording** — shortlist mentioned HSV; implementation uses Lab hue (chroma-weighted). Dictionary is correct; align T031 text or leave a one-line note so Phase 4 writers do not say “HSV.”  
3. **Worklist source** — optional: both extractors read the same authority (preprocess manifest *or* SQLite) to avoid future drift.

### Nice-to-have

1. Unit test: ID-set equality preprocess ↔ embed ↔ features.  
2. Phase 4 loader that hard-fails if `split != cohort` enters fit (structural L1).

---

## 7. Recommendation

| Gate | Call |
|---|---|
| Phase 3 Wave B quality | **PASS** |
| Blocking defects | **None** |
| Next | **T038** cleanup + git push (D24/D28), then Phase 4 design gate (**T040** — O02/O04) |

Do **not** start scoring until T040 is human-locked. Do **not** drop/reweight O03 columns after peeking at validation.
