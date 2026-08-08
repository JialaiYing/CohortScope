# Phase 4 cleanup log (T046)

**Date:** 2026-08-08 · **Role:** stats (+ orchestrator push separately)  
**Trigger:** T044 **PASS** should-fix #1–3 (`results/phase4_review.md`)  
**Constraint:** Do **not** change scores, fusion, or O04 outcome (`weak`).

---

## Done

| # | Should-fix | Action |
|---|---|---|
| 1 | Design memo still “DRAFT” | `results/phase4_scoring_design.md` → **LOCKED (D30)**; §8 lock record |
| 2 | Absolute Windows paths in artifacts | `score.py` writes **repo-relative** POSIX paths via `repo_rel()`; regenerated `fit_manifest.json` + `validation_report.md` |
| 3 | Optional `driver_A` | Constant column `embed_cosine_to_centroid` added to CSV + report; numeric scores unchanged |

## Verified unchanged

| Check | Value |
|---|---|
| O04 | **`weak`** (SK-A-3934) |
| Val `combined` | `0.28260805` |
| Rank | 10 / 25 |
| Fit rules | Cohort-only + LOO; O02 `z_A+z_B`; O04 p95/median tiers |

## Regenerated (metadata / schema only)

- `results/scores/scores_v1.csv` — added `driver_A`; same numeric columns  
- `results/scores/fit_manifest.json` — relative sources  
- `results/validation_report.md` — relative artifact paths + `driver_A` rows  

## Not done here

- Git commit / push (D28) — orchestrator / human  
- Nice-to-have unit tests from T044  
- T050 method changes — **not opened**

## Keep

- `score.py`, `results/scores/*`, `results/validation_report.md`, `results/phase4_scoring_design.md`, `results/phase4_review.md`
