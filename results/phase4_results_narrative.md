# Phase 4 results narrative (T045)

**Role:** literature · **Date:** 2026-08-08  
**Sources:** `results/validation_report.md`, `results/phase4_review.md`, `results/scores/scores_v1.csv`, `results/prior_art_brushstroke_auth.md`  
**Recipe:** `scores_v1` (D30)

---

## Verdict (one sentence)

**The method does not meet the pre-registered success bar.** O04 on the sole held-out validation work is **`weak`** — not pass, not a soft pass. With validation N=1 this outcome is **inconclusive**, not proof that cohort anomaly ranking “works” for reattribution triage.

---

## Method (what we actually ran)

1. **Cohort:** 23 Rijksmuseum oil paintings currently attributed to Rembrandt (`split=cohort`). Normals fitted on cohort only (LOO for cohort self-scores).
2. **Signal A:** ResNet50 embedding cosine distance to cohort centroid → `z_A`.
3. **Signal B:** Eight hand-built texture/color scalars → robust distances → `z_B`, with named feature drivers.
4. **Combined:** `combined = z_A + z_B`; ranks and `dominant_signal` preserved (decomposable; D05).
5. **Held-out check (O04):** Circle/workshop-style probe `SK-A-3934` (`validation`, N=1). Pre-registered tiers on cohort LOO `combined`: **pass** ≥ p95; **weak** median ≤ score < p95; **fail** < median. Rules were not retuned after seeing validation scores (review confirmed).

Ambiguous `SK-A-4096` was scored exploratorily and **excluded** from O04 (D21).

---

## O04 result — honest

| Item | Value |
|---|---|
| Object | `SK-A-3934` — *Borstbeeld van een lachende jonge man* |
| `combined` | 0.283 |
| Cohort median / p95 | −0.117 / 2.107 |
| Clears median / p95 | Yes / **No** |
| **O04** | **`weak`** |
| Rank among 25 scored | **10** (mid-pack) |
| Drivers | **B**-dominant; `hue_circ_std`, `grad_mag_std` |
| `z_A` / `z_B` | ≈0.023 / ≈0.260 — embedding channel near null |

Interpretation: the probe sits slightly above the cohort median and far below the p95 bar. Hand-built features contribute a mild lift; the CNN embedding does not flag it. That is a **weak** case under the locked rule — not recovery of a clear anomaly.

---

## What the ranks show (descriptive, not success)

From `scores_v1.csv` (rank 1 = most anomalous by `combined`):

- **Top of list are mostly cohort works** (e.g. `SK-A-4674` rank 1, several≈3.06, B-driven by `laplacian_var` / `glcm_contrast`). High ranks therefore mean “far from this cohort’s fitted normal,” not “museum says misattributed.”
- **Validation probe ranks 10 / 25** — neither extreme nor below-median. It does not stand out as a triage priority under this recipe.
- **Ambiguous `SK-A-4096` ranks 2** (combined≈2.28, B-driven). Interesting for exploration; **must not** be folded into the success metric to rescue a weak primary result (review / D21).
- **Signal mix:** Top ranks include both A- and B-dominant rows; decomposability works as designed even though the validation gate failed to pass.

---

## Limits (state plainly)

1. **Validation N=1** — Cannot estimate a recovery rate; one weak case is inconclusive for “never works” and insufficient for “works.”
2. **IIIF ~1500 px** (D12/D27) — Weaker than forensic brushstroke scan sets used in classic wavelet auth prior art.
3. **No AUC / no learned fusion** — By design; avoids leakage, also limits power.
4. **Prior-art honesty** — Brushstroke stats and CNN artist models are established; our novelty was contingent on a held-out pass. That contingency **did not fire** (see `results/prior_art_brushstroke_auth.md` claim gate).

---

## Claims allowed vs forbidden

| Allowed | Forbidden |
|---|---|
| Pipeline ran end-to-end; scores are decomposable and reproducible from `scores_v1` | “The method works” / “validation succeeded” / “soft pass” |
| O04=`weak`; probe above median, below p95 | Treating ambiguous rank #2 as confirmation |
| Mid-pack validation rank; B mild, A near-null | Retuning thresholds or fusion after the fact in the narrative |
| Tiny-N and imaging limits | Implying Johnson-parity brushstroke forensics |

---

## Hand-off

- **Phase 5 (T051 / T071):** Expand methodology + limits; keep this verdict.  
- **T050:** Only if human opens scope-tight fixes — do not rewrite O02/O04 to manufacture a pass.  
- **T052:** Sustainability remains a design claim, not empirically demonstrated here.  
- **UX:** Tables-only remains the default (D07/D08); Gradio/API stay deferred.
