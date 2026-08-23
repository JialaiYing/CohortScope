# Decisions — Cohortscope

Shared source of truth for locked choices. **Agents must read this before proposing changes.**  
To change a locked decision: propose in chat, get human approval, then update this file with date + reason.

Last updated: 2026-08-22 (D35 tile statistics run; O09 resolved = `fail`)

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
