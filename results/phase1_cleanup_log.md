# Phase 1 cleanup log (T019 / D24)

**Role:** data · **Date:** 2026-08-05  
**Trigger:** T018 PASS with patches; orchestrator cleanup checklist before Phase 2

---

## Removed

| Path | Reason |
|---|---|
| `data/images/smoke_hodeb.jpg` | Phase 0 smoke leftover (should-fix #1) |
| `data/meta/phase0_validation_probe.json` | Unused stub (`{"note": "validation discovery probe"}`); superseded by smoke report + inventory |
| `smoke_api.py` | Duplicate full HTTP stack; **deleted** (preferred). Replaced by `rijks_api.py` + `acquire.py` (D23 resolved in favor of delete) |

**Kept:** `data/meta/phase0_smoke_report.json` (Phase 0 provenance; not moved).

## Patched

| Path | Change |
|---|---|
| `config.py` | Storage comment → D22 locked SQLite (not “provisional”) |
| `acquire.py` `assign_split` | Anonymous probe FPs → `split_reason=anonymous` (was `other_artist`) |
| `rijks_api.py` docstring | Notes Phase 0 smoke removed in T019 |
| `data/cohortscope.sqlite` | Cheap UPDATE: SK-A-3014, SK-A-3035 `split_reason` → `anonymous` (no re-harvest) |
| `results/inventory.*` | Regenerated via `python acquire.py --inventory` |

## Not touched (intentional)

- Production `data/images/SK-*.jpg` / `SK-C-*.jpg`
- `data/cohortscope.sqlite` schema / splits (counts unchanged)
- Design/review memos under `results/`
- `docs/**` except `docs/tasks.md` (T019 → done)
- No Phase 2 code; no re-download

## Counts after cleanup (unchanged)

cohort=23 · validation=1 · ambiguous=1 · excluded=5 · total=30 · missing images=0

## Hand-off

Phase 1 cleanup complete. Orchestrator may open Phase 2 design gate (CV T020). Do not start Phase 2 implementation without human confirm.
