# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

CohortScope is a datathon research pipeline: it ranks Rijksmuseum Rembrandt oil paintings by how anomalous they look versus a firm-attribution "cohort", using pretrained ResNet50 embeddings (Signal A) plus 8 handcrafted texture/color features (Signal B). It is a **science deliverable (tables/CSV), not a product**.

**The method does not currently work, and the repo says so.** Two held-out tests: O04 (`weak`, N=1, `results/validation_report.md`) and O06 (**`fail`**, N=67 documented Rembrandt pupils, AUC 0.419, `results/pupil_validation_report.md`). Per-signal AUC is at chance for both signals, and mm/px of the source image alone separates the classes better (0.590) than the whole pipeline. Never write code or docs that claim the method works.

## Commands

Environment: mamba env `CohortScope`, Python 3.13, Windows, CUDA torch (RTX 3050 4 GB). CPU torch also works.

```bash
mamba activate CohortScope
python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
python -m pip install -r requirements.txt
```

Pipeline stages must run in order; each reads the previous stage's manifest:

```bash
python acquire.py      # Rijksmuseum API → data/cohortscope.sqlite + data/images/
python preprocess.py   # → data/preprocessed/preprocess_v1/{rgb,cnn}/
python embed.py        # → data/embeddings/embed_v1/ (vectors/ + matrix.pt)
python features.py     # → data/features/features_v1.csv
python score.py        # → results/scores/ + results/validation_report.md
python dimensions.py       # backfill geometry onto pre-D33 rows (no-op after a fresh harvest)
python evaluate_pupils.py  # → results/pupil_validation_report.md (O06)
python resolution_audit.py # → results/resolution_audit.{md,csv}
python demo_app.py     # optional read-only Gradio viewer over existing scores
```

All shipped artifacts are committed except `data/preprocessed/` (see below). `preprocess`, `embed`, `features`, `score`, `evaluate_pupils`, and `resolution_audit` **refuse to overwrite** existing outputs unless given `--force`; `dimensions.py` is incremental instead (it only fills gaps). `acquire.py` takes `--dry-run` (no image download / no DB write), `--inventory` (regenerate `results/inventory.*` from the existing DB), and `--pupils-only`. `acquire.py` and `dimensions.py` are the only stages that need network.

`acquire.py --pupils-only` adds the D32 pupil cohort **additively** against an existing DB, migrating the `works` table to the wider split enum and leaving every pre-existing row and image byte-identical. Prefer it over a full re-harvest, which deletes and rebuilds the DB and re-downloads every image.

There is no test suite, linter config, or CI. Verification is by re-running a stage with `--force` and diffing its manifest / QC CSVs.

## Architecture

Flat modules at repo root (D15); docs in `docs/`, artifacts in `data/` and `results/`.

**Recipe-ID contract.** Every stage has a frozen `RECIPE_ID` (`preprocess_v1`, `embed_v1`, `features_v1`, `scores_v1`) that names its output directory and is written into a `manifest.json`. Downstream stages read the upstream manifest, assert `recipe_id`, and use its `object_numbers` / `splits_by_id` as the worklist — they do **not** re-glob the filesystem or re-query SQLite for the worklist. Changing a recipe means bumping the ID and rerunning everything downstream, not editing outputs in place.

**Two-branch preprocess (D26/D29).** `preprocess.py` writes two disjoint caches from the same JPEG:
- Branch H `rgb/*.png` — identity/EXIF-corrected RGB, **only** consumer is `features.py` (interpretable features).
- Branch C `cnn/*.pt` — 256-resize/224-center-crop/ImageNet-normalized tensors, **only** consumer is `embed.py`.

Never cross the branches: hand-built features must not read CNN tensors, and the CNN must not read Branch H PNGs.

**Splits (D19–D21, D32).** `works.split` is one of `cohort | validation | ambiguous | pupil | excluded`, assigned by priority rules in `acquire.py` (circle/workshop/school phrases → validation; attributed-to → ambiguous; `creator=`-matched documented pupils → pupil). Downstream stages process `SCORED_SPLITS = ("cohort","validation","ambiguous","pupil")`. Statistical normals are fit on `split=cohort` **only** (N=23) — `ambiguous` and `pupil` are scored but never enter a fit or the O04 outcome. `score.py` enforces this structurally: every fit path branches on `meta[oid]["split"] == "cohort"`, so a new split is non-fitting by construction.

**Pre-registration is the project's core discipline.** O04 and O06 both have a design document committed *before* the data existed (`results/phase4_scoring_design.md`, `results/phase7_pupil_validation_design.md`). Thresholds, seeds, and k values in `evaluate_pupils.py` are transcribed from those docs — do not edit them to move an outcome. When a locked rule costs you samples (O06 lost 3 works to §3.1), record the loss in the report rather than amending the rule.

**Scoring (D30, `score.py`).** Signal A = cosine distance to the cohort embedding centroid → `z_A`; Signal B = RMS of the 8 cohort feature z-scores → `z_B`; `combined = z_A + z_B`. Cohort rows use **leave-one-out** centroid and LOO mean/std so a work never contributes to its own normal; validation/ambiguous rows use the full-cohort statistics. O04 tiers for SK-A-3934: `pass` ≥ cohort p95, `weak` ≥ median, else `fail`. No AUC (N=1). Per-signal drivers are always kept — a single opaque score is explicitly rejected.

**`data/preprocessed/` is gitignored.** It is ~340 MB of PNG/tensor cache that `preprocess.py` regenerates byte-identically from the tracked `data/images/`. A fresh clone must run `python preprocess.py` before `embed.py` or `features.py`. Everything else in `data/` is tracked.

**Physical geometry (D33).** `works` stores `cm_width`/`cm_height` (catalogued), `native_px_*` (IIIF `info.json`), `analyzed_px_*`, and derived `mm_per_px_analyzed` / `mm_per_px_native`. `acquire.compute_geometry()` is the single producer, called both during harvest and by `dimensions.py` (which backfills by default, takes `--force` to re-resolve everything and `--check` to report coverage without network); the DB is authoritative and there is no side-cache. All columns are **nullable on purpose** — the museum does not catalogue a size for every object, and "unknown" must stay distinguishable from "fine". Never coerce a missing mm/px to 0 or to a default.

`acquire.migrate_schema()` brings an older DB forward: a CHECK-constraint change (widening the split enum) forces a table rebuild, plain nullable columns do not. It is idempotent and returns a list of what it changed. Add new plain columns to `ADDED_COLUMNS` and to `DDL`.

**Geometry changes no score.** D33 is data capture only. `features.py`, `embed.py`, and `score.py` do not read the geometry columns — resampling to a fixed physical resolution is a separate, still-unmade decision (**O07**), and `results/resolution_audit.md` deliberately declines to pick a floor for that reason.

**QC side-channel.** Each stage writes `results/qc_<recipe_id>/` (failures CSV, summary JSON) alongside its data output; failures are logged rather than silently dropped.

`rijks_api.py` is the only HTTP layer (search / resolve / IIIF); `acquire.py` owns SQLite, splits, and inventory. `config.py` holds locked constants (API filters, IIIF template, backbone) — treat its values as decisions, not tunables.

## Working conventions

- `docs/decisions.md` is the source of truth for locked decisions (D01–D33). Read it before proposing anything that contradicts a `D##`; changing a locked decision requires human approval plus a dated update to that file. `docs/tasks.md` and `docs/roadmap-phase-plan.md` are the shared task/phase state.
- Code and design docs cite decision/task IDs (`D30`, `T043`, `O04`) in docstrings and reports. Keep doing this — the write-up traces back through them.
- After a phase succeeds: cleanup pass (D24) → git commit + push to `origin/main` (D28). Cleanup logs live at `results/phase*_cleanup_log.md`.
- Deferred and not to be reopened without strong reason: FastAPI/service layer, DINOv2 or alternate backbones, finetuning, multi-museum cohorts, folding attributed-to works into primary validation.
- `.cursor/rules/multi-agent.mdc` casts the default agent as an orchestrator that routes to specialists in `docs/agents/` rather than primary-coding. That workflow is documentation-only; do not let it block doing the work when the human asks directly.
- `requirements.txt` omits `scipy` even though `features.py` imports `scipy.ndimage` — it arrives transitively via `scikit-learn`.
