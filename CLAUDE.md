# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

CohortScope is a datathon research pipeline: it ranks Rijksmuseum Rembrandt oil paintings by how anomalous they look versus a firm-attribution "cohort", using pretrained ResNet50 embeddings (Signal A) plus 8 handcrafted texture/color features (Signal B). It is a **science deliverable (tables/CSV), not a product**.

**The method does not work, the repo says so, and the question is closed.** Five held-out outcomes: O04 (`weak`, N=1), O06 (**`fail`**, N=67 pupils, AUC 0.419), O09 (**`fail`**, Signal B at 0.20 mm/px, AUC 0.469), O11 (**`fail`**, Signal A at 0.20 mm/px with no resize, AUC 0.523), O13 (**`fail`**, both signals swept 0.15–0.30 mm/px on a fixed population — all eight points within 0.047 of chance).

The escape hatches are closed in order: the 35× scale confound was real and D34 removed it; both halves were then retested on commensurable pixels and both failed; the sweep then showed 0.20 was not simply the wrong scale. In **all four** pupil tests a digitization column alone out-separates the whole pipeline — `mm_per_px_analyzed` 0.590 (O06), `mm_per_px_native` 0.689 (O09), 0.705 (O11), 0.617 (O13). Never write code or docs that claim the method works, and do not propose a sixth variant of it without new evidence.

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
python tiles.py            # → data/tiles/tiles_v1/ + results/tiling_report.md (D34)
python tile_features.py    # → data/features/tile_features_v1.csv (one row per tile, D35)
python tile_score.py       # → results/tile_scores/ + results/tile_validation_report.md (O09)
python cnn_tiles.py        # → data/tiles/cnn_tiles_v1/ (224 px tiles for Signal A, D36)
python tile_embed.py       # → data/embeddings/tile_embed_v1/matrix.pt
python tile_score_a.py     # → results/tile_embedding_report.md (O11)
python sweep.py --plan     # sweep population census; no network (D37)
python sweep.py --fetch    # fetch the 4,800 sweep tiles (~85 min, resumable)
python sweep.py            # → results/sweep/ + results/resolution_sweep_report.md (O13)
python demo_app.py     # optional read-only Gradio viewer over existing scores
```

All shipped artifacts are committed except `data/preprocessed/` (see below). `preprocess`, `embed`, `features`, `score`, `evaluate_pupils`, `resolution_audit`, `tile_features`, `tile_score`, `tile_embed`, and `tile_score_a` **refuse to overwrite** existing outputs unless given `--force`; `dimensions.py` is incremental instead (it only fills gaps). `acquire.py` takes `--dry-run` (no image download / no DB write), `--inventory` (regenerate `results/inventory.*` from the existing DB), and `--pupils-only`. `acquire.py` and `dimensions.py` are the only stages that need network.

`acquire.py --pupils-only` adds the D32 pupil cohort **additively** against an existing DB, migrating the `works` table to the wider split enum and leaving every pre-existing row and image byte-identical. Prefer it over a full re-harvest, which deletes and rebuilds the DB and re-downloads every image.

There is no test suite, linter config, or CI. Verification is by re-running a stage with `--force` and diffing its manifest / QC CSVs.

## Architecture

Flat modules at repo root (D15); docs in `docs/`, artifacts in `data/` and `results/`.

**Recipe-ID contract.** Every stage has a frozen `RECIPE_ID` (`preprocess_v1`, `embed_v1`, `features_v1`, `scores_v1`, `tiles_v1`, `tile_features_v1`, `tile_scores_v1`, `cnn_tiles_v1`, `tile_embed_v1`, `tile_scores_a_v1`, `sweep_v1`) that names its output directory and is written into a `manifest.json`. Downstream stages read the upstream manifest, assert `recipe_id`, and use its `object_numbers` / `splits_by_id` as the worklist — they do **not** re-glob the filesystem or re-query SQLite for the worklist. Changing a recipe means bumping the ID and rerunning everything downstream, not editing outputs in place.

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

**Physically-normalized tiling (D34, `tiles.py`).** The second acquisition path, parallel to `preprocess_v1` rather than replacing it. Instead of one fixed-1500px image per work it fetches 20 IIIF **region** tiles, each covering 30 mm × 30 mm of canvas served at 150 × 150 px — so every tile is 0.20 mm/px on a 15 cm panel and on a 4 m canvas alike. Tile selection is deterministic (evenly spaced indices over the row-major grid, no RNG), so the same DB yields the same tiles every run.

Works whose `mm_per_px_native` exceeds the 0.20 floor are **below floor**: not tiled, and not to be scored on this recipe. Six firm Rembrandts including the Night Watch fall out, taking the cohort from 23 to 17. That exclusion is the point — reporting a work as unanswerable beats scoring it on inadequate pixels. Eligibility is **derived, never stored on `works`**: the table holds measured facts, the floor is policy, and cached policy goes stale silently.

`data/tiles/` is gitignored (regenerable via `python tiles.py`). `scores_v1` and the whole fixed-1500 chain stay published as the baseline the normalized pipeline gets compared against — deleting them would destroy that comparison.

**Tile statistics (D35, `tile_features.py` + `tile_score.py`).** The Signal-B half of the pipeline recomputed on `tiles_v1`. `tile_features.py` calls the *same* `features.extract_one()` with the *same* constants — the only difference from `features_v1` is what a pixel means, and that is the experimental control. `tile_score.py` aggregates a work by the **median over its 20 tiles**, fits cohort-only LOO normals on the 17 eligible firm Rembrandts, and reports `z_B_tile` = RMS of the 8 z-scores.

**There is no Signal A and no `combined` on this recipe, on purpose.** A 150 px tile cannot enter the 224 px `embed_v1` branch without a resample factor, which is the arbitrariness D34 exists to remove. A result here is evidence about the handcrafted signal only.

Two rules that look like edge cases and are not: (1) a tile is **never** dropped for what it depicts — `hue_circ_std` is undefined on 77 near-grey tiles, and those cells are excluded from that one feature's median while the tile is kept, because dropping the tile is content-based filtering with a class-correlated rate (design §4.1). (2) The report always prints the paired **ΔAUC** against `features_v1` re-fit on the same 55 works, so the pixels are the only thing that differs between the arms.

**Signal A on commensurable pixels (D36, `cnn_tiles.py` + `tile_embed.py` + `tile_score_a.py`).** The other half, and the answer to the obstacle D35 §2 named. `tiles.py` carries a `Recipe` dataclass with two instances — `TILES_V1` (150 px / 30 mm, D34) and `CNN_TILES_V1` (224 px / 44.8 mm, D36) — so the deterministic selection rule has **one** implementation and cannot drift between them. Adding a recipe means adding a `Recipe`, never copying the tiler.

**44.8 mm is derived, not chosen:** 224 px (fixed by `config.BACKBONE`) × 0.20 mm/px (locked as O07). Because the region arrives at the backbone's native input size, `tile_embed.py` applies **only ImageNet normalization — no resize, no crop, no interpolation**. It deliberately does *not* call `preprocess.build_cnn_transform()`, whose 256-resize and 224-crop are exactly what makes `embed_v1`'s mm/px vary per work. It reuses `embed.build_model()` rather than constructing its own network, so backbone, weights, and layer cannot diverge from `embed_v1`.

The larger tile costs 3 works (64 → 61), all the physically **smallest** — D34's exclusions were the largest, so the two recipes are size-biased in opposite directions. **There is no `combined` on either tile recipe**: Signal A and Signal B now live on different populations (61 vs 64), so summing their z-scores would sum different corpora.

**The resolution sweep (D37, `sweep.py`).** The declared experiment `phase8 §4.5` named as the only legitimate way to vary the locked floor. Three things about it are load-bearing and easy to get wrong if it is ever re-run:

1. **`Recipe.floor_mm_per_px` is per-recipe, not `config.TILE_FLOOR_MM_PER_PX`.** A recipe that requests a finer tile than the source supports would have IIIF **upsample** to fill it — inventing resolution, the one failure this whole line of work exists to prevent. `Recipe.__post_init__` asserts `size_mm == size_px × floor`, so the tile size cannot be chosen independently of the floor.
2. **The population is fixed across floors**, not re-derived per floor. Eligibility is **not monotonic** in the floor — a coarser floor admits more works by the mm/px test while excluding more by the 20-tiles-must-fit test — so a per-floor population would confound resolution with which paintings entered the sample. The 0.05–0.40 intersection is 6 works for Signal B and **zero** for Signal A, which is why the range is 0.15–0.30.
3. **Multiplicity is corrected.** 4 floors × 2 signals = 8 tests; the descriptive 95% CI and the Bonferroni 99.375% CI are computed from the *same* draws at *every* point, so the correction cannot be applied selectively to a winner.

`tiles_v1` and `cnn_tiles_v1` are reused as the 0.20 points rather than re-derived, and the run verifies that.

**Geometry changes no score.** D33 is data capture only. `features.py`, `embed.py`, and `score.py` do not read the geometry columns — resampling to a fixed physical resolution is a separate, still-unmade decision (**O07**), and `results/resolution_audit.md` deliberately declines to pick a floor for that reason.

**QC side-channel.** Each stage writes `results/qc_<recipe_id>/` (failures CSV, summary JSON) alongside its data output; failures are logged rather than silently dropped.

`rijks_api.py` is the only HTTP layer (search / resolve / IIIF); `acquire.py` owns SQLite, splits, and inventory. `config.py` holds locked constants (API filters, IIIF template, backbone) — treat its values as decisions, not tunables.

## Working conventions

- `docs/decisions.md` is the source of truth for locked decisions (D01–D37). Read it before proposing anything that contradicts a `D##`; changing a locked decision requires human approval plus a dated update to that file. `docs/tasks.md` and `docs/roadmap-phase-plan.md` are the shared task/phase state.
- Code and design docs cite decision/task IDs (`D30`, `T043`, `O04`) in docstrings and reports. Keep doing this — the write-up traces back through them.
- After a phase succeeds: cleanup pass (D24) → git commit + push to `origin/main` (D28). Cleanup logs live at `results/phase*_cleanup_log.md`.
- Deferred and not to be reopened without strong reason: FastAPI/service layer, DINOv2 or alternate backbones, finetuning, multi-museum cohorts, folding attributed-to works into primary validation.
- `.cursor/rules/multi-agent.mdc` casts the default agent as an orchestrator that routes to specialists in `docs/agents/` rather than primary-coding. That workflow is documentation-only; do not let it block doing the work when the human asks directly.
- `requirements.txt` omits `scipy` even though `features.py` imports `scipy.ndimage` — it arrives transitively via `scikit-learn`.
