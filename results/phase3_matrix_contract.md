# Phase 3 → Phase 4 matrix contract

**Task:** T035 · **Role:** stats · **Date:** 2026-08-06  
**Status:** design contract for Wave B extractors + Phase 4 scoring  
**Inputs:** T030 `results/phase3_embedding_design.md`; T031 `results/phase3_feature_shortlist.md`; L1–L8 in `results/phase1_experimental_design.md` §4; D05, D13, D19–D21  
**No scoring code in Phase 3.**

---

## Verdict

| Topic | Rule |
|---|---|
| Join key | **`object_number` only** (e.g. `SK-A-3934`) — same as SQLite `works`, images, preprocess |
| Scored rows | `cohort` ∪ `validation` ∪ `ambiguous` (**N=25**); never `excluded` |
| CV delivers | `embed_v1` matrix: float32 `[N, 2048]` + aligned ID list |
| Features delivers | `features_v1` table: `object_number` + **8** O03 scalars |
| Phase 3 may | Extract raw matrices; QC completeness/finiteness |
| Phase 3 must **not** | Fit normals, z-score, PCA, ranks, thresholds, flags, or peek at val/ambiguous for model choice (L5–L6) |
| Phase 4 fits | **`split=cohort` rows only** (L1–L2); then apply transforms to all scored rows |

---

## 1. Join keys and identity

| Key | Role |
|---|---|
| `object_number` | **Primary join** across embeddings, features, `works.split`, inventory |
| `uri` | Optional audit only; do not use as matrix row index |
| Row order | Prefer **sorted** `object_numbers` in both matrices; Stats re-aligns by key if needed |

**Integrity checks before T041:**

1. Embedding ID set == feature ID set == preprocess scored set (N=25).  
2. Every ID has exactly one `works.split` ∈ {`cohort`,`validation`,`ambiguous`}.  
3. No duplicate `object_number` (L7).  
4. Fail closed on missing row — **no imputation**.

---

## 2. Required artifacts (Wave B)

### 2.1 Computer Vision (T036) — signal A

| Artifact | Spec |
|---|---|
| Path | `data/embeddings/embed_v1/` |
| `matrix.pt` | Dict with `object_numbers: list[str]` and `X: float32[N,2048]`; `X[i]` ↔ `object_numbers[i]` |
| `vectors/{id}.pt` | Optional per-ID `[2048]` (debug) |
| `manifest.json` | `recipe_id=embed_v1`, backbone, weights, `dim=2048`, preprocess recipe, ID list, `splits_included` |
| QC | `results/qc_embed_v1/failures.csv` + completeness (N=25, all finite) |

**Not in CV output:** PCA, whitening, cohort mean subtraction, distances, ranks.

### 2.2 Feature Engineering (T032/T033) — signal B

| Artifact | Spec |
|---|---|
| Path | `data/features/features_v1.parquet` **or** `.csv` (pick one at implement; document in feature dict) |
| Columns | `object_number` + O03 eight: `grad_mag_mean`, `grad_mag_std`, `grad_orient_entropy`, `laplacian_var`, `lbp_entropy`, `glcm_contrast`, `lab_chroma_mean`, `hue_circ_std` |
| Dictionary | Short column meanings (mirror T031 §1) beside the matrix |
| QC | Failure log for bad rows; no fill-in |

**Not in Features output:** cohort mean/std, z-scores, anomaly flags, fused scores.

### 2.3 Split labels (already exist)

| Source | Use |
|---|---|
| `data/cohortscope.sqlite` table `works` | Authoritative `split` for fit masks |
| `results/inventory.*` | Human audit (L8); expect cohort=23, validation=1, ambiguous=1 |

Stats must load splits from DB (or inventory export), **not** infer from filenames.

---

## 3. Cohort-only fit rules (Phase 4 — T041+)

Applies when scoring starts; Phase 3 extractors must leave room for this and not violate it early.

| Rule | Detail |
|---|---|
| **Fit mask** | Rows with `split == "cohort"` only (N=23) |
| **Apply mask** | After fit, transform/score **all** scored rows (cohort + validation + ambiguous) |
| **Never fit on** | `validation`, `ambiguous`, `excluded`, or “all Rembrandt search hits” (L1–L2) |
| **Signal A normals** | e.g. cohort mean embedding ± distance (Mahalanobis / cosine-to-centroid / kNN — exact rule = O02 at T040); parameters estimated on cohort embeddings only |
| **Signal B normals** | Per-column center/scale (mean/std or robust) on cohort feature rows only; then z or equivalent on all rows |
| **Fusion / thresholds** | O02 + O04 at Phase 4 design gate only (L5); not estimated by maximizing SK-A-3934 extremity |
| **Ambiguous** | Score and report; **exclude** from T043 success fraction (D21) |
| **Validation** | Score; **only** this split counts for T043 (D04/D19) |

**Decomposability (D05):** Phase 4 outputs must retain **per-signal** contributions (embedding driver + which hand-built columns drive) — not a single opaque number. Fusion must not destroy that audit trail.

---

## 4. Forbidden in Phase 3 (hard)

| Forbidden | Leakage / scope |
|---|---|
| Computing anomaly scores, ranks, or “flagged” columns | Premature O02; Contaminates QC with outcomes |
| Fitting mean/std/PCA/kNN on any split (incl. cohort) inside extractors | Belongs to T041; sneaking fits into `embed.py` / feature scripts blurs audit |
| Thresholds τ, top-k cutoffs, pass/fail | L5; O04 not locked |
| Choosing pool layer, backbone, or feature columns using val/ambiguous | L6 |
| Dropping or reweighting columns after seeing SK-A-3934 / SK-A-4096 | L6 |
| Imputing missing features/embeddings | Silent bias |
| Writing fused scores into SQLite in Phase 3 | Wrong phase |

**Allowed Phase 3 QC only:** load success, shape, finite checks, optional L2-norm band logging **without** comparing validation to cohort or tuning on that band.

---

## 5. Acceptance checklist (before T041)

| # | Check |
|---|---|
| M1 | Embedding and feature ID sets equal; N=25 |
| M2 | Join on `object_number` succeeds for every scored work |
| M3 | Split counts match inventory (23 / 1 / 1) |
| M4 | No z-scores, distances-to-cohort, or ranks in Phase 3 artifacts |
| M5 | Manifests pin `embed_v1` + `features_v1` recipes |
| M6 | Reviewer (T037) can verify L1–L2 structurally: fit code does not exist yet in extractors |

---

## 6. Hand-off

| Who | Action |
|---|---|
| **Human** | Lock T030 + T031 (O03); this contract constrains Wave B outputs |
| **CV T036** | Emit §2.1 only |
| **Features T032/T033** | Emit §2.2 only |
| **Stats T040** | Lock O02/O04 before implementing scores |
| **Stats T041–T043** | Fit cohort-only; score all; validate with tiny-N honesty |
| **Review T037** | Matrix completeness + no premature scoring |

**Wave B extraction may proceed after human lock of embed/O03 designs; scoring remains Phase 4.**
