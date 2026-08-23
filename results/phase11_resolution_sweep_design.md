# Phase 11 pre-registration — the resolution-floor sweep (D37 / O12 resolved, O13 opened)

**Status:** pre-registered. Written and committed **before any sweep tile has been fetched at any floor other than 0.20**, and before any sweep AUC has been computed. The eligibility census in §3 is arithmetic over geometry already in the database (D33) and involved no image and no score.
**Does not modify:** D04, D19–D21, D26/D29, D30, D32–D36, O04, O06, O07, O09, O11. Every published recipe and report stays exactly as it is.

---

## 1. Why, and the trap this phase has to avoid

O09 (`fail`, Signal B, AUC 0.469) and O11 (`fail`, Signal A, AUC 0.523) both tested a single resolution: the 0.20 mm/px floor locked as O07. Between them they establish that neither half of the method separates firm Rembrandts from their pupils **at that one scale**. They do not establish that 0.20 was the right scale to look at.

That is the open question, and it is the last one worth asking of this method: **is there a physical resolution at which the signal exists, and does the corpus contain imagery good enough to reach it?**

The trap is obvious and it has a name. Sweeping a parameter and reporting the best value it produces is the garden of forking paths — with 4 floors × 2 signals there are 8 chances to find an AUC that looks good by luck alone, and at N ≈ 40 the sampling noise is wide enough to supply one. `results/phase8_tiling_design.md` §4.5 already forbids moving the floor to improve a downstream number. **This document does not relax that rule; it is the declared, fully-reported experiment that §4.5 named as the only legitimate way to vary the floor.** §6 fixes the multiplicity correction before any sweep point exists, and §7 states in advance that a good number at another floor does not retroactively amend O07, O09, or O11.

---

## 2. What is swept, and what is held fixed (O12 resolved)

Each signal keeps its **pixel count fixed** and lets the tile's physical size follow the floor:

| | Signal B (`tile_features_v1` family) | Signal A (`tile_embed_v1` family) |
|---|---|---|
| tile pixels | **150 × 150**, every floor | **224 × 224**, every floor |
| tile canvas | `150 × floor` mm | `224 × floor` mm |
| what varies with the floor | the physical scale the operators probe | the physical scale the CNN sees |
| what does not vary | pixel count, so GLCM/LBP histogram stability is constant | pixel count, so **no resize or crop at any floor** (D36 §2) |

This is the only parameterization that keeps both signals honest across the sweep:

- Holding the **canvas size** fixed instead and varying pixels would give a 600 px tile at 0.05 and a 75 px tile at 0.40. Signal B's texture histograms would be computed on 64× more samples at one end than the other, and Signal A would need a per-floor resize — reintroducing exactly the arbitrariness D34 and D36 exist to remove.
- Holding the **pixel count** fixed makes every floor's tile the same statistical object. Only the millimetres each pixel covers changes, which is precisely the variable under study.

A consequence worth stating plainly: **`tiles_v1` is the 0.20 point of the Signal-B curve and `cnn_tiles_v1` is the 0.20 point of the Signal-A curve.** They are not re-derived, they are reused, and the sweep's 0.20 tiles must be byte-identical to the already-published ones. That is a verification the run will perform, not an assumption.

### Swept floors (locked)

**0.15, 0.20, 0.25, 0.30 mm/px** — four points spanning 2×, bracketing the locked floor on both sides.

The range is not a preference. §3 shows it is the widest contiguous range over which a **fixed population** survives for both signals, and a fixed population is what makes the curve interpretable at all.

---

## 3. Population — fixed across floors, and why the wider sweep is impossible

Eligibility is not monotonic in the floor. A coarser floor admits more works by the mm/px test but excludes more by the "20 tiles must fit inside the inset" test, because the tile grows with the floor. So the eligible sets at different floors are **not nested**, and the population changes shape as the floor moves.

That matters because a curve computed on a shifting population confounds the thing being studied with the sample. A rise in AUC between two floors could be resolution, or it could be that eleven different paintings entered the sample. **The sweep therefore runs on the intersection: the works eligible at every swept floor.**

Census over the full candidate range, computed from D33 geometry with no image fetched:

| Floor | Signal B eligible | Signal A eligible |
|---:|---:|---:|
| 0.05 | 9 | 9 |
| 0.10 | 24 | 24 |
| **0.15** | **46** | **44** |
| **0.20** | **64** | **61** |
| **0.25** | **76** | **72** |
| **0.30** | **82** | **76** |
| 0.40 | 90 | 78 |

Intersection size by candidate range (cohort + Tier-1 + Tier-2):

| Range | Signal B | Signal A |
|---|---|---|
| 0.05–0.40 (7 pts) | 6 works | **0 works** |
| 0.10–0.40 (6 pts) | 18 | 6 |
| 0.15–0.40 (5 pts) | 40 | 28 |
| **0.15–0.30 (4 pts)** | **43** | **37** |
| 0.20–0.30 (3 pts) | 61 | 55 |

**The full-range sweep is arithmetically impossible, not merely underpowered:** zero works are eligible at every floor from 0.05 to 0.40 for Signal A. Only nine works in the entire corpus have published imagery finer than 0.05 mm/px. That is itself a finding about the corpus and is reported as one.

0.15–0.30 is chosen as the widest range where both signals retain a usable fixed population. Adding 0.40 would cost Signal A nine works to buy one more point.

### Locked sweep populations

| | Signal B | Signal A |
|---|---:|---:|
| cohort | **16** | **15** |
| pupil — Tier 1 | **24** | **20** |
| pupil — Tier 2 | 1 | 1 |
| validation | 1 | 1 |
| ambiguous | 1 | 0 |
| **total** | **43** | **37** |
| **primary comparison** | **16 vs 24 = 40** | **15 vs 20 = 35** |
| **base rate** | **0.600** | **0.571** |

Tier-2 falls to a single work in both sweeps. **Tier-2 sensitivity is therefore not computed in this phase** — one work cannot support an AUC — and its absence is recorded here rather than being quietly omitted from the report.

These populations differ from O09 (55) and O11 (52), so **every number in this phase is a new number on a new population.** No sweep figure amends, replaces, or is directly comparable to an O09 or O11 figure, including at the 0.20 point.

---

## 4. What is computed at each floor (locked; unchanged from D35 and D36)

Nothing about either signal's definition changes. That is the experimental control — the only thing varying across the sweep is millimetres per pixel.

**Signal B**, per floor: the eight `features_v1` columns via `features.extract_one()` on each 150 px tile; work-level value = **median over the work's 20 tiles** per feature (design D35 §4, including the §4.1 undefined-cell rule); z-scored against a **cohort-only, leave-one-out** fit; `z_B_tile` = RMS of the 8 z-scores.

**Signal A**, per floor: each 224 px tile embedded by the unchanged ResNet50 (`embed.build_model`, ImageNet normalization only, **no resize, no crop**); per-tile cosine distance to a **cohort-only, leave-one-out tile centroid**; work-level `d_A_tile` = **median** over the work's 20 tile distances; `z_A_tile` = LOO z-score of that.

Tile selection at every floor is the D34 rule — 5% edge inset, 20 non-overlapping tiles, evenly spaced indices over the row-major grid, **no RNG**.

**The two signals are not combined at any floor** (D35 §2, D36 §4). They run on different populations and are reported as two separate curves.

---

## 5. Metrics (locked before computing)

Per signal, per floor:

1. **AUC** — {cohort = negative, Tier-1 pupil = positive}, higher score implies pupil. Null = 0.50.
2. **Bootstrap 95% CI** — 10,000 stratified resamples over **works**, fixed seed **20260824**. Reported for every point; this is the descriptive curve.
3. **precision@k** for k ∈ {5, 10} — k = 20 is dropped because it is half the Signal-B population and would be near-tautological at N = 40/35. Base rates (0.600 / 0.571) are printed beside every value.
4. **Per-feature AUC** (Signal B only), so a floor-dependent single-feature effect cannot hide inside the RMS.
5. **`mm_per_px_native` confound AUC at every floor** — it out-scored the entire pipeline at 0.20 in both O09 (0.689) and O11 (0.705). The sweep population is fixed, so this quantity is **constant across floors by construction**; it is computed once per signal and reported at the head of each curve. If it again exceeds every swept AUC, the sweep has found nothing the digitization does not already explain, and the report says exactly that.
6. **Trend** — Spearman ρ between floor and AUC across the four points. With n = 4 this is **descriptive only**; no p-value is computed from it and none may be quoted.

---

## 6. The multiplicity correction (locked before any sweep point exists)

The sweep performs **8 tests**: 4 floors × 2 signals. Reading the best of 8 against an uncorrected 95% interval inflates the false-positive rate to roughly 1 − 0.95⁸ ≈ 34%.

> **Confirmatory rule.** A floor counts as showing separation only if its bootstrap **99.375% CI** lower bound exceeds 0.50 — that is 1 − 0.05/8, Bonferroni across all 8 tests. Percentiles 0.3125 and 99.6875 of the same 10,000 resamples, same seed.

Both intervals are reported for every point: the 95% one as the descriptive curve, the 99.375% one as the only interval that may support a claim. The corrected interval is computed at **every** point, not only at the winner, so the correction cannot be applied selectively after the fact.

10,000 resamples resolve the 0.3125th percentile to roughly ±30 order statistics. That is coarse, and it is why the corrected bound is used only for a directional pass/fail and never quoted as a precise number.

---

## 7. Decision rule — O13 (locked; will not be retuned after seeing the curve)

Let `Lc` be the 99.375% CI lower bound at a given floor and signal.

| Tier | Condition |
|---|---|
| **pass** | some swept floor has `Lc > 0.50` **and** AUC ≥ 0.70 at that floor |
| **weak** | some swept floor has `Lc > 0.50` **and** 0.50 < AUC < 0.70 |
| **fail** | no swept floor has `Lc > 0.50` |

The 0.70 bar is transcribed unchanged from O06 §5, O09 §8, and O11 §8 so all outcomes remain comparable.

Three clauses bind independently:

- **A `pass` or `weak` does not amend O07, O09, or O11 and does not move the locked floor.** It would be grounds to open a new pre-registered phase at that floor with a fresh population, nothing more. The 0.20 floor stays locked. Retro-fitting a published outcome to a better sweep point is the exact failure this project exists to avoid.
- **The confound clause carries over.** If `mm_per_px_native` (§5.5) matches or beats the best swept AUC, the result is reported as **confounded** whatever the tier — the O09/O11 precedent.
- **A flat curve is the expected result and is informative.** If AUC is statistically indistinguishable from chance at all four floors, then the answer to "was 0.20 simply the wrong scale?" is **no** — the method does not work at any resolution this corpus can support, over a 2× range bracketing the locked floor. Combined with O09 and O11 that closes the method. **This is to be stated plainly and not softened into a call for more resolution**, because §3 already shows the corpus cannot supply more: nine works reach 0.05 mm/px and zero support a full-range sweep.

---

## 8. Limitations (stated in advance)

1. **The swept range is 2×, not the 8× the candidate list suggested.** §3 shows why. A signal that only appears below 0.15 mm/px would be invisible to this experiment, and the corpus cannot test for it — that is a limit of the available imagery, not a result about paint.
2. **N = 40 and 35**, smaller than O09 (55) and O11 (52). Confidence intervals will be correspondingly wider, and the Bonferroni correction widens them further. This experiment is well powered to detect a *large* resolution effect and poorly powered to detect a small one; it will not be described as showing "no effect", only as failing to find one at this N.
3. **The cohort is 16 and 15.** Normals fit on that many works have wide standard errors, and the cohort remains size-biased — D34 removed the largest works and the tile-count rule removes the smallest.
4. **Tier-2 sensitivity is not computed** (§3): one work per sweep.
5. **20 tiles per work at every floor** — the sampled fraction of the surface shrinks as the tile grows, so the coarsest floor samples the most canvas per tile but the same 20 patches. Per-work IQR is reported as in D35 §4.
6. **The IIIF server re-encodes every region as JPEG at every floor**, and the degree of downsampling it performs differs per work and per floor. §5.5 is the available proxy.
7. **Career-divergence and subject-matter confounds carry over** unchanged from `results/phase7_pupil_validation_design.md` §6.1–§6.3.
8. **ImageNet features are not brushwork features** (D36 §9.3). A flat Signal-A curve is evidence about this backbone across this range, and is **not** a licence to reopen the deferred DINOv2 / finetuning work.

---

## 9. Artifacts

| Artifact | Path |
|---|---|
| Sweep tile caches (gitignored; regenerable) | `data/tiles/sweep_{signal}_{floor}/` |
| Per-floor per-work scores, both signals | `results/sweep/sweep_v1.csv` |
| Per-floor AUC, both CIs, precision@k, confound | `results/sweep/sweep_curve.csv` |
| Fit manifest (per floor, per signal) | `results/sweep/fit_manifest.json` |
| O13 outcome, the curve, the correction | `results/resolution_sweep_report.md` |
| QC | `results/qc_sweep_v1/` |
| This pre-registration | `results/phase11_resolution_sweep_design.md` |

Recipe ID frozen by this document: **`sweep_v1`**.
