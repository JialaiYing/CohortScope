# Decisions — Cohortscope

Shared source of truth for locked choices. **Agents must read this before proposing changes.**  
To change a locked decision: propose in chat, get human approval, then update this file with date + reason.

Last updated: 2026-08-23 (D38 findings dossier; the method is closed and the record is published)

---

## Locked

| ID | Decision | Rationale | Locked |
|---|---|---|---|
| D01 | Museum = Rijksmuseum only | Single imaging pipeline; avoid cross-museum confounds | briefing |
| D02 | Paintings only, Rembrandt focus | Brushstroke features don't transfer to prints/drawings | briefing |
| D03 | Main cohort = currently attributed Rembrandt van Rijn | Defines the statistical "normal" | briefing |
| D04 | Primary validation = circle / workshop / school / omgeving / atelier held out | Method only "works" if these look anomalous vs cohort | briefing; refined 2026-08-05 |
| D05 | Two signals: ResNet50 embeddings + hand-built texture/color | Decomposable flags required; no opaque single score | briefing + Phase 0 |
| D06 | ML framework = PyTorch | Briefing | briefing |
| D07 | Frontend deferred; Gradio later if needed | Prove method first; demo may be static results + short UI only if time | briefing |
| D08 | No FastAPI / backend API for now | Premature before method validated | 2026-08-05 |
| D09 | Env = mamba `CohortScope`, Python 3.13, Windows + CUDA | User setup; RTX 3050 4GB | Phase 0 |
| D10 | Search filters: `type=painting`, `material=oil paint`, `imageAvailable=true` | English terms verified; Dutch same counts | Phase 0 |
| D11 | Do **not** use `technique` as a search filter | API technique ≈ role ("painter"), not medium | Phase 0 |
| D12 | Image size = IIIF long-edge **1500px** | Quality vs &lt;5 GB budget; ~237 KB/sample | Phase 0 |
| D13 | Backbone = **ResNet50** (`IMAGENET1K_V2`) | Fits 4GB VRAM; DINOv2 only if ResNet50 signal fails | Phase 0 |
| D14 | Validation acquisition via **description** probes, then label filter | `creator=` workshop/circle phrases return 0 hits | Phase 0 |
| D15 | Project layout = minimal flat Python modules | User preference | Phase 0 |
| D16 | Working name = Cohortscope (placeholder OK) | Nothing depends on final name | briefing |
| D17 | Buffer days 12–13 treated as already spent | Do not plan work into buffer | briefing |
| D18 | Start date = 2026-08-04 (Day 1) | User confirmed | Phase 0 |
| D19 | Split enum = `cohort` \| `validation` \| `ambiguous` \| `excluded` | Stats T017; Data T010; human approved 2026-08-05 | 2026-08-05 |
| D20 | Split assignment = priority rules in `results/phase1_experimental_design.md` §1.2 | First match wins; probes are discovery only | 2026-08-05 |
| D21 | O05: *attributed to / toegeschreven aan Rembrandt* (incl. SK-A-4096) → `ambiguous` | Never fit normals; never count in T043; score exploratorily | 2026-08-05 |
| D22 | Phase 1 storage = SQLite `data/cohortscope.sqlite`, table `works` per T010 §1 | Human approved schema | 2026-08-05 |
| D23 | Phase 1 modules = `rijks_api.py` + `acquire.py`; `smoke_api.py` **removed** in T019 | Duplicate HTTP stack deleted | 2026-08-05 |
| D24 | After each successful phase: **cleanup pass** then **git push (D28)** before the next phase | Delete obsolete files; keep canonical artifacts; publish to GitHub | 2026-08-05; push added 2026-08-06 |
| D25 | Datathon submission pack (in-repo, excluding demo video) | See § Datathon below | 2026-08-05 |
| D26 | Phase 2 preprocess = `preprocess_v1` (Branch H RGB identity + Branch C 224 CNN) | Two-branch; scored splits only; no corpus pixel fit | 2026-08-05 human |
| D27 | IIIF geometry honesty: Phase 1 URLs use **width=1500** (`full/1500,`), not always long-edge 1500 | Tall works can have long edge &gt;1500; Branch H is identity on those JPEGs; document, do not val-retune | 2026-08-06 (T025) |
| D28 | After each phase succeeds (review + cleanup): **git commit + push to `origin/main`** | Datathon continuous publish; human approved 2026-08-06 | 2026-08-06 |
| D29 | Phase 3 extract = ResNet50 `embed_v1` (Branch C) + O03 **8** hand-built features (Branch H) | Human locked 2026-08-06; matrices per `results/phase3_matrix_contract.md`; no scoring in Phase 3 | 2026-08-06 |
| D30 | Phase 4 scoring = `results/phase4_scoring_design.md` (`scores_v1`) | A: cosine-to-centroid + z; B: RMS of 8 cohort z; O02: `combined=z_A+z_B`; O04: val p95/median tiers; cohort-only fit + LOO | 2026-08-07 human |
| D31 | Optional **read-only Gradio demo viewer** for T072 (`demo_app.py`) | Presentation aid only — not a product claim; does not reopen T050 or change O04; science deliverable remains CSV/tables (T054) | 2026-08-08 |
| D34 | **Physically-normalized tiling** (`tiles_v1`): IIIF region requests of 30 mm x 30 mm of canvas served at 150 x 150 px, 20 non-overlapping tiles per work, 5% edge inset, deterministic selection. Works whose native resolution is coarser than the floor are **below floor** and are not tiled | Fixed-pixel downloads made mm/px vary 35x, so texture features were not measuring the same physical quantity across works. Fixed-*area* requests make one pixel mean the same distance on every painting. Pre-registered in `results/phase8_tiling_design.md` **before** any tile was fetched. Computes no feature, embedding, or score; `scores_v1` is retained as the baseline | 2026-08-19 |
| D33 | **Physical geometry is first-class**: `works` stores catalogued cm size, native IIIF pixel size, analyzed pixel size, and derived `mm_per_px_analyzed` / `mm_per_px_native` | Texture features are implicitly measured in mm of canvas per pixel, and the fixed `width=1500` request made that quantity vary 35× across the corpus (D27). It cannot be reasoned about while it is unrecorded. Captured during acquisition; `dimensions.py` backfills existing snapshots. Changes **no** score | 2026-08-19 |
| D32 | **Pupil split** added to the split enum: documented Rembrandt pupils, catalogued under their own names, as a surrogate held-out negative class (O06) | D04's population cannot be grown inside D01 (N=1); pupils are the closest available stylistic neighbours and `creator=` search works for them. Pre-registered in `results/phase7_pupil_validation_design.md` **before** acquisition or scoring. Never fitted into cohort normals; never enters O04 | 2026-08-19 |
| D35 | **Tile statistics = Signal B only** (`tile_features_v1` / `tile_scores_v1`): the eight `features_v1` columns recomputed per 150x150 tile, aggregated to a work by the **median** over that work's 20 tiles, z-scored against a **cohort-only, leave-one-out** fit on the 17 eligible firm Rembrandts; `z_B_tile` = RMS of the 8 z-scores | Resolves O08. Signal A is excluded on purpose: tiles are 150 px and `embed_v1` wants 224, so embedding a tile means choosing a resample factor — the exact arbitrariness D34 exists to remove. Feature definitions are deliberately **unchanged** so the only difference from `features_v1` is what a pixel means. Pre-registered in `results/phase9_tile_statistics_design.md` before any feature value was computed from any tile. Does not amend O04 or O06; `scores_v1` stays published as the baseline. §4.1 of that document was added the same day, before any aggregate or AUC existed, to fix the handling of a feature that is undefined on a tile (77 of 1,280 tiles are entirely near-grey and have no hue): the tile is retained and the one cell is excluded from that feature's median, because dropping the tile would be the content-based filtering §4 forbids | 2026-08-22 |
| D36 | **Signal A on commensurable pixels** (`cnn_tiles_v1` / `tile_embed_v1` / `tile_scores_a_v1`): a second tile fetch at **44.8 mm x 44.8 mm served at 224 x 224 px**, embedded by the unchanged ResNet50 with **no resize and no crop**; work-level `d_A_tile` = median over the work's 20 tile cosine distances to a cohort-only, leave-one-out tile centroid | Resolves O10, the obstacle D35 §2 named. The tile size is **derived, not chosen**: 224 px (fixed by `config.BACKBONE`) x 0.20 mm/px (locked as O07) = 44.8 mm, so the resample factor that blocked Signal A on `tiles_v1` does not exist in this path. Backbone, weights, and layer are unchanged so the only difference from `embed_v1` is what a pixel means. Costs 3 works, the physically **smallest** (D34 lost the largest) — cohort 17->16, Tier-1 38->36. No `combined`: the two signals now live on different populations. Pre-registered in `results/phase10_tile_embedding_design.md` before any 224 px tile was fetched | 2026-08-23 |
| D37 | **Resolution-floor sweep** (`sweep_v1`): both signals re-run at **0.15 / 0.20 / 0.25 / 0.30 mm/px** on a **population held fixed across floors** (Signal B 16 vs 24; Signal A 15 vs 20), each signal holding its pixel count fixed (150 / 224) so only millimetres-per-pixel varies | Resolves O12. The declared, fully-reported experiment that `results/phase8_tiling_design.md` §4.5 named as the only legitimate way to vary the locked floor. Range is forced, not preferred: §3 of the design shows 0.15-0.30 is the widest contiguous range where a fixed population survives for both signals — a 0.05-0.40 sweep has **zero** works eligible at every floor for Signal A. Fixed pixel count keeps GLCM/LBP stability constant and keeps Signal A resize-free at every floor. `tiles_v1` and `cnn_tiles_v1` are reused as the 0.20 points. Pre-registered in `results/phase11_resolution_sweep_design.md` before any non-0.20 tile was fetched | 2026-08-23 |
| D38 | **Findings dossier** (`dossier.py` + `dossier_template.html` -> `results/dossier/index.html`): a single self-contained page presenting the closed negative result -- the five held-out outcomes, the alternatives ruled out in order, the resolution evidence, the flat sweep, the metadata confound, and a per-work adequacy lookup over all 108 works | Presentation layer only; restates D31 for the post-O13 state. **Every figure is read out of a committed artifact at build time**, never transcribed, so the page cannot drift from the results. Features that only make sense for a working method were deliberately **cut**: no anomaly heatmap (it would map noise at AUC 0.47), no precision@k triage widget (precision@k is at or below base rate), no contrastive 'look at this suspicious pupil' demo (cherry-picking). The reusable deliverable is the adequacy verdict, not the ranking | 2026-08-23 |

## Datathon submission mapping (D25)

Track expects: repo + dataset link in README + report + demo video. We control the first three; **demo video is human-owned** (orchestrator will list suggested footage late, not produce the video).

| Requirement | Our plan | Owner phase |
|---|---|---|
| Code repository | Public GitHub (or similar) with clear run instructions | Phase 5 + human publish |
| Dataset link in README | Document Rijksmuseum open collection + how to reproduce via `acquire.py`; optional zenodo/release of `data/` snapshot if GitHub LFS awkward | Phase 1 inventory already; README in Phase 5 (stub earlier OK) |
| Report | Methodology, decisions, results, evaluation honesty (tiny-N) | Literature Phase 5; Stats results feed |
| Demo video | Human records screen-capture of **Gradio demo viewer** (D31/T080) + validation `weak` | Human; after T080 |

**Method framing (do not warp the science to match “train a Kaggle model” wording):**  
This project uses a **pretrained** ResNet50 (no finetune by default) + handcrafted features + cohort anomaly scoring. Report language: “model/pipeline evaluation,” not “we trained a classifier from scratch on Kaggle.” Dataset remains Rijksmuseum (D01), not a forced Kaggle swap.

## Provisional (use until overturned)

| ID | Decision | Notes |
|---|---|---|
| P01 | Storage = SQLite at `data/cohortscope.sqlite` | **Locked for Phase 1 as D22** |
| P02 | Main cohort query creator = `Rembrandt van Rijn` | ~24 oil paintings with images |
| P03 | Exclude attributed/circle labels from cohort **statistics** even if they appear in Rembrandt search | Reinforced by D19–D21 |
| P04 | Agent roster = Project Manager + 6 specialists (see `docs/agents/`, launch via `docs/launch/`) | Manager routes; specialists execute |
| P05 | Description probes may omit `material` for discovery; exclude if known non-oil after resolve | Aligns Phase 0 smoke with D10 intent |

## Open

| ID | Question | Owner | Needed by |
|---|---|---|---|
| O01 | Final project display name | Human | write-up |

**O07 resolved (D34) — floor = `0.20 mm/px`:** chosen by the human on 2026-08-19 from the eligibility census in `results/resolution_audit.md` §4, before any tile was fetched. A 1 mm stroke spans 5 px at this floor. The 0.15 floor admits the *same* 17 cohort works while costing 12 Tier-1 pupils, so it is dominated. Accepted consequences, recorded in advance: the cohort shrinks **23 → 17** (the six physically largest firm Rembrandts, including the Night Watch at 0.310 mm/px native, are below floor) and Tier-2 pupils fall to 7. Eligible population **64 / 108**. See `results/phase8_tiling_design.md` §4 and `results/tiling_report.md`.

**O08 resolved (D35) — Signal B only, median over tiles, cohort-only LOO fit on 17:** pre-registered in `results/phase9_tile_statistics_design.md` on 2026-08-22, before any feature value was computed from any tile. Signal A is out of scope by design (§2 there): a 150 px tile cannot enter a 224 px CNN without a resample factor, which is the arbitrariness D34 removed. Consequences accepted in advance: there is **no `combined`** on this recipe, so the baseline to beat is `z_B` alone (**AUC 0.522**, not the 0.419 headline), and the comparison is a **paired ΔAUC** against `features_v1` re-fit on the same 55 eligible works so the pixels are the only thing that differs.

**O09 resolved (D35) — outcome `fail`.** Cohort (17) vs Tier-1 pupils (38) at a constant 0.20 mm/px: `z_B_tile` AUC = **0.469**, bootstrap 95% CI [0.303, 0.638] — below chance, CI spanning 0.50. The paired comparison locked in §5 gives **ΔAUC = +0.042**, 95% CI [−0.141, +0.223]: against `features_v1` re-fit on the same 55 works (AUC 0.427), physical normalization moved separation by an amount **indistinguishable from zero**. precision@k = 0.600 / 0.700 / 0.700 at k = 5/10/20 against a base rate of 0.691 — at or below a random shortlist. Per-feature AUC peaks at 0.627 (`grad_orient_entropy`); no single feature carries a signal. Tier-2 sensitivity (7 works) = 0.395, reported and never pooled.

**The successor confound fired exactly where §7 said it would.** With analyzed mm/px constant by construction, `mm_per_px_native` — how far the IIIF server had to downsample to reach the floor — separates the classes at **AUC 0.689**, out-performing the whole pipeline (0.469), the same shape as the 0.590 finding in O06. Native pixel width reaches 0.759 direction-free. The fail-closed clause therefore fires; per §8 it exists to override an otherwise-positive tier, and here there is none to override. Normalizing the *nominal* scale did not normalize the *effective* sharpness behind it.

**What O09 settles:** the 9.5× scale gradient O06 named as its largest exposure was real and D34 removed it, and separation was not hiding behind it. The handcrafted-feature line of attack is exhausted at 0.20 mm/px. **What it does not settle:** Signal A is untested at this resolution by design (§2), and the 17-work cohort is size-biased toward small and medium works. O04 (`weak`) and O06 (`fail`) are unchanged and unamended; `scores_v1` stays published as the fixed-pixel baseline. See `results/tile_validation_report.md`.

**O10 resolved (D36) — embed the tile natively, do not resize it.** D35 §2 excluded Signal A because a 150 px tile cannot enter a 224 px CNN without a per-work resample factor. The answer is to request the tile at 224 px in the first place: 224 x 0.20 mm/px = **44.8 mm** of canvas, so the region arrives at both the locked floor and the backbone's native input size and nothing is resized, cropped, or interpolated. Neither number was chosen for this phase — the floor is O07 and 224 is `config.BACKBONE`. Accepted in advance: 3 works fall out (64 -> 61), all of them the physically smallest, because a larger tile fits fewer times inside the inset.

**O11 resolved (D36) — outcome `fail`.** Cohort (16) vs Tier-1 pupils (36) with the CNN fed 224 px tiles at 0.20 mm/px and **no resize or crop anywhere in the path**: `z_A_tile` AUC = **0.523**, bootstrap 95% CI [0.318, 0.727] — chance, with a CI nearly 0.41 wide at N=52. The mean-embedding variant (§4, reported not substituted) gives 0.510. precision@k = 0.200 / 0.500 / 0.700 at k = 5/10/20 against a base rate of 0.692 — the top of the ranking is *worse* than random. Tier-2 sensitivity (7 works) = 0.438.

**ΔAUC = +0.132**, 95% CI [−0.092, +0.352], against `embed_v1` re-fit on the same 52 works (AUC 0.391). This is the largest movement any change has produced and the one place normalization visibly did something: the fixed-pixel arm sat clearly *below* chance and commensurable pixels brought it back to chance. But the CI contains zero, and an arm that lands on chance is not a method.

**Both halves of the method have now been tested on commensurable pixels and both failed.** O09 = `fail` for the eight handcrafted features at 0.20 mm/px; O11 = `fail` for the embedding at the same scale. The scale confound was real and was the best available explanation for O06 — D34 removed it, and what was left underneath is noise in both signals. Cross-signal Spearman ρ between `z_A_tile` and `z_B_tile` is +0.268 over the 61 shared works: close to independent, so neither rescues the other.

**The successor confound fired again, harder.** `mm_per_px_native` separates the classes at **AUC 0.705** (0.689 in O09) with Spearman ρ = −0.422 against `z_A_tile` — a genuine correlation, not a vacuous tie. How far the IIIF server had to downsample to reach the floor still out-predicts the pipeline.

**What O11 does not settle:** ImageNet features are not brushwork features, and a 44.8 mm tile is outside the training distribution of a network trained on whole objects. This is evidence about *this* backbone at *this* scale and is **not** a licence to reopen the deferred DINOv2 / finetuning work. O04, O06, and O09 are unchanged and unamended. See `results/tile_embedding_report.md`.



**O12 resolved (D37) — sweep 0.15-0.30 mm/px on a fixed population, pixel count held constant.** The obvious sweep (0.05-0.40, eight floors, all works eligible at each) is not available: eligibility is **not monotonic** in the floor, because a coarser floor admits more works by the mm/px test while excluding more by the 20-tiles-must-fit test. The eligible sets are therefore not nested, and the intersection over 0.05-0.40 is 6 works for Signal B and **0 for Signal A**. Only nine works in the corpus have imagery finer than 0.05 mm/px at all. 0.15-0.30 is the widest contiguous range retaining a usable fixed population (43 / 37 works), and it brackets the locked 0.20 floor on both sides. Each signal holds its **pixel count** fixed rather than its canvas size: the alternative would give Signal B 64x more texture samples at one end of the sweep than the other and would force a per-floor resize on Signal A, reintroducing the arbitrariness D34 and D36 removed. Accepted in advance: N drops to 40 / 35, and Tier-2 falls to one work so its sensitivity analysis is **not computed** in this phase.

**O13 resolved (D37) — outcome `fail`. The method is closed.** Both signals re-run at 0.15 / 0.20 / 0.25 / 0.30 mm/px on a population held fixed across floors (Signal B 16 vs 24, Signal A 15 vs 20), each signal holding its pixel count fixed so only millimetres-per-pixel varied:

| floor | Signal B AUC | Signal A AUC |
|---:|---:|---:|
| 0.15 | 0.466 | 0.453 |
| 0.20 | 0.474 | 0.530 |
| 0.25 | 0.484 | 0.503 |
| 0.30 | 0.495 | 0.473 |

**All eight points are at chance.** Signal B spans 0.466–0.495 across a 2× change in resolution, Signal A 0.453–0.530; every point sits within 0.047 of 0.500. Zero of eight clear the Bonferroni-corrected 99.375% bar — and zero clear even the *uncorrected* 95% bar, so the multiplicity correction never had to do any work. The curves are flat, not noisy-but-trending.

**The confound clause fires again.** `mm_per_px_native` separates the classes at AUC 0.557 (Signal B population) and 0.617 (Signal A population), beating the best swept point in both cases. That is the fourth consecutive test in which a digitization column out-predicts the pipeline: 0.590 in O06, 0.689 in O09, 0.705 in O11, and again here.

**What O13 settles:** the answer to "was 0.20 simply the wrong scale?" is **no**. Over a 2× range bracketing the locked floor, with the population fixed so only resolution varied, neither half of the method separates firm Rembrandts from their pupils at any resolution. Combined with O09 and O11, **the method as specified is closed.** Per design §7 this is not softened into a call for more resolution, and §3 shows it cannot be: nine works in the whole corpus have imagery finer than 0.05 mm/px, and **zero** support a full-range sweep for Signal A. The imagery to test a finer hypothesis does not exist in this collection.

**What O13 does not settle:** N is 40 and 35, so the experiment is well powered for a large resolution effect and poorly powered for a small one — it fails to find one, which is not the same as showing there is none. Tier-2 sensitivity was not computed (one work per sweep). ImageNet features are still not brushwork features, and a flat Signal-A curve is **not** a licence to reopen the deferred DINOv2 / finetuning work. O04, O06, O09, and O11 are unchanged and unamended; the locked 0.20 floor does not move. See `results/resolution_sweep_report.md`.

**O02 resolved (D30):** `combined = z_A + z_B`; keep per-signal drivers.  
**O03 resolved (D29):** 8 columns in `results/phase3_feature_shortlist.md` §1.  
**O04 resolved (D30):** SK-A-3934 pass ≥ cohort p95; weak median–p95; fail &lt; median; no AUC; ambiguous excluded.  
**O06 resolved (D32) — outcome `fail`:** cohort vs 67 Tier-1 pupils, AUC = **0.419**, bootstrap 95% CI [0.269, 0.578]. Per-signal AUC: `z_A` 0.427, `z_B` 0.522 — both at chance. precision@k is **below** the 0.744 base rate at k=5/10/20, so the ranking is worse than a random shortlist for triage. Confound check: **mm/px alone separates the two classes better (AUC 0.590) than the entire two-signal pipeline (0.419)**. See `results/pupil_validation_report.md`. O04 is unchanged.
## Explicitly deferred

- FastAPI / service layer — still deferred (D31 is Gradio viewer only)
- DINOv2 / alternate backbones — not opened (weak N=1 documented; no T050)
- Multi-artist / multi-museum — sustainability claim in write-up only this cycle
- T050 method rewrites — cancelled for Phase 5; document limitations instead

**T054 clarified by D31:** Core submission stays tables/CSV. A thin Gradio **viewer** over existing artifacts is allowed for the human demo video; it must not claim the method works or retune scores.

## Rejected / do not reopen without strong reason

- Training a custom backbone from scratch
- Mixing other museums into the Rembrandt cohort
- Single opaque anomaly score as the only output
- Folding attributed-to Rembrandt into primary validation by default (inflates N, mixes hypotheses)
- Random holdout of firm Rembrandt as “validation” (does not test D04)
