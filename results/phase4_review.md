# Phase 4 review (Wave C / T044)

**Role:** Code Reviewer  
**Date:** 2026-08-08  
**Artifacts reviewed:** `score.py`, `results/scores/scores_v1.csv`, `results/scores/fit_manifest.json`, `results/validation_report.md`, `results/phase4_scoring_design.md`, D30  

---

## Verdict (orchestrator)

**PASS**

Scoring implements D30 correctly: cohort-only fits with LOO for cohort self-scores; validation/ambiguous use the full cohort fit and never enter μ/σ/centroid estimation; O04 applied as pre-registered p95/median tiers → **`weak`** for SK-A-3934; no evidence of post-hoc retuning; ranked table remains decomposable (`z_A`, `z_B`, drivers, eight `z_<feature>`).

No **must-fix**. Do **not** rewrite the method in Phase 5 for a weak N=1 outcome unless the human explicitly opens T050.

---

## 1. Cohort-only fit + LOO

| Rule | Implementation | Result |
|---|---|---|
| Fit mask = `split=cohort` only | `cohort_idx` / `cohort_mask` from SQLite; asserts 23/1/1 | **OK** |
| Signal A centroid | Cohort LOO mean of L2-normalized vectors; val/ambiguous → full cohort centroid | **OK** |
| Signal B column μ/σ | Cohort LOO for cohort rows; full cohort for val/ambiguous | **OK** |
| `z_A` / `z_B` scales | μ/σ of cohort raw `d_A` / `d_B` (LOO distances already) | **OK** |
| Val/ambiguous never in fit | No path adds them to `cohort_idx` | **OK** |
| Manifest | `loo: true` for both signals; N_cohort=23, N_scored=25 | **OK** |

Independent check: `combined = z_A + z_B` for all 25 rows; dominant_signal matches `A if z_A≥z_B else B`.

---

## 2. No validation retuning (L5–L6)

| Check | Finding |
|---|---|
| O04 cutoffs | Hard-coded median / p95 on cohort `combined`; same text in design, code, report |
| AUC / learned weights / column drop | Absent |
| Order of operations | Score all → write CSV/manifest → **then** `o04_outcome` + report |
| Fit manifest | Stores **rules** + fit summaries; **not** val `combined` or pass/fail outcome |
| Report honesty | States rules not changed after seeing validation; tiny-N limits |

Ambiguous SK-A-4096 ranks **#2** (combined≈2.28) but is correctly **excluded** from O04 (D21). That is not leakage — it is exploratory scoring as designed. Do not promote it into the success metric to “rescue” a weak primary result.

---

## 3. O04 applied correctly

Recomputed from `scores_v1.csv`:

| Quantity | Value |
|---|---|
| SK-A-3934 `combined` | 0.282608 |
| Cohort median | −0.116810 |
| Cohort p95 | 2.106898 |
| Clears median / p95 | True / False |
| Outcome | **`weak`** |
| Rank among 25 | 10 |
| Drivers | B-dominant; `hue_circ_std`, `grad_mag_std` |

Matches `validation_report.md`. Sensitivity (p90/p99) reported; decision uses p95 only. No AUC.

---

## 4. Decomposability (D05)

| Column family | Present |
|---|---|
| `d_A`, `z_A`, `d_B`, `z_B`, `combined`, `rank_combined` | Yes |
| `dominant_signal`, `driver_B_1`, `driver_B_2` | Yes |
| Eight `z_<O03 feature>` | Yes |
| Single opaque score only | **No** |

Signal A driver is implicit (`d_A` / cosine-to-centroid). Design named `embed_cosine_to_centroid` — optional constant column missing (should-fix below), but audit trail is sufficient via `d_A`/`z_A`.

---

## 5. Scope / method critique (not a fail)

**Scientific honesty:** O04=`weak` is the correct call. Validation is barely above the cohort median and far from the p95 bar; embedding channel is near-null (`z_A≈0.02`). Phase 5 must narrate this as **weak / inconclusive under N=1**, not as a soft pass.

**Not required for PASS:** redesigning fusion, swapping to max(`z_A`,`z_B`), DINOv2, or folding SK-A-4096 into T043 — those would be scope creep or L6 unless human reopens O02/O04 via T050.

---

## 6. Findings ranked

### Must-fix

*(none)*

### Should-fix (T046 — non-blocking)

1. **Design memo status** — `phase4_scoring_design.md` header still says “DRAFT — awaiting human lock”; update to **LOCKED (D30)** for audit coherence.  
2. **Repo-relative paths** in `fit_manifest.json` / validation report artifact list (currently absolute Windows paths).  
3. **Optional `driver_A`** column = `embed_cosine_to_centroid` for symmetry with B drivers.

### Nice-to-have

1. Unit test: LOO excludes self from centroid; val uses N=23 fit.  
2. Assert fit_manifest contains no validation score fields before merge.

---

## 7. Recommendation

| Gate | Call |
|---|---|
| Phase 4 Wave B quality / leakage | **PASS** |
| O04 honesty | **Confirmed `weak`** — do not sugarcoat |
| Blocking defects | **None** |
| Next | **T046** cleanup + push; **T045** honest narrative; **T050** only if human opens scope-tight fixes |

Phase 5: document method + limits; default stays tables-only (D07/D08). Do not claim “working” — briefing gate failed to reach **pass**.
