# Pupil-cohort validation report (O06 / D32)

**Design:** [`results/phase7_pupil_validation_design.md`](phase7_pupil_validation_design.md) · **Scores:** `scores_v1` · **Generated:** `2026-08-20T00:53:45.486187+00:00`

Every threshold, seed, and k below is transcribed from the pre-registration, which was committed before any pupil work was acquired or scored.

## Counts

| Group | N | Role |
|---|---:|---|
| cohort | 23 | fit normals (LOO self-scores); negative class |
| pupil — Tier 1 (documented pupils) | 67 | positive class, primary analysis |
| pupil — Tier 2 (associates) | 16 | sensitivity only, never pooled |

Held-out negatives available to the D04 probe before this phase: **1**. Available to O06 now: **67**.

### Acquisition adherence

The pre-registered roster listed 87 search hits (Tier 1 = 69, Tier 2 = 18). Four were lost to rules written before acquisition, none by choice after seeing a score:

| Work | Creator | Why dropped |
|---|---|---|
| `SK-C-371` | Govert Flinck | already claimed as `excluded/other_artist` by a Phase 1 description probe; design §3.1 forbids re-splitting a claimed work |
| `SK-C-1598` | Jan Lievens | same (title *Portret van Rembrandt*) |
| `SK-A-1627` | Jan Lievens | same |
| `SK-A-4034` | Aert de Gelder | IIIF returned 400; fail-closed to `excluded/missing_image` per the standing rule |

Reading §3.1 literally costs three works. Amending it after seeing which three would have been a post-hoc change to a pre-registered rule, so it was not done.

## O06 outcome

**Result: `fail`**

| Quantity | Value |
|---|---|
| AUC (cohort vs Tier 1, `combined`) | **0.4192** |
| bootstrap 95% CI | [0.2686, 0.5775] |
| CI lower bound `L` vs 0.50 | at or below |
| resamples / seed | 10000 / 20260819 |

Rule (design §5, not retuned): **pass** = `L > 0.50` and AUC ≥ 0.70; **weak** = `L > 0.50` and 0.50 < AUC < 0.70; **fail** = `L ≤ 0.50`.

## Per-signal AUC (design §4.4)

| Signal | AUC |
|---|---|
| `z_A` — ResNet50 cosine-to-centroid | 0.4270 |
| `z_B` — RMS of 8 feature z-scores | 0.5224 |
| `combined` = z_A + z_B | 0.4192 |

## precision@k (design §4.3)

Pooled cohort + Tier 1 ranking by `combined` descending, N=90. Base rate (a random pick being a pupil) = **0.744**.

| k | precision@k | vs base rate |
|---:|---|---|
| 5 | 0.600 | -0.144 |
| 10 | 0.500 | -0.244 |
| 20 | 0.600 | -0.144 |

## Tier 2 sensitivity (design §2 — reported, never pooled)

| Quantity | Value |
|---|---|
| N | 16 |
| AUC (cohort vs Tier 2) | 0.3587 |
| bootstrap 95% CI | [0.1875, 0.5353] |

## Confound checks (design §4.6)

| Check | Value | Reading |
|---|---|---|
| Spearman ρ(mm/px of analyzed image, `combined`) | -0.091 | non-zero ⇒ the score partly tracks digitization scale, not handling |
| Spearman ρ(native IIIF pixel width, `combined`) | 0.067 | non-zero ⇒ the score partly tracks how large a file the museum published |
| AUC on mm/px **alone** (cohort vs Tier 1) | 0.5902 | compare against the `combined` AUC above |

mm/px across the analyzed corpus spans 0.100–3.287 (33× spread), so texture features are not measuring the same physical quantity across works. Design §6.4 records this as unfixed at this phase.

## Per-artist breakdown (design §4.5)

Cohort median `combined` = -0.1168. A pupil group above it scores as more anomalous than the median firm Rembrandt.

| Tier 1 creator | N | median `combined` | vs cohort median |
|---|---:|---|---|
| Barent Fabritius | 5 | -0.0644 | +0.0524 |
| Samuel van Hoogstraten | 2 | -0.3169 | -0.2001 |
| Gerrit Dou | 9 | -0.5605 | -0.4437 |
| Nicolaes Maes | 15 | -0.5610 | -0.4441 |
| Ferdinand Bol | 20 | -0.5863 | -0.4695 |
| Govert Flinck | 7 | -0.5887 | -0.4719 |
| Carel Fabritius | 1 | -0.6615 | -0.5447 |
| Aert de Gelder | 4 | -0.6787 | -0.5619 |
| Gerbrand van den Eeckhout | 3 | -0.7989 | -0.6821 |
| Willem Drost | 1 | -1.0202 | -0.9033 |

## What this does and does not establish

- O06 is a **surrogate** for D04, not a substitute (design §6.1). Pupils catalogued under their own names are not workshop pictures produced under Rembrandt's supervision.
- O04 is unchanged by this report. `SK-A-3934` remains the sole D04 probe and its outcome is still computed from cohort LOO percentiles alone.
- No cohort normal was fitted on any pupil row. The Signal A centroid and the Signal B feature means/stds are bit-identical to the pre-D32 fit manifest.

## Artifacts

| Artifact | Path |
|---|---|
| Pre-registration | `results/phase7_pupil_validation_design.md` |
| Scores | `results/scores/scores_v1.csv` |
| Geometry | `data/cohortscope.sqlite` (`works.mm_per_px_analyzed`) |
| D04 outcome (untouched) | `results/validation_report.md` |
