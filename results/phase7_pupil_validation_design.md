# Phase 7 pre-registration — pupil-cohort validation (D32 / O06)

**Status:** pre-registered. Written and committed **before** any pupil work was acquired, preprocessed, embedded, featurized, or scored.
**Does not modify:** D04, D19–D21, D30, O04. `scores_v1` fit rules and the O04 outcome for `SK-A-3934` are untouched.

---

## 1. Why

`O04` was evaluated against a held-out set of **N=1** (`SK-A-3934`). A single-case tail test cannot distinguish "the method does not separate" from "we drew one unlucky sample." The Rijksmuseum holds no larger set of works labelled *circle/workshop/school of Rembrandt* in oil with images, so the D04 population cannot be grown inside D01.

There is, however, a larger and better-documented population of the **closest available stylistic neighbours**: painters who trained in Rembrandt's studio and are catalogued under their own names. If cohort normals fit on firm Rembrandt cannot separate firm Rembrandt from the people who learned to paint in his workshop, the two-signal design does not discriminate handling at this resolution. If it can, the D04 question becomes worth re-testing with better inputs.

This is a **surrogate** hypothesis, not D04. See §6.

---

## 2. Population (locked)

Acquired with the standing D10 filters (`type=painting`, `material=oil paint`, `imageAvailable=true`) and `creator=<name>`. Counts are live API results at pre-registration time.

### Tier 1 — documented pupils (primary analysis)

| Creator | Studio period | Oils w/ image |
|---|---|---:|
| Gerrit Dou | 1628–1631 (Leiden; first pupil) | 9 |
| Govert Flinck | c. 1633–1636 | 8 |
| Ferdinand Bol | c. 1636–1641 | 20 |
| Carel Fabritius | c. 1641–1643 | 1 |
| Samuel van Hoogstraten | c. 1642–1646 | 2 |
| Nicolaes Maes | c. 1648–1653 | 15 |
| Willem Drost | c. 1650s | 1 |
| Barent Fabritius | c. 1640s | 5 |
| Gerbrand van den Eeckhout | c. 1635–1640 | 3 |
| Aert de Gelder | c. 1661–1663 (last pupil) | 5 |
| **Tier 1 total** | | **69** |

### Tier 2 — associates, not documented pupils (sensitivity only)

| Creator | Relation | Oils w/ image |
|---|---|---:|
| Jan Lievens | shared Leiden studio c. 1626–1631; peer, not pupil | 11 |
| Jacob Backer | Rembrandt circle; pupilage disputed (likely trained under Lambert Jacobsz) | 7 |
| **Tier 2 total** | | **18** |

Tier 2 is reported separately and never pooled into the primary figure.

---

## 3. Split semantics (D32)

New split value `pupil`, added to the `works.split` enum.

- `pupil` rows are **never** fit into cohort normals. Signal A centroid, Signal B feature means/stds, and all LOO logic remain **cohort-only**, exactly as in D30.
- `pupil` rows are scored with full-cohort statistics, identically to `validation` and `ambiguous`.
- `pupil` rows do **not** enter the O04 computation. `SK-A-3934` remains the sole D04 probe and its `pass`/`weak`/`fail` tier is computed from cohort LOO percentiles alone.

### Acquisition exclusion rules (fail-closed, applied before scoring)

A candidate is rejected unless all hold:

1. `object_number` is not already present under any other split — no work may be both cohort and pupil.
2. The resolved creator labels contain **no** occurrence of `rembrandt`. Any Rembrandt-hedged or co-attributed label falls through to the existing D20 rules (`validation` / `ambiguous` / `excluded`) and never becomes `pupil`.
3. Materials do not look non-oil (existing P05 check).
4. A IIIF image resolves and downloads.

Rule 2 is the leakage guard: it makes it impossible for a work carrying a Rembrandt attribution hedge to enter the negative class.

---

## 4. Metrics (locked before scoring)

Computed over `combined = z_A + z_B` as defined by D30. Cohort uses its existing LOO self-scores; pupil uses full-cohort statistics.

1. **AUC** — ROC area for {cohort = negative, pupil = positive}, direction: higher `combined` implies pupil. Null = 0.50.
2. **Bootstrap 95% CI on AUC** — 10,000 stratified resamples, fixed seed 20260819.
3. **precision@k** for k in {5, 10, 20} over the pooled cohort+pupil ranking by `combined` descending; a hit is a `pupil` row.
4. **Per-signal AUC** — the same AUC computed on `z_A` alone and `z_B` alone.
5. **Per-artist breakdown** — N and median `combined` for each Tier 1 creator.
6. **Confound checks** — Spearman rho between `combined` and (a) mm/px of the analyzed image, (b) native IIIF pixel width, over the pooled set; plus AUC for {cohort vs pupil} on mm/px alone. If mm/px alone separates the classes comparably to `combined`, the result is confounded and reported as such regardless of tier.

---

## 5. Decision rule — O06 (locked; will not be retuned after seeing results)

Let `L` be the lower bound of the bootstrap 95% CI on Tier 1 AUC.

| Tier | Condition |
|---|---|
| **pass** | `L > 0.50` **and** AUC >= 0.70 |
| **weak** | `L > 0.50` **and** 0.50 < AUC < 0.70 |
| **fail** | `L <= 0.50` |

If AUC < 0.50 and the CI excludes 0.50 (firm Rembrandt scoring as *more* anomalous than pupils), the outcome is **fail**, reported with an explicit note that the score is tracking an inverse property — most plausibly image acquisition rather than handling.

O06 is reported alongside, not instead of, O04. Neither overrides the other.

---

## 6. Limitations (stated in advance, not after the fact)

1. **Surrogate hypothesis.** D04 asks whether *workshop pictures produced under Rembrandt's supervision* look anomalous against firm Rembrandt. This phase asks whether *pupils working under their own names* do. Bol and Flinck in the early 1640s painted deliberately in Rembrandt's manner; Dou after 1640 and Maes after 1655 did not. The pupil set is stylistically adjacent, not equivalent, and separation here does not establish D04.
2. **Career-divergence confound.** Most pupils developed independent styles. Separation may measure divergence from Rembrandt's mature manner rather than any workshop-discrimination capability. Mitigated only by reporting §4.5 per-artist, which will make divergence visible if present.
3. **Subject-matter confound.** The cohort is dominated by portraits and history pieces; the pupil set includes genre, interior, and still-life subjects. Signal A is a global ImageNet embedding of a 224 px centre crop and is known to order this corpus by genre (top `z_A` in `scores_v1` is the sole landscape). A high Signal-A AUC should therefore be read as evidence of subject discrimination until shown otherwise — which is why §4.4 splits AUC per signal.
4. **Scale confound, unfixed at this phase.** Analyzed images are fixed-width 1500 px, giving a 30x spread in mm/px across works (0.100–3.023). Texture features are therefore not measuring the same physical quantity across the corpus. §4.6 quantifies the exposure; the fix is out of scope for this phase and is deferred.
5. **This phase changes no inputs.** It runs on the existing `preprocess_v1` / `embed_v1` / `features_v1` recipes. Its purpose is to establish a **baseline** on the current instrument, against which later input changes can be measured. A `fail` here is expected to be informative about the instrument, not only about the method.

---

## 7. Artifacts

| Artifact | Path |
|---|---|
| Pupil rows | `data/cohortscope.sqlite` (`split='pupil'`) |
| Scores incl. pupil | `results/scores/scores_v1.csv` |
| O06 outcome | `results/pupil_validation_report.md` |
| This pre-registration | `results/phase7_pupil_validation_design.md` |
