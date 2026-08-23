# Phase 10 pre-registration — Signal A on commensurable pixels (D36 / O10 resolved, O11 opened)

**Status:** pre-registered. Written and committed **before any 224 px tile has been fetched** and before any embedding, distance, or score has been computed from one. The data does not exist yet.
**Does not modify:** D04, D19–D21, D26/D29, D30, D32, D33, D34, D35, O04, O06, O09. `preprocess_v1`, `embed_v1`, `features_v1`, `scores_v1`, `tiles_v1`, `tile_features_v1`, and `tile_scores_v1` are untouched and stay published.

---

## 1. Why

D35 §2 deliberately excluded Signal A and said why: *"Tiles are 150 × 150 px and the `embed_v1` CNN branch expects a 224 px input, so putting the CNN on tiles requires choosing a resampling factor — reintroducing exactly the arbitrary resize that this line of work exists to eliminate."* O09 then returned `fail` for the handcrafted signal at a constant 0.20 mm/px, and recorded that this says nothing either way about the embedding.

That leaves Signal A the only untested half of the method, and it is the half with the worse prior. `results/resolution_audit.md` established that after Branch C's 256-resize and 224-centre-crop, the CNN saw **0.586–16.058 mm/px** — **0 of 108 works reached 0.30 mm/px**. The ResNet50 never had brushwork to compare on any painting in the corpus. That is the arithmetic reason `z_A` scored AUC 0.427 in O06, and it has never been corrected.

This phase corrects it and asks the matching narrow question: **does the embedding separate cohort from Tier-1 pupils when it is finally shown paint at a constant physical scale?**

---

## 2. The resample problem, and why this recipe has no free parameter (O10 resolved)

The obstacle D35 named is real: any tile whose pixel count differs from 224 must be resized before the CNN, and the resize factor would be a tunable that varies by work — the exact defect D34 removed.

It is avoided by **not resizing at all**. Two quantities are already locked elsewhere:

- **0.20 mm/px** — the resolution floor, locked as O07 on 2026-08-19 from the census in `results/resolution_audit.md` §4. `results/phase8_tiling_design.md` §4.5 forbids moving it to improve a downstream number.
- **224 px** — the ResNet50 input size, fixed by `config.BACKBONE` (D29). Not ours to choose.

Their product is the tile size, and it is **determined, not selected**:

```
224 px x 0.20 mm/px = 44.8 mm
```

A 44.8 mm × 44.8 mm region of canvas served by IIIF at 224 × 224 px arrives at exactly 0.20 mm/px and at exactly the CNN's native input size. **There is no resize, no crop, and no resample factor anywhere in the path.** Branch C's 256-resize and 224-centre-crop are both skipped; the tile *is* the input.

This is the same derivation that produced `TILE_SIZE_PX = 150` in D34, run in the other direction. Changing 44.8 requires changing the floor or the backbone, each of which is a locked decision with its own approval path.

### What is kept from Branch C, and what is not

| Step | `embed_v1` (Branch C) | this recipe | why |
|---|---|---|---|
| resize short edge to 256 | yes | **no** | would change mm/px per work |
| centre-crop 224 | yes | **no** | tile is already 224 |
| ImageNet mean/std normalization | yes | **yes** | part of the pretrained model's contract, not a geometry choice |
| ResNet50 `IMAGENET1K_V2`, penultimate 2048-d pool | yes | **yes** | identical backbone and layer; only the input geometry differs |

Backbone, weights, and layer are **unchanged on purpose** — the same experimental control D35 §3 used for the features. The only difference between `embed_v1` and this recipe is what a pixel means.

---

## 3. Acquisition — `cnn_tiles_v1` (locked)

A second tile fetch, parallel to `tiles_v1` rather than replacing it. Identical rules, one derived constant changed:

| Parameter | Value | Source |
|---|---|---|
| Resolution floor | **0.20 mm/px** | O07, unchanged |
| Tile size | **44.8 mm × 44.8 mm** | derived: 224 × 0.20 |
| Tile pixels | **224 × 224** | `config.BACKBONE` input size |
| Edge inset | **5%** | D34, unchanged |
| Tiles per work | **20**, non-overlapping | D34, unchanged |
| Selection | evenly spaced indices over the row-major inset grid, **no RNG** | D34 §2, unchanged |
| Recipe ID | `cnn_tiles_v1` | frozen by this document |

Eligibility is the D34 rule with the larger tile substituted, and stays **derived, never stored on `works`**.

### Expected population (computed from geometry already in the DB; no tile fetched)

| Group | `tiles_v1` (150 px) | `cnn_tiles_v1` (224 px) |
|---|---:|---:|
| cohort | 17 | **16** |
| pupil — Tier 1 | 38 | **36** |
| pupil — Tier 2 | 7 | 7 |
| validation | 1 | 1 |
| ambiguous | 1 | 1 |
| **Total** | **64** | **61** |

**Three works are lost, and all three are lost for the same reason:** a larger tile means fewer of them fit inside the inset, so the physically smallest works can no longer supply 20.

| Object | Split | Size | Why |
|---|---|---|---|
| `SK-A-3982` | cohort | 15.0 × 19.0 cm | 20 tiles of 44.8 mm do not fit |
| `SK-A-88` | pupil (Tier 1) | 19.0 × 25.2 cm | same |
| `SK-A-89` | pupil (Tier 1) | 17.2 × 18.8 cm | same |

Note the direction: D34's exclusions were the physically **largest** works, these are the **smallest**. The two recipes are size-biased in opposite directions, and neither population is a random subsample of anything. This is recorded now rather than discovered later.

---

## 4. Per-tile measurement and aggregation (locked)

Each 224 × 224 tile is ImageNet-normalized and passed through ResNet50 to a 2048-d penultimate vector, L2-normalized — identical to `embed_v1` in every respect except that nothing was resized to get there.

**Work-level Signal A, primary rule:**

1. Build the **cohort tile centroid**: the L2-normalized mean of every tile vector belonging to a `split == 'cohort'` work. Leave-one-out for cohort rows — a work's own tiles never enter the centroid it is scored against.
2. For each tile of a work, `d = 1 − cos(tile vector, centroid)`.
3. **The work's `d_A_tile` is the median of its 20 tile distances.** Median, not mean, for the reason given in D35 §4: a geometrically-chosen tile may land on background, a frame edge inside the inset, or a varnish defect.
4. `z_A_tile` = `d_A_tile` z-scored against the cohort distribution of `d_A_tile`, leave-one-out for cohort rows.

**Reported alongside, never substituted for it:** the *mean-embedding* variant — average a work's 20 tile vectors first, L2-normalize, then take one cosine distance. It is the natural alternative and it will differ; both are printed so neither can be selected after the fact.

The **IQR of the 20 tile distances** is reported per work, as in D35 §4, so the within-work sampling spread is visible rather than asserted.

Design §4.1 of Phase 9 has no analogue here: an embedding is defined on every tile, including a uniformly grey one. No tile is dropped for content. A work with fewer than 10 written tiles is dropped from the primary analysis and the loss recorded.

**There is no `combined` in this recipe.** Signal A and Signal B now live on different populations (61 vs 64 works) with different tile sizes, so summing their z-scores would be summing measurements of different corpora. Combining them requires its own decision and is deliberately not taken here.

---

## 5. Fit, population, and the paired comparison (locked)

Normals are fit on `split == 'cohort'` **only** — 16 works — leave-one-out for cohort rows, structurally as D30 and D35. `pupil`, `validation`, and `ambiguous` are scored and never fitted.

Primary analysis is cohort (16) vs Tier 1 (36): **N = 52, base rate 36/52 = 0.692.**

### The paired baseline (locked before seeing either number)

As in D35 §5, the comparison must not confound the pixel change with a population change:

> **ΔAUC = AUC(`z_A_tile`) − AUC(`z_A` recomputed on the same 52 works)**, where the `embed_v1` cosine distances are **re-fit from scratch** on the 16-work cohort restricted to the eligible set.

Both arms are then the same backbone, the same layer, the same works, and the same fit rule. The only difference is that one saw 0.586–16.058 mm/px and the other saw 0.200 mm/px. A paired bootstrap 95% CI on ΔAUC resamples **works** (not tiles), using the same resampled indices for both arms, seed below.

The re-fitted 52-work `embed_v1` figure is a **new** number. It does not amend O06 or `results/pupil_validation_report.md`, where `z_A` scored 0.427 on 23 cohort vs 67 pupils.

---

## 6. Metrics (locked before computing)

1. **AUC** — {cohort = negative, Tier-1 pupil = positive}, direction: higher `z_A_tile` implies pupil. Null = 0.50.
2. **Bootstrap 95% CI** — 10,000 stratified resamples over works, fixed seed **20260823**.
3. **ΔAUC vs the re-fitted 52-work `embed_v1` arm**, with paired bootstrap 95% CI (§5).
4. **precision@k** for k in {5, 10, 20} over the pooled 52-work ranking. **The base rate to beat is 0.692**, stated here so it cannot be omitted if the result falls below it.
5. **Mean-embedding variant AUC** (§4), reported beside the median rule, not in place of it.
6. **Per-artist breakdown** — N, median `z_A_tile`, median tile-distance IQR per Tier-1 creator.
7. **Tier-2 sensitivity** — cohort vs the 7 Tier-2 works, reported with its N, never pooled.
8. **Cross-signal check** — Spearman rho between `z_A_tile` and `z_B_tile` on the 61 works both recipes score. If the two signals are strongly rank-correlated they are not independent evidence, whatever either one scores.
9. **Confound checks** — §7.

---

## 7. Confound checks

Analyzed mm/px is constant at 0.200 by construction, so as in D35 §7 an AUC on it is undefined and reporting it as 0.500 would be circular. The residual confounds are the same successors, named in advance, and **8a is the one that fired in O09 at AUC 0.689**:

| # | Quantity | Why it could leak |
|---|---|---|
| 9a | `mm_per_px_native` | How far the IIIF server had to downsample to reach 0.20 — effective sharpness at constant nominal scale. **Fired in O09.** |
| 9b | native IIIF pixel width | Digitization campaign and equipment. |
| 9c | painting area in cm² | Subject scale still varies at constant mm/px. |
| 9d | tiles written (< 20) | Fetch-failure count, in case failures correlate with class. |

For each: **AUC for {cohort vs Tier-1} on that quantity alone**, plus Spearman rho against `z_A_tile`. A quantity that is constant across the population is reported as constant, not as a tie at 0.500.

**Fail-closed rule, locked:** if the AUC of any single quantity in 9a–9d **equals or exceeds** the AUC of `z_A_tile`, the result is reported as **confounded** regardless of the outcome tier. As in D35 §8 the clause exists to override an otherwise-positive tier; where the primary AUC is at or below chance the clause fires without having anything to override, and the report must say so plainly instead of presenting a vacuous breach as a finding.

---

## 8. Decision rule — O11 (locked; will not be retuned after seeing results)

Let `L` be the lower bound of the bootstrap 95% CI on Tier-1 AUC for `z_A_tile`.

| Tier | Condition |
|---|---|
| **pass** | `L > 0.50` **and** AUC ≥ 0.70 |
| **weak** | `L > 0.50` **and** 0.50 < AUC < 0.70 |
| **fail** | `L ≤ 0.50` |

Thresholds transcribed unchanged from O06 §5 and O09 §8, so all three outcomes are directly comparable.

- **ΔAUC is reported whatever the tier.** If `z_A_tile` fails *and* ΔAUC ≤ 0, then showing the CNN actual brushwork at a constant physical scale did not help, and — with O09 already `fail` for the handcrafted signal — **both halves of the method have been tested on commensurable pixels and both have failed.** That conclusion is to be stated plainly, not hedged, and it is the honest end of the current method rather than a prompt to try a third variant.
- If AUC < 0.50 with a CI excluding 0.50, the outcome is **fail** with an explicit note that the score tracks an inverse property.
- **O11 does not override O04, O06, or O09, and none overrides it.** All four are reported side by side.

---

## 9. Limitations (stated in advance)

1. **20 tiles is a sample, not a census** — under 1% of the painted surface on the largest works. The per-work distance IQR (§4) makes this visible.
2. **The cohort is 16**, and it is size-biased toward *medium* works from both ends: D34 removed the six largest, this recipe additionally removes the smallest. Normals fit here describe neither extreme.
3. **ImageNet features are not brushwork features.** ResNet50 was trained to name objects, not to characterise handling. Showing it paint at 0.20 mm/px removes a known defect; it does not make the representation appropriate. A `fail` here is evidence about *this* backbone at *this* scale, and D-level deferral of DINOv2/finetuning is unchanged — this is not a licence to reopen it.
4. **A 44.8 mm tile is a small field of view for a network trained on whole objects.** The receptive field now covers paint texture rather than a face or a hand, which is the point, but it also means the model is being used outside its training distribution.
5. **The IIIF server re-encodes each region as JPEG**; compression artefacts at 0.20 mm/px are uncontrolled. 9a/9b are the available proxies.
6. **Career-divergence and subject-matter confounds carry over** unchanged from `results/phase7_pupil_validation_design.md` §6.1–§6.3.
7. **The floor is not swept in this phase.** A sweep is legitimate only as a declared, fully reported experiment (planned separately), never as a substitution for a disappointing 0.20 result.
8. **Signal A and Signal B are not combined** (§4) and `scores_v1` is not superseded.

---

## 10. Artifacts

| Artifact | Path |
|---|---|
| 224 px tile cache (gitignored; regenerable) | `data/tiles/cnn_tiles_v1/{object_number}/{row}_{col}.jpg` |
| Tile manifest incl. every below-floor verdict | `data/tiles/cnn_tiles_v1/manifest.json` |
| Per-tile embeddings | `data/embeddings/tile_embed_v1/` + `manifest.json` |
| Work-level distances, z-scores, both arms | `results/tile_scores/tile_scores_a_v1.csv` |
| Fit manifest | `results/tile_scores/fit_manifest_a.json` |
| O11 outcome, ΔAUC, confound table | `results/tile_embedding_report.md` |
| QC | `results/qc_cnn_tiles_v1/`, `results/qc_tile_embed_v1/` |
| This pre-registration | `results/phase10_tile_embedding_design.md` |

Recipe IDs frozen by this document: **`cnn_tiles_v1`**, **`tile_embed_v1`**, **`tile_scores_a_v1`**.
