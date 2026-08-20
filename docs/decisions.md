# Decisions — Cohortscope

Shared source of truth for locked choices. **Agents must read this before proposing changes.**  
To change a locked decision: propose in chat, get human approval, then update this file with date + reason.

Last updated: 2026-08-19 (D32 pupil-cohort validation; O06 = `fail`)

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
| D32 | **Pupil split** added to the split enum: documented Rembrandt pupils, catalogued under their own names, as a surrogate held-out negative class (O06) | D04's population cannot be grown inside D01 (N=1); pupils are the closest available stylistic neighbours and `creator=` search works for them. Pre-registered in `results/phase7_pupil_validation_design.md` **before** acquisition or scoring. Never fitted into cohort normals; never enters O04 | 2026-08-19 |

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
