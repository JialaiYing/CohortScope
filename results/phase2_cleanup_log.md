# Phase 2 cleanup log (T026 / D24)

**Role:** cv · **Date:** 2026-08-06  
**Trigger:** T025 PASS with patches; should-fix docs before Phase 3

---

## Removed

| Path | Reason |
|---|---|
| *(none)* | No one-off review/scratch scripts found. Python surface remains `preprocess.py`, `acquire.py`, `rijks_api.py`, `config.py` only. |

## Added / patched

| Path | Change |
|---|---|
| `results/qc_preprocess_v1/geometry_note.md` | **New.** Width=1500 vs long-edge 1500 (5 / 20); Branch H identity; D27 |
| `data/preprocessed/preprocess_v1/manifest.json` | `geometry_note` → that file |
| `preprocess.py` module docstring | Consumer contract: Features = Branch H only; Branch C = embeddings-only |
| `docs/tasks.md` | T026 → done; Phase 3 gate unblocked for design |

## Kept (intentional)

- `preprocess.py` and `preprocess_v1` cache (`rgb/`, `cnn/`, `manifest.json`)
- QC: `results/qc_preprocess_v1/before_after_grid.png`, `failures.csv`
- Design / review / sign-off memos: `phase2_preprocess_design.md`, `phase2_preprocess_stats_memo.md`, `phase2_features_signoff.md`, `phase2_review.md`

## Not touched (intentional)

- Preprocess ops / transforms (no re-run, no val-driven retune)
- Phase 1 images / SQLite
- Phase 3 embeddings or hand-built feature code

## Hand-off

Phase 2 cleanup complete. Orchestrator may open Phase 3 design gate (CV T030 / Features T031). Do not start embedding extraction until that gate.
