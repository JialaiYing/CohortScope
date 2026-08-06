# Phase 3 cleanup log (T038 / D24)

**Role:** features (+ any for push) · **Date:** 2026-08-06  
**Trigger:** T037 PASS; should-fix items from `results/phase3_review.md` §6

---

## Removed

| Path | Reason |
|---|---|
| *(none)* | No obsolete Phase 3 scratch scripts or duplicate matrices. |

## Added / patched (Features should-fix #1–2)

| Path | Change |
|---|---|
| `data/features/manifest.json` | Added `design`, `matrix_contract`, `geometry_note`, `decision: D29` (parity with `embed_v1`) |
| `data/features/features_v1_dictionary.md` | One-line note: `hue_circ_std` is **Lab** hue, not HSV |
| `results/phase3_feature_shortlist.md` | Lab/hue recipe row corrected (Lab-only; not HSV) |
| `features.py` | Same manifest pointers + dictionary note so future `--force` runs stay aligned |

## Not touched (intentional)

| Item | Reason |
|---|---|
| `data/features/features_v1.csv` | **No re-extract** — feature values unchanged |
| Branch H / Branch C caches | Unchanged |
| Embeddings (`embed_v1`) | CV-owned; already had audit pointers |
| Should-fix #3 (shared worklist source) | Optional; deferred — both extractors still agree on N=25 |
| Scoring / z-scores | Forbidden until Phase 4 |

## Kept (canonical)

- `features.py`, `embed.py`
- `data/features/features_v1.csv` + dictionary + manifest
- `data/embeddings/embed_v1/`
- QC: `results/qc_features_v1/`, `results/qc_embed_v1/`
- Design/contract/review: T030–T035 memos, `phase3_review.md`

## Hand-off

Features T038 should-fix **done**. Orchestrator / any: **git commit + push** (D28) when ready, then open Phase 4 design gate (**T040** — O02/O04). Do not start scoring until T040 is human-locked.
