# Tile validation report — O09 (D35 / `tile_scores_v1`)

**Recipe:** `tile_scores_v1` · **Decision:** D35 · **Generated:** `2026-08-23T00:23:37.473780+00:00`  
**Pre-registration:** `results/phase9_tile_statistics_design.md` — thresholds, seed, k values, and the confound list were fixed before any feature value was computed from any tile.

Signal B only. There is no `z_A` and no `combined` on this recipe (design §2): a 150 px tile cannot enter a 224 px CNN without a resample factor, which is the arbitrariness D34 exists to remove. This report says nothing about Signal A.

## Headline

**O09 outcome: `fail`**

**Confound clause (§7): fires** — see below.

| Quantity | Value |
|---|---|
| AUC (`z_B_tile`, cohort vs Tier-1) | **0.469** |
| bootstrap 95% CI (10,000 resamples, seed 20260822) | [0.303, 0.638] |
| N | 17 cohort vs 38 Tier-1 pupils = 55 |
| chance | 0.500 |

### The paired comparison (design §5) — did physical normalization help?

Both arms use the **same 55 works** and the **same 8 features**; the only difference is what a pixel means.

| Arm | pixels | AUC |
|---|---|---|
| `tile_scores_v1` (`z_B_tile`) | 0.20 mm/px everywhere | **0.469** |
| `features_v1` re-fit on the same works | fixed 1500 px wide (0.100–0.947 mm/px) | 0.427 |
| **ΔAUC** | | **+0.042**, 95% CI [-0.141, +0.223] |

The re-fitted fixed-pixel figure is a **new** number computed on this population. It does not amend O06 or `results/pupil_validation_report.md`, where `z_B` scored 0.522 on 23 cohort vs 67 pupils.

## precision@k (design §6.4)

Pooled ranking of all 55 works by `z_B_tile` descending. **Base rate = 0.691** — a random shortlist of any size scores this. A value below it means the ranking is worse than picking at random.

| k | precision@k | vs base rate |
|---:|---:|---|
| 5 | 0.600 | -0.091 |
| 10 | 0.700 | +0.009 |
| 20 | 0.700 | +0.009 |

## Per-feature AUC (design §6.5)

Each of the eight z-scores on its own. This exposes whether one feature carries the signal or whether the RMS is pooling eight noise channels.

| Feature | AUC alone |
|---|---:|
| `grad_orient_entropy` | 0.627 |
| `grad_mag_std` | 0.622 |
| `grad_mag_mean` | 0.607 |
| `lbp_entropy` | 0.598 |
| `glcm_contrast` | 0.568 |
| `laplacian_var` | 0.542 |
| `hue_circ_std` | 0.481 |
| `lab_chroma_mean` | 0.506 |

## Confound checks (design §7)

mm/px of the *analyzed* pixels is constant at 0.200 by construction, so the O06 finding cannot recur in its original form. These are the residual acquisition confounds, named in the pre-registration before being computed.

| # | Quantity | AUC alone | direction-free | Spearman ρ vs `z_B_tile` | N |
|---|---|---:|---:|---:|---|
| 8a | `mm_per_px_native` | 0.689 | 0.689 | -0.137 | 17+38 |
| 8b | `native_px_width` | 0.241 | 0.759 | -0.189 | 17+38 |
| 8c | `area_cm2` | 0.533 | 0.533 | -0.165 | 17+38 |
| 8d | `tiles_written` | *constant* | — | — | 17+38 |

`tiles_written` is the same value for every work in the population, so it cannot separate the classes and no AUC or ρ is defined for it. It is reported as constant rather than as a tie at 0.500.

**Fail-closed rule (§7), applied literally:** a quantity whose AUC ≥ 0.469 (the `z_B_tile` AUC) makes the result *confounded* regardless of tier.

- Breaching quantities: **8a mm_per_px_native, 8c area_cm2** → reported as **confounded**.
- Reported, not substituted for the literal rule: on the direction-free measure `max(AUC, 1−AUC)`, these also match or beat `z_B_tile`: **8a mm_per_px_native, 8b native_px_width, 8c area_cm2**. A quantity that separates in the *opposite* direction still separates.

**How much weight this carries.** `z_B_tile` is at 0.469, *below* chance, so any quantity sitting at or near 0.500 clears the bar by arithmetic rather than by doing real work — `area_cm2` at 0.533 is in that category. The clause is reported as firing because that is what §7 says, and §8 scopes its *effect* to overriding an otherwise-positive tier, of which there is none here. The entry that carries real weight is **8a**: at 0.689 it is not near chance and it beats the pipeline outright.

## Per-artist breakdown (design §6.6)

`tile_iqr_sigma` is the within-work spread across that work's tiles: the median over the eight features of IQR ÷ cohort σ. It is the visible form of limitation §9.1 — 20 tiles is a sample, not a census.

| Tier-1 creator | N | median `z_B_tile` | median tile IQR (σ) |
|---|---:|---:|---:|
| Carel Fabritius | 1 | 1.271 | 0.466 |
| Gerrit Dou | 9 | 1.014 | 0.632 |
| Samuel van Hoogstraten | 1 | 0.837 | 0.857 |
| Aert de Gelder | 1 | 0.719 | 0.828 |
| Nicolaes Maes | 13 | 0.702 | 0.985 |
| Ferdinand Bol | 6 | 0.650 | 0.885 |
| Willem Drost | 1 | 0.587 | 0.642 |
| Gerbrand van den Eeckhout | 3 | 0.504 | 0.738 |
| Govert Flinck | 3 | 0.492 | 1.429 |

## Tier-2 sensitivity (never pooled)

Cohort (17) vs the 7 eligible Tier-2 works (Lievens, Backer — pupilage disputed or absent): **AUC 0.395**. Reported with its reduced N per design §6.7; it is not combined with the Tier-1 figure and does not enter O09.

## Works dropped from the primary analysis

None. Every eligible work retained 10+ tiles and no feature was undefined on all of a work's tiles (design §4, §4.1).

## What this does and does not settle

- **O04 (`weak`, N=1) and O06 (`fail`, N=67) are unchanged.** They are not recomputed here and this report does not amend them. All three outcomes stand side by side.
- **`scores_v1` remains the published fixed-pixel baseline.**
- **Signal A is untested at 0.20 mm/px** (design §2). Nothing here exonerates or condemns the embedding.
- **The cohort is 17 and size-biased** — the six excluded firm Rembrandts are systematically the largest, so these normals describe small-and-medium works.
- **The floor was not swept.** Re-running at another floor is legitimate only as a declared sweep reported in full, never as a substitution (`results/phase8_tiling_design.md` §4.5).

### The informative reading (design §8, stated in advance)

**Physical normalization did not rescue the handcrafted signal.** ΔAUC is +0.042 with a 95% CI of [-0.141, +0.223] — an interval that contains zero, so the change from fixed-pixel to physically-normalized input is indistinguishable from no change at this N. Both arms sit below chance (0.469 and 0.427).

This is the result the pre-registration named in advance as the informative one. The 9.5× scale gradient that O06 flagged as its largest exposure was real, and D34 removed it — the eight features now measure the same physical quantity on every work. Separation was not hiding behind it -- removing it did not produce one. On this evidence the handcrafted-feature line of attack is exhausted at 0.20 mm/px, and that is a finding, not a step on the way to a better number.

**The successor confound is the story.** §7 named `mm_per_px_native` in advance as "the direct successor to the 0.590 finding", and it is: at 0.689 it out-separates the entire pipeline (0.469), exactly as `mm_per_px_analyzed` did in O06. Analyzed resolution is now constant, so what remains is **how far the IIIF server had to downsample to reach 0.20 mm/px** — a property of the digitization, not of the painting. Normalizing the nominal scale did not normalize the effective sharpness behind it.

## Artifacts

- `results/tile_scores/tile_scores_v1.csv` — per-work aggregates, z-scores, both arms
- `results/tile_scores/fit_manifest.json` — cohort means/stds for both arms
- `data/features/tile_features_v1.csv` — one row per tile
- `results/qc_tile_scores_v1/`
- Pre-registration: `results/phase9_tile_statistics_design.md`
