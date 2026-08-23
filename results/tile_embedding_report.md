# Tile embedding report — O11 (D36 / `tile_scores_a_v1`)

**Recipe:** `tile_scores_a_v1` · **Decision:** D36 · **Generated:** `2026-08-23T20:19:05.613588+00:00`  
**Pre-registration:** `results/phase10_tile_embedding_design.md` — thresholds, seed, k values, and the confound list were fixed before any 224 px tile was fetched.

Signal A only, and for the first time on pixels the CNN can actually resolve paint in. Each tile is 44.8 mm of canvas served at 224 × 224 px — the backbone's native input size at the locked 0.20 mm/px floor — so **nothing is resized, cropped, or interpolated** on the way in. `embed_v1` by contrast fed the network 0.586–16.058 mm/px after its 256-resize and 224-crop, which is why `z_A`'s 0.427 in O06 was never a fair test.

There is no `combined` here (design §4): Signal A and Signal B now live on different populations, so summing their z-scores would sum different corpora.

## Headline

**O11 outcome: `fail`**

**Confound clause (§7): fires** — see below.

| Quantity | Value |
|---|---|
| AUC (`z_A_tile`, cohort vs Tier-1) | **0.523** |
| bootstrap 95% CI (10,000 resamples, seed 20260823) | [0.318, 0.727] |
| N | 16 cohort vs 36 Tier-1 pupils = 52 |
| chance | 0.500 |
| mean-embedding variant (§4, reported not substituted) | 0.510 |

### The paired comparison (design §5) — did showing the CNN brushwork help?

Both arms are the same backbone, the same layer, the same 52 works, and the same fit rule. The only difference is what a pixel means.

| Arm | what the CNN saw | AUC |
|---|---|---|
| `tile_scores_a_v1` (`z_A_tile`) | 0.20 mm/px, no resize | **0.523** |
| `embed_v1` re-fit on the same works | 0.586–16.058 mm/px after resize + crop | 0.391 |
| **ΔAUC** | | **+0.132**, 95% CI [-0.092, +0.352] |

The re-fitted figure is a **new** number on this population. It does not amend O06, where `z_A` scored 0.427 on 23 cohort vs 67 pupils.

## precision@k (design §6.4)

Pooled ranking of all 52 works by `z_A_tile` descending. **Base rate = 0.692.** Below it means worse than a random shortlist.

| k | precision@k | vs base rate |
|---:|---:|---|
| 5 | 0.200 | -0.492 |
| 10 | 0.500 | -0.192 |
| 20 | 0.700 | +0.008 |

## Cross-signal independence (design §6.8)

Spearman ρ between `z_A_tile` and `z_B_tile` over the 61 works both recipes score: **+0.268**. Weak rank correlation, so the two signals are close to independent evidence — which also means neither is rescued by the other.

## Confound checks (design §7)

Analyzed mm/px is constant at 0.200 by construction. These are the residual acquisition confounds, named in the pre-registration before being computed. **9a fired in O09 at AUC 0.689.**

| # | Quantity | AUC alone | direction-free | Spearman ρ vs `z_A_tile` | N |
|---|---|---:|---:|---:|---|
| 9a | `mm_per_px_native` | 0.705 | 0.705 | -0.422 | 16+36 |
| 9b | `native_px_width` | 0.264 | 0.736 | -0.009 | 16+36 |
| 9c | `area_cm2` | 0.531 | 0.531 | -0.519 | 16+36 |
| 9d | `tiles_written` | *constant* | — | — | 16+36 |

`tiles_written` is the same value for every work in the population, so it cannot separate the classes and no AUC or ρ is defined.

**Fail-closed rule (§7), applied literally:** a quantity whose AUC ≥ 0.523 makes the result *confounded* regardless of tier.

- Breaching quantities: **9a mm_per_px_native, 9c area_cm2**.
- Reported, not substituted for the literal rule: on the direction-free measure `max(AUC, 1−AUC)`, these also match or beat `z_A_tile`: **9a mm_per_px_native, 9b native_px_width, 9c area_cm2**.

**How much weight this carries.** The breach list is not uniform:
- `area_cm2` sits within 0.05 of chance and clears a 0.523 bar by arithmetic, not by doing real work. §8 scopes the clause's *effect* to overriding an otherwise-positive tier.
- `mm_per_px_native` is not near chance: **AUC 0.705** against the pipeline's 0.523, with Spearman ρ -0.422 against the score itself. That one is a real confound, and it is the same column that fired in O09.

## Per-artist breakdown (design §6.6)

| Tier-1 creator | N | median `z_A_tile` | median tile-distance IQR |
|---|---:|---:|---:|
| Nicolaes Maes | 13 | 0.355 | 0.1746 |
| Samuel van Hoogstraten | 1 | 0.174 | 0.1349 |
| Carel Fabritius | 1 | 0.084 | 0.2573 |
| Gerrit Dou | 7 | 0.066 | 0.1599 |
| Ferdinand Bol | 6 | 0.055 | 0.1513 |
| Aert de Gelder | 1 | -0.059 | 0.2175 |
| Willem Drost | 1 | -0.128 | 0.1718 |
| Govert Flinck | 3 | -0.693 | 0.1884 |
| Gerbrand van den Eeckhout | 3 | -1.083 | 0.1170 |

## Tier-2 sensitivity (never pooled)

Cohort (16) vs the 7 eligible Tier-2 works: **AUC 0.438**. Reported with its reduced N per design §6.7.

## Works dropped from the primary analysis

None. Every eligible work retained 10+ tiles (design §4).

### The reading (design §8, stated in advance)

**Showing the CNN actual brushwork did not rescue Signal A.** ΔAUC is +0.132, 95% CI [-0.092, +0.352] — an interval that contains zero. The bootstrap CI on the primary AUC is [0.318, 0.727], which includes chance.

`results/resolution_audit.md` showed the ResNet50 had never seen better than 0.586 mm/px on any work in the corpus — 0 of 108 reached 0.30 — so `z_A`'s 0.427 in O06 was never a fair test of the embedding. It has now had one. At 0.20 mm/px, with no resize and no crop, on the backbone's native input size, it still does not separate firm Rembrandts from their pupils.

**Both halves of the method have now been tested on commensurable pixels and both have failed.** O09 returned `fail` for the eight handcrafted features at this same scale; O11 returns `fail` for the embedding. Signal B moved +0.042 and Signal A moved +0.132 — this is the larger of the two, and it is the one place where normalization visibly did something: the fixed-pixel arm was at 0.391, clearly *below* chance, and commensurable pixels brought it back to 0.523. But a 95% CI of [-0.092, +0.352] contains zero, and an arm that lands on chance is not a method. The scale confound was real, D34 removed it, and what was left underneath is noise in both signals.

That is the honest end of this method as specified. It is not a prompt to try a third variant of it.

## What this does and does not settle

- **O04 (`weak`), O06 (`fail`), and O09 (`fail`) are unchanged** and not amended. All four outcomes stand side by side.
- **`scores_v1` remains the published fixed-pixel baseline.**
- **ImageNet features are not brushwork features** (design §9.3). ResNet50 was trained to name objects. Showing it paint at 0.20 mm/px removes a known defect; it does not make the representation appropriate. This is evidence about *this* backbone at *this* scale, and it is **not** a licence to reopen the deferred DINOv2 / finetuning work.
- **A 44.8 mm tile is outside the training distribution** of a network trained on whole objects (§9.4).
- **The cohort is 16 and size-biased from both ends** — D34 removed the six largest works, this recipe additionally removes the smallest.
- **The floor was not swept** (§9.7).

## Artifacts

- `results/tile_scores/tile_scores_a_v1.csv`
- `results/tile_scores/fit_manifest_a.json`
- `data/embeddings/tile_embed_v1/matrix.pt` — one vector per tile
- `results/qc_tile_scores_a_v1/`
- Pre-registration: `results/phase10_tile_embedding_design.md`
