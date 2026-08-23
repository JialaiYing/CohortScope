# Phase 9 pre-registration — statistics over the tile population (D35 / O08 resolved, O09 opened)

**Status:** pre-registered. Written and committed **before any feature value has been computed from any tile.**
**Honest scope note:** unlike Phase 7 and Phase 8, the *data* already exists — `data/tiles/tiles_v1/` was fetched at commit `3f1a95a`. What does not exist is any statistic over it. No tile has been featurized, embedded, z-scored, ranked, or visually inspected while writing this document. The thresholds, seed, aggregation rule, and decision table below are therefore fixed against an unseen result, which is the property pre-registration is for.
**Does not modify:** D04, D19–D21, D30, D32, D33, D34, O04, O06. `scores_v1`, `features_v1`, `embed_v1`, and `preprocess_v1` are untouched and remain published as the baseline.

---

## 1. Why

D34 fixed an instrument defect, not a method. `features_v1` computed texture statistics on images whose scale varied **35×** — 0.100 to 3.467 mm/px (`results/resolution_audit.md` §1) — so `glcm_contrast` at a 1-pixel offset meant 0.1 mm of canvas on one painting and 3.5 mm on another. The eight handcrafted features were never measuring the same physical quantity across the corpus. O06 recorded this as limitation §6.4 and quantified the exposure: **mm/px alone separated cohort from pupils better (AUC 0.590) than the entire two-signal pipeline (0.419)**.

`tiles_v1` removes that defect by construction. Every tile is 30 mm × 30 mm of canvas served at 150 × 150 px, so one pixel is 0.200 mm on the 15 cm `SK-A-3982` and on the 142 cm `SK-A-2507` alike — the full physical span of the eligible corpus, previously a 9.5× scale gradient, now flat. A GLCM offset of 1 px is 0.20 mm everywhere; an LBP radius of 1 px is 0.20 mm everywhere.

This phase asks the narrow question that follows: **was physical normalization the missing ingredient for the handcrafted signal?** The baseline to beat is not the headline 0.419 — that number includes Signal A. It is `z_B` alone, which scored **AUC 0.522** on the fixed-1500 pixels. §5 locks the comparison.

---

## 2. Scope — Signal B only (locked)

**In scope:** the eight `features_v1` columns, recomputed per tile, aggregated to a work-level value, z-scored against cohort normals.

**Out of scope, deliberately:** Signal A. Tiles are 150 × 150 px and the `embed_v1` CNN branch expects a 224 px input, so putting the CNN on tiles requires choosing a resampling factor — reintroducing exactly the arbitrary resize that this line of work exists to eliminate. There is consequently **no `z_A` and no `combined` in this recipe.** The primary statistic is `z_B_tile` alone, and it is compared against `z_B`, never against `combined`.

A `fail` here is evidence about the handcrafted signal at 0.20 mm/px. It says nothing either way about Signal A.

---

## 3. Per-tile measurement (locked; unchanged from `features_v1` on purpose)

The same eight columns, the same `features.extract_one()`, the same constants:

| Feature | Physical meaning at 0.20 mm/px |
|---|---|
| `grad_mag_mean` | mean Sobel gradient magnitude over a 3 px = 0.60 mm neighbourhood |
| `grad_mag_std` | dispersion of the same |
| `grad_orient_entropy` | isotropy of stroke direction |
| `laplacian_var` | second-derivative energy; focus/impasto proxy |
| `lbp_entropy` | uniform LBP, `P=8`, `R=1` px = **0.20 mm** radius |
| `glcm_contrast` | 32 levels, `d=1` px = **0.20 mm**, mean over 0°/45°/90°/135° |
| `lab_chroma_mean` | mean CIE-Lab chroma |
| `hue_circ_std` | circular s.d. of hue |

**Nothing about the feature definitions changes.** That is the experimental control: the only difference between `features_v1` and this recipe is what a pixel means. Changing the features and the pixels together would make the result uninterpretable.

Branch discipline (D26/D29) is preserved: tiles are RGB JPEGs read as RGB — the interpretable-feature branch. No CNN tensor is read here.

---

## 4. Aggregation — tile → work (locked)

For each work and each of the eight features:

- **Primary work-level value = the median across that work's 20 tiles.** Median, not mean, because a geometrically-chosen tile may land on a dark background passage, a frame edge inside the inset, a varnish defect, or a signature. The median tolerates a few such tiles; the mean does not.
- **Reported alongside, never substituted for it:** the mean, and the interquartile range across the 20 tiles. The IQR is the within-work dispersion and is the honest expression of limitation §9.1 — it makes the sampling error visible per work instead of asserting it in prose.

A work with fewer than 20 written tiles (fetch failures, see `results/qc_tiles_v1/failures.csv`) is aggregated over whatever it has, and its tile count is carried into every output row. **A work with fewer than 10 written tiles is dropped from the primary analysis** and the loss is recorded in the report — the D32 precedent of recording the cost of a locked rule rather than amending the rule.

There is no content-based tile filtering, no outlier-tile rejection, and no re-selection. Any such filter would be a tunable that could be turned to move the outcome.

### §4.1 Addendum — a feature that is undefined on a tile (added 2026-08-22)

**Recorded before any aggregate, z-score, AUC, or ranking was computed.** The
per-tile extraction run at commit-time surfaced a case §4 did not anticipate and
this fills the gap; it is not a change to a rule that was already written.

`hue_circ_std` is defined only over pixels with CIE-Lab chroma >= 5.0
(`features.HUE_CHROMA_MIN`). On a whole painting some such pixel always exists.
On a 30 mm x 30 mm patch it need not: **77 of 1,280 tiles (6.0%) across 20 of the
64 eligible works are entirely near-grey**, so their hue statistic has no value.
No other feature is ever undefined.

Two candidate rules, and why one is disqualified:

- **Drop the whole tile.** Rejected. Discarding a tile because of what it depicts
  is content-based tile filtering, which §4 forbids in the sentence directly
  above, and the affected rate differs by class (7 of 17 cohort works vs 11 of 38
  Tier-1 works), so it would silently reshape both arms.
- **Retain the tile; treat that one cell as missing.** Adopted.

**Locked rule.** A tile is never dropped for feature content. Each of the eight
work-level medians (and the mean and IQR reported with it) is taken over the
tiles on which that feature is defined. Every output row carries `n_tiles` and,
where it differs, `n_tiles_hue`, so any reader can see the support behind a
number. If a feature is undefined on **every** tile of a work, that work is
dropped from the primary analysis and the loss is recorded in the report rather
than patched over. No work in `tiles_v1` triggers that clause -- the worst case
retains 10 of 20 tiles -- but the rule is fixed now, before results, so it cannot
be chosen later.

The `< 10 written tiles` drop rule in §4 continues to count *written tiles*, not
per-feature support.

---

## 5. Fit and population (locked)

**Fit rule, structurally identical to D30:** normals are fit on `split == 'cohort'` **only**. Each of the eight work-level medians is z-scored against the cohort mean/std, **leave-one-out** for cohort rows so no work contributes to its own normal. Then

```
z_B_tile = RMS of the 8 cohort z-scores
```

Non-cohort rows use full-cohort statistics. `pupil`, `validation`, and `ambiguous` rows are scored and never fitted.

**Population** — the 64 works eligible at the 0.20 mm/px floor (D34):

| Group | N | Role |
|---|---:|---|
| cohort | **17** | fit + LOO self-scores |
| pupil — Tier 1 | **38** | primary positive class |
| pupil — Tier 2 | 7 | sensitivity only, never pooled |
| validation | 1 | `SK-A-3934`, scored but O04 is **not** recomputed |
| ambiguous | 1 | scored, excluded from every outcome |

Primary analysis is cohort (17) vs Tier 1 (38): **N = 55, base rate 38/55 = 0.691.**

### The paired baseline comparison (locked before seeing either number)

`features_v1`'s Tier-1 `z_B` AUC of 0.522 was computed on 23 cohort + 67 pupils. Comparing it directly to a 17-vs-38 result would confound the pixel change with a population change. Therefore:

> The comparison statistic is **ΔAUC = AUC(`z_B_tile`) − AUC(`z_B` recomputed on the same 55 works)**, where the `features_v1` z-scores are **re-fit from scratch on the 17-work cohort** restricted to the eligible set.

Both arms then differ in exactly one respect: fixed-1500 pixels versus 0.20 mm/px pixels. A bootstrap 95% CI on ΔAUC is computed by resampling **works** (not tiles) with the seed below, recomputing both arms on each resample.

The re-fitted 55-work `features_v1` arm is written to the report as its own number. It is a **new** figure and does not amend O06 or `results/pupil_validation_report.md`.

---

## 6. Metrics (locked before computing)

1. **AUC** — ROC area for {cohort = negative, Tier-1 pupil = positive}, direction: higher `z_B_tile` implies pupil. Null = 0.50.
2. **Bootstrap 95% CI on AUC** — 10,000 stratified resamples over **works**, fixed seed **20260822**.
3. **ΔAUC vs the re-fitted 55-work `features_v1` baseline**, with bootstrap 95% CI (§5).
4. **precision@k** for k in {5, 10, 20} over the pooled 55-work ranking by `z_B_tile` descending. **The base rate to beat is 0.691**, stated here so it cannot be quietly omitted if the result falls below it, as it did in O06.
5. **Per-feature AUC** — the same AUC on each of the eight z-scores alone, to expose whether any single feature carries the signal or whether the RMS is pooling eight noise channels.
6. **Per-artist breakdown** — N, median `z_B_tile`, and median tile-IQR for each Tier-1 creator.
7. **Tier-2 sensitivity** — the same AUC on cohort vs the 7 Tier-2 works, reported with its reduced N and never pooled into the primary figure.
8. **Confound checks** — see §7.

---

## 7. Confound checks — the point of the exercise

mm/px of the analyzed pixels is now **constant at 0.200 by construction**, so the O06 finding cannot recur in its original form: an AUC on analyzed mm/px alone is undefined here, and reporting it as 0.500 would be circular. The residual acquisition confounds are different, and are named in advance:

| # | Quantity | Why it could still leak |
|---|---|---|
| 8a | `mm_per_px_native` | How far the IIIF server had to downsample to reach 0.20. A work already near the floor is served near-natively; one far above it is heavily resampled. Different effective sharpness, same nominal scale. **This is the direct successor to the 0.590 finding.** |
| 8b | native IIIF pixel width | Correlates with digitization campaign and equipment. |
| 8c | painting area in cm² | Physical scale of the *subject* still differs at constant mm/px — a face occupies more canvas on a large canvas. |
| 8d | tiles written (< 20) | Fetch-failure count, in case failures correlate with class. |

For each: **AUC for {cohort vs Tier-1 pupil} on that quantity alone**, plus Spearman rho against work-level `z_B_tile`.

**Fail-closed rule, locked:** if the AUC of any single quantity in 8a–8d **equals or exceeds** the AUC of `z_B_tile`, the result is reported as **confounded** regardless of the primary outcome tier — the O06 precedent. A `pass` that a metadata column can match is not a pass.

---

## 8. Decision rule — O09 (locked; will not be retuned after seeing results)

Let `L` be the lower bound of the bootstrap 95% CI on Tier-1 AUC for `z_B_tile`.

| Tier | Condition |
|---|---|
| **pass** | `L > 0.50` **and** AUC ≥ 0.70 |
| **weak** | `L > 0.50` **and** 0.50 < AUC < 0.70 |
| **fail** | `L ≤ 0.50` |

Thresholds are transcribed unchanged from the O06 rule (`results/phase7_pupil_validation_design.md` §5) so the two outcomes are directly comparable.

Two clauses bind independently of the tier:

- **The confound clause (§7) overrides an otherwise-positive tier.** `pass` or `weak` with a matching-or-better metadata AUC is reported as *confounded*, not as evidence.
- **ΔAUC is reported whatever the tier.** If `z_B_tile` fails *and* ΔAUC ≤ 0, that is the informative result: physical normalization was not the missing ingredient, and the handcrafted-feature line of attack is exhausted at this resolution. That conclusion is to be stated plainly rather than hedged.

If AUC < 0.50 with a CI excluding 0.50 — firm Rembrandt scoring as *more* anomalous than pupils — the outcome is **fail**, with an explicit note that the score is tracking an inverse property.

**O09 does not override O04 or O06, and neither overrides it.** All three are reported side by side.

---

## 9. Limitations (stated in advance, not after the fact)

1. **20 tiles is a sample, not a census.** For the largest eligible works it is under 1% of the painted surface. Every work-level number carries sampling error that grows with painting size. The per-work tile IQR (§4) is reported so this is visible rather than asserted.
2. **The cohort is 17.** Normals fit on 17 works have wide standard errors, and the six excluded firm Rembrandts are systematically the *largest* — so the cohort is not a random subsample of Rembrandt's output but a size-biased one. Any normal fit here describes small-and-medium Rembrandts.
3. **Signal A is absent by design (§2).** This phase cannot exonerate or condemn the embedding.
4. **Tiles are chosen geometrically, not by content.** Some will contain background, floor, dark drapery, or unpainted ground rather than characteristic handling. This is not corrected, on purpose — see §4.
5. **The IIIF server re-encodes each region as JPEG.** Compression artefacts at 0.20 mm/px are not controlled and could carry digitization-campaign signal. §7 8a/8b are the available proxies.
6. **Career-divergence and subject-matter confounds carry over unchanged** from `results/phase7_pupil_validation_design.md` §6.1–§6.3. A separation here may still measure stylistic divergence rather than any workshop-discrimination capability.
7. **The floor is not swept in this phase.** Re-running at 0.15 mm/px is legitimate only as a declared sweep reported in full, never as a substitution for a disappointing 0.20 result (`results/phase8_tiling_design.md` §4.5).
8. **`scores_v1` is not superseded.** It stays published as the fixed-pixel baseline.

---

## 10. Artifacts

| Artifact | Path |
|---|---|
| Per-tile features (one row per tile) | `data/features/tile_features_v1.csv` + `manifest.json` |
| Work-level aggregates, z-scores, `z_B_tile` | `results/tile_scores/tile_scores_v1.csv` |
| Fit manifest (cohort N, LOO, means/stds) | `results/tile_scores/fit_manifest.json` |
| O09 outcome, ΔAUC, confound table | `results/tile_validation_report.md` |
| QC (failures, summary) | `results/qc_tile_features_v1/`, `results/qc_tile_scores_v1/` |
| This pre-registration | `results/phase9_tile_statistics_design.md` |

Recipe IDs frozen by this document: **`tile_features_v1`**, **`tile_scores_v1`**.
