# Resolution sweep report - O13 (D37 / `sweep_v1`)

**Recipe:** `sweep_v1` - **Decision:** D37 - **Generated:** `2026-08-23T22:36:50.526785+00:00`  
**Pre-registration:** `results/phase11_resolution_sweep_design.md` - the swept floors, the fixed population, the bootstrap seed, the Bonferroni correction, and the decision table were fixed before any non-0.20 tile was fetched.

O09 and O11 tested one resolution: the 0.20 mm/px floor locked as O07. This phase asks the question they left open - **is there a resolution at which the signal exists?** - over the widest range the corpus can support with a population held fixed across floors.

## Headline

**O13 outcome: `fail`**

**Confound clause: fires.**

Best point of the eight: **Signal A at 0.20 mm/px, AUC 0.530** (95% [0.310, 0.757], corrected [0.230, 0.838]).

### Why the corrected interval is the one that counts

The sweep runs **8 tests** (4 floors x 2 signals). Reading the best of eight against an uncorrected 95% interval inflates the false-positive rate to about 34%. Design §6 therefore locked a Bonferroni correction **before any point existed**: a floor shows separation only if its **99.3750% CI** excludes 0.50. Both intervals are printed at every point so the correction cannot be applied selectively.

## The curves

### Signal B - eight handcrafted features (150 px tiles, N = 16 vs 24, base rate 0.600)

| floor mm/px | tile canvas | AUC | 95% CI | corrected CI | p@5 | p@10 |
|---:|---:|---:|---|---|---:|---:|
| 0.15 | 22.5 mm | **0.466** | [0.286, 0.651] | [0.224, 0.716] | 0.600 | 0.600 |
| 0.20 | 30 mm | **0.474** | [0.292, 0.656] | [0.224, 0.724] | 0.600 | 0.700 |
| 0.25 | 37.5 mm | **0.484** | [0.286, 0.677] | [0.224, 0.750] | 0.400 | 0.500 |
| 0.30 | 45 mm | **0.495** | [0.310, 0.682] | [0.242, 0.757] | 0.600 | 0.500 |

AUC spans 0.029 across a 2x change in resolution; Spearman rho between floor and AUC = +1.000 (n = 4 points, **descriptive only** - design §5.6 forbids quoting a p-value from it).

Best single feature at each floor (design §5.4), so a floor-dependent single-feature effect cannot hide inside the RMS:

| floor | best feature | its AUC |
|---:|---|---:|
| 0.15 | `grad_mag_std` | 0.615 |
| 0.20 | `grad_mag_std` | 0.607 |
| 0.25 | `lbp_entropy` | 0.609 |
| 0.30 | `grad_orient_entropy` | 0.612 |


### Signal A - ResNet50 embedding (224 px tiles, N = 15 vs 20, base rate 0.571)

| floor mm/px | tile canvas | AUC | 95% CI | corrected CI | p@5 | p@10 |
|---:|---:|---:|---|---|---:|---:|
| 0.15 | 33.6 mm | **0.453** | [0.250, 0.667] | [0.170, 0.760] | 0.200 | 0.500 |
| 0.20 **<-**  | 44.8 mm | **0.530** | [0.310, 0.757] | [0.230, 0.838] | 0.200 | 0.500 |
| 0.25 | 56 mm | **0.503** | [0.283, 0.720] | [0.197, 0.810] | 0.400 | 0.400 |
| 0.30 | 67.2 mm | **0.473** | [0.263, 0.690] | [0.180, 0.773] | 0.200 | 0.500 |

AUC spans 0.077 across a 2x change in resolution; Spearman rho between floor and AUC = +0.200 (n = 4 points, **descriptive only** - design §5.6 forbids quoting a p-value from it).

## The confound, at every floor (design §5.5)

The sweep population is fixed, so `mm_per_px_native` - how far the IIIF server had to downsample to reach the floor - is **constant across floors by construction** and is computed once per signal.

| Signal | `mm_per_px_native` AUC | direction-free | best swept AUC | N |
|---|---:|---:|---:|---|
| B | **0.557** | 0.557 | 0.495 (at 0.30) | 16+24 |
| A | **0.617** | 0.617 | 0.530 (at 0.20) | 15+20 |

**The clause fires.** A single metadata column matches or beats the best of eight swept points. In O06 it was `mm_per_px_analyzed` at 0.590, in O09 `mm_per_px_native` at 0.689, in O11 at 0.705 - and again here. Whatever the sweep found, the digitization already explained it.

## What this settles

**No floor separates the classes.** All eight corrected intervals contain 0.50 - and so do all eight *uncorrected* 95% intervals, so the multiplicity correction never had to do any work: not a single point clears even the unadjusted bar. The answer to *"was 0.20 simply the wrong scale?"* is **no**: over a 2x range bracketing the locked floor, on a population held fixed so that only millimetres-per-pixel varies, neither signal separates firm Rembrandts from their pupils at any resolution tested.

The curves are flat, not noisy-but-trending: Signal B moves 0.466-0.495 across the range and Signal A 0.453-0.530. Every point sits within 0.047 of chance.

Design §7 named this outcome in advance and required that it not be softened into a call for more resolution. It is not one, and §3 explains why it cannot be: **nine works in the entire corpus have imagery finer than 0.05 mm/px, and zero works support a full 0.05-0.40 sweep for Signal A.** The imagery to test a finer hypothesis does not exist in this collection.

Together with O09 and O11 this closes the method as specified:

| Outcome | What was tested | Result |
|---|---|---|
| O04 | SK-A-3934 vs cohort, N=1 | `weak` |
| O06 | both signals, fixed-1500 px, N=67 | `fail` (AUC 0.419) |
| O09 | Signal B at 0.20 mm/px, N=55 | `fail` (AUC 0.469) |
| O11 | Signal A at 0.20 mm/px, N=52 | `fail` (AUC 0.523) |
| **O13** | **both signals, 0.15-0.30 mm/px, fixed population** | **`fail`** |

## Limits (stated in the pre-registration, not after)

- **The swept range is 2x, not the 8x the candidate list suggested.** Eligibility is not monotonic in the floor - a coarser floor admits more works by the mm/px test while excluding more by the 20-tiles-must-fit test - so the eligible sets are not nested. The 0.05-0.40 intersection is 6 works for Signal B and **zero** for Signal A.
- **N = 16+24 and 15+20**, smaller than O09 (55) and O11 (52), and the Bonferroni correction widens the intervals further. This experiment is well powered for a large resolution effect and poorly powered for a small one; it fails to find one, which is not the same as showing there is none.
- **Tier-2 sensitivity is not computed**: one work per sweep (design §3).
- **These are new numbers on a new population.** No sweep figure amends or is directly comparable to an O09 or O11 figure, including at 0.20.
- **ImageNet features are not brushwork features.** A flat Signal-A curve is evidence about this backbone across this range and is **not** a licence to reopen the deferred DINOv2 / finetuning work.

## Artifacts

- `results/sweep/sweep_curve.csv` - one row per swept point
- `results/sweep/sweep_v1.csv` - per-work score at every point
- `results/sweep/fit_manifest.json`
- `results/qc_sweep_v1/`
- Pre-registration: `results/phase11_resolution_sweep_design.md`
