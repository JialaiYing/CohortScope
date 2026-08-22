# Tasks — Cohortscope

Shared board. **Update status here when you finish or unblock work.**  
Statuses: `todo` | `in_progress` | `blocked` | `done` | `cancelled`

Last updated: 2026-08-22 (Phase 7/8 backfilled; Phase 9 pre-registered — D35 / O08 resolved, O09 open)

---

## How to use (all agents)

1. Read `docs/decisions.md` and this file at session start.
2. Only pick tasks tagged with your role (or marked `any`).
3. Set status to `in_progress` before coding; `done` when deliverable exists on disk.
4. If blocked, set `blocked` and name the blocker in Notes.
5. Do not expand scope into another role’s column — hand off via a new task instead.

---

## Current phase

**Phase 0–6 — DONE** (on GitHub; O04=`weak`)  
**Phase 7 pupil validation — DONE** (D32; **O06 = `fail`**, AUC 0.419; mm/px alone separates better at 0.590)  
**Phase 8 physically-normalized tiling — DONE** (D33 geometry + D34 `tiles_v1`; O07 = 0.20 mm/px; 1,280 tiles over 64 eligible works)  
**Phase 9 tile statistics — pre-registered, not yet implemented** (D35; O08 resolved, **O09 open**) → `results/phase9_tile_statistics_design.md`  
**T072** demo video remains human — launch `python demo_app.py`  
**Datathon:** https://github.com/JialaiYing/CohortScope.git  


---

## Board

### Phase 0 — Prerequisites

| ID | Task | Role | Status | Notes |
|---|---|---|---|---|
| T001 | Confirm env (mamba, CUDA, PyTorch) | data | done | CohortScope env; torch 2.6+cu124; RTX 3050 |
| T002 | API smoke + IIIF probe | data | done | Phase 0; `smoke_api.py` removed in T019 (see cleanup log) |
| T003 | Lock filters, image size, backbone | any | done | See `docs/decisions.md` D10–D13 |
| T004 | Creator / validation label discovery | data | done | Description probes required for validation |

### Phase 1 — Data acquisition (Days 1–2)

| ID | Task | Role | Status | Notes |
|---|---|---|---|---|
| T016 | Note prior-art dataset practices for write-up | literature | done | `results/prior_art_dataset_practices.md` |
| T017 | Experimental-design memo: split, O05, tiny-N | stats | done | `results/phase1_experimental_design.md` — **human locked** |
| T010 | Design acquisition split + schema | data | done | `results/phase1_acquisition_design.md` — **human locked** |
| T011 | Implement paginated search + resolve + IIIF download | data | done | `rijks_api.py` + `acquire.py`; IIIF 1500px |
| T012 | Build main cohort table (exclude validation labels) | data | done | cohort N=23; hedges excluded from cohort |
| T013 | Build curated validation set from description probes | data | done | validation=1 (SK-A-3934); ambiguous=1 (SK-A-4096) |
| T014 | Persist metadata locally (SQLite works table) | data | done | `data/cohortscope.sqlite` |
| T015 | Inventory report: counts, missing images, label list | data | done | `results/inventory.json` + `inventory.md` |
| T018 | Review Phase 1 artifacts for leakage/split/schema | review | done | `results/phase1_review.md` — **PASS with patches**; no must-fix |
| T019 | Phase 1 cleanup (D24) + should-fix #1–2 | data | done | `results/phase1_cleanup_log.md`; smoke leftovers gone; `smoke_api.py` deleted |

### Phase 5 submission track (D25) — schedule in Days 10–11; stub OK earlier

| ID | Task | Role | Status | Notes |
|---|---|---|---|---|
| T070 | Root README: run instructions + dataset link (Rijksmuseum / acquire reproduce) | data + literature | done | Root `README.md` — acquire→score runbook; dataset + GitHub link |
| T071 | Datathon report (method, decisions, results, evaluation) | literature | done | `results/datathon_report.md` (folds T051+T052); O04=weak |
| T072 | Human: publish GitHub + record demo video | human | todo | Repo already public; video still human |

### Phase 2 — Preprocessing (Days 3–4)

| ID | Task | Role | Status | Notes |
|---|---|---|---|---|
| T020 | Design normalize pipeline (scale, color) | cv | done | `results/phase2_preprocess_design.md` — **human locked (D26)** |
| T024 | Preprocess leakage / allowed stats memo (L6) | stats | done | `results/phase2_preprocess_stats_memo.md` — per-image only; published ImageNet constants |
| T023 | Confirm preprocess does not erase brushstroke signal | features | done | `results/phase2_features_signoff.md` — **Approve**; Branch H @1500 only |
| T021 | Implement preprocess → cached tensors/images | cv | done | `preprocess.py`; `data/preprocessed/preprocess_v1/` N=25 |
| T022 | QC: before/after samples + failure log | cv | done | `results/qc_preprocess_v1/` — 0 failures |
| T025 | Review Phase 2 artifacts | review | done | `results/phase2_review.md` — **PASS with patches**; no must-fix |
| T026 | Phase 2 cleanup (D24) + should-fix docs | cv | done | `results/phase2_cleanup_log.md`; geometry note + docstring |
| T027 | Phase 2 git push (D28) | any | done | This commit |

### Phase 3 — Feature extraction (Days 5–7)

| ID | Task | Role | Status | Notes |
|---|---|---|---|---|
| T030 | Design ResNet50 embedding extract I/O | cv | done | locked D29 |
| T031 | Shortlist interpretable features (O03 confirm) | features | done | locked D29 — 8 cols |
| T034 | Literature notes on wavelet/brushstroke auth | literature | done | `results/prior_art_brushstroke_auth.md` |
| T035 | Stats note: embedding/feature matrix contract | stats | done | `results/phase3_matrix_contract.md` |
| T032 | Implement texture / brushstroke / palette stats | features | done | `features.py`; Branch H only; 8 O03 cols |
| T033 | Feature matrix export + schema doc | features | done | `data/features/features_v1.csv` + dictionary; QC 0 failures |
| T036 | Implement ResNet50 embedding extractor | cv | done | `embed.py`; `data/embeddings/embed_v1/` N=25; QC 0 fails |
| T037 | Review Phase 3 artifacts | review | done | `results/phase3_review.md` — **PASS**; no must-fix |
| T038 | Phase 3 cleanup + git push (D24/D28) | any | done | cleanup log + this push |

### Phase 4 — Scoring + validation (Days 8–9)

| ID | Task | Role | Status | Notes |
|---|---|---|---|---|
| T040 | Design decomposable outlier score (confirm) | stats | done | locked D30 |
| T041 | Fit cohort normals on **main cohort only** | stats | done | `score.py` — cohort LOO fits; `results/scores/fit_manifest.json` |
| T042 | Score all works; emit ranked table + per-signal drivers | stats | done | `results/scores/scores_v1.csv` (N=25) |
| T043 | Validate vs held-out circle/workshop set | stats | done | `results/validation_report.md` — **O04=`weak`** (SK-A-3934); rules not retuned |
| T044 | Critique stats method + leakage risks | review | done | `results/phase4_review.md` — **PASS**; O04=weak confirmed; no must-fix |
| T045 | Draft results narrative (pass/fail honesty) | literature | done | `results/phase4_results_narrative.md` — O04=`weak`; do not claim works |
| T046 | Phase 4 cleanup + git push (D24/D28) | any | done | cleanup log + this push |


### Phase 5 — Iterate + write-up (Days 10–11)

| ID | Task | Role | Status | Notes |
|---|---|---|---|---|
| T050 | Fix failures from validation | stats+cv+features | cancelled | Human/orchestrator: closed — document weak; no retune |
| T051 | Methodology + limits write-up | literature | done | Folded into `results/datathon_report.md` |
| T052 | Sustainability claim (second artist without code change) | literature | done | Design-level §8 in `results/datathon_report.md` |
| T053 | Final code review + scope check | review | done | `results/phase5_review.md` — **PASS**; no must-fix |
| T054 | Decide Gradio/API or stay tables-only | any | done | Science = tables-only; **D31** allows read-only Gradio **viewer** for video |
| T055 | Phase 5 cleanup + git push (D24/D28) | any | done | cleanup log + this push |

### Phase 6 — Buffer / demo aid (Days 12–13)

| ID | Task | Role | Status | Notes |
|---|---|---|---|---|
| T060 | Buffer — do not schedule new features here | any | cancelled | D17 — science features still cancelled |
| T080 | Gradio read-only demo viewer for T072 | any | done | D31 — `demo_app.py`; scores+images only; default=SK-A-3934; O04 weak copy; no score import |
| T081 | README + requirements: how to launch demo | any | done | `## Demo viewer (optional)` + `gradio>=4.0.0` in requirements |
| T082 | Quick demo review (honesty + scope) | review | done | `results/phase6_demo_review.md` — **PASS**; no must-fix |
| T083 | Demo cleanup + git push | any | done | cleanup log + this push |

### Phase 7 — Pupil-cohort validation (D32 / O06)

| ID | Task | Role | Status | Notes |
|---|---|---|---|---|
| T070 | Pre-register pupil validation **before** acquiring any pupil work | stats | done | `results/phase7_pupil_validation_design.md`; D32; thresholds + seed locked in advance |
| T071 | Acquire Tier-1/Tier-2 pupils additively (`acquire.py --pupils-only`) | data | done | split enum widened via `migrate_schema()`; pre-existing rows byte-identical |
| T073 | Score pupils on `scores_v1`; evaluate O06 | stats | done | `evaluate_pupils.py` → `results/pupil_validation_report.md` — **O06 = `fail`**, AUC 0.419, CI [0.269, 0.578] |
| T074 | Report the confound honestly | stats | done | mm/px alone AUC **0.590** > pipeline 0.419; 3 works lost to §3.1 recorded, rule not amended |

### Phase 8 — Physical geometry + normalized tiling (D33 / D34 / O07)

| ID | Task | Role | Status | Notes |
|---|---|---|---|---|
| T090 | Make physical geometry first-class on `works` | data | done | D33; `acquire.compute_geometry()` sole producer; `dimensions.py` backfills; all columns nullable on purpose |
| T091 | Audit resolution exposure; decline to pick a floor | stats | done | `resolution_audit.py` → `results/resolution_audit.{md,csv}`; 30× mm/px spread; audit deliberately picks no floor |
| T092 | Human picks the floor (O07) from the eligibility census | human | done | **0.20 mm/px**, chosen 2026-08-19 before any tile fetched; 0.15 dominated |
| T093 | Pre-register tiling **before** fetching any tile | cv | done | `results/phase8_tiling_design.md`; D34; cohort 23→17 accepted in advance |
| T094 | Fetch tiles (`tiles.py` / `tiles_v1`) | cv | done | 1,280 tiles, 5.5 MB, 64/108 eligible; `results/tiling_report.md`; **no** feature/score computed |
| T095 | Phase 7+8 cleanup + git push | any | done | commits `48332fd`…`3f1a95a` |

### Phase 9 — Statistics over the tile population (D35 / O08 → O09)

| ID | Task | Role | Status | Notes |
|---|---|---|---|---|
| T100 | Pre-register tile statistics **before** computing any feature value | stats | done | `results/phase9_tile_statistics_design.md`; D35; O08 resolved = Signal B only, median-over-tiles, cohort-only LOO on 17 |
| T101 | Implement `tile_features.py` (`tile_features_v1`) | features | todo | 8 unchanged `features_v1` columns per tile; reads `tiles_v1` manifest as worklist; `--force` guard + `results/qc_tile_features_v1/` |
| T102 | Implement `tile_score.py` (`tile_scores_v1`) | stats | todo | median aggregate + IQR; cohort-only LOO fit on N=17; `z_B_tile` = RMS of 8 z; **no `z_A`, no `combined`** |
| T103 | Evaluate O09 + paired ΔAUC vs `features_v1` re-fit on the same 55 works | stats | todo | seed 20260822; k ∈ {5,10,20}; base rate 0.691 → `results/tile_validation_report.md` |
| T104 | Run the §7 confound successors fail-closed | stats | todo | `mm_per_px_native`, native px width, canvas cm², tiles written; any AUC ≥ `z_B_tile` ⇒ report **confounded** |
| T105 | Phase 9 cleanup + git push (D24/D28) | any | todo | — |

---

## Active blockers

| Blocker | Blocks | Owner |
|---|---|---|
| T072 demo video | Submission complete | human |
| T101 `tile_features.py` | T102–T104, O09 | features |

## Parallel work allowed now

- Human: record T072 with `python demo_app.py`  
- T101 may start now — D35 is pre-registered and the tile cache exists  
- Do **not** open T050 / retune O04  
- Do **not** edit the D35 thresholds, seed, k values, or the median aggregation rule to move O09  
- Do **not** re-run at another floor as a substitute for a disappointing 0.20 result (declared sweep only)  


---

## Role legend

| Role key | Agent | Launch |
|---|---|---|
| `any` | Project Manager (default chat) | `docs/agents/project-manager.md` |
| `data` | Data Engineer | `docs/launch/data-engineer.md` |
| `cv` | Computer Vision | `docs/launch/computer-vision.md` |
| `features` | Feature Engineering | `docs/launch/feature-engineering.md` |
| `stats` | Statistics | `docs/launch/statistics.md` |
| `literature` | Literature | `docs/launch/literature.md` |
| `review` | Code Reviewer | `docs/launch/code-reviewer.md` |
