# Phase 5 review (Wave B / T053 final gate)

**Role:** Code Reviewer  
**Date:** 2026-08-08  
**Artifacts reviewed:** `README.md` (T070), `results/datathon_report.md` (T071 / T051+T052)  
**Cross-checks:** `docs/tasks.md`, `docs/decisions.md`, `results/scores/scores_v1.csv`, `results/validation_report.md`, `results/phase4_review.md`

---

## Verdict (orchestrator)

**PASS**

README + datathon report stay honest on O04=`weak`, match score artifacts, keep acquire→score reproduce + dataset links, do not promote SK-A-4096 into O04, and do not contradict Phase 4 leakage/no-retune findings. Scope lock holds (T050 cancelled; T054 tables-only).

No **must-fix**. Light **should-fix** below for T055 polish only — not blocking.

---

## 1. Scope lock

| Lock | Status |
|---|---|
| T050 cancelled (no method retune) | **Holds** — `docs/tasks.md` cancelled; report §6 explicitly does not open T050; D25 deferred list matches |
| T054 tables-only | **Holds** — README status + report §2 / §9; no Gradio/API language as a deliverable |
| O04 still `weak` | **Holds** — README, report headline/§4/§10, `validation_report.md` |

---

## 2. O04 numbers vs `scores_v1.csv` / `validation_report.md`

| Quantity | Report §4 | validation_report | scores_v1 (SK-A-3934) | Match |
|---|---|---|---|---|
| `combined` | 0.282608 | 0.282608 | 0.28260805 | **OK** |
| `z_A` / `z_B` | 0.022581 / 0.260027 | same | 0.02258057 / 0.26002749 | **OK** |
| Rank | 10 | 10 | 10 | **OK** |
| Cohort median / p95 | −0.116810 / 2.106898 | same | (implied by O04) | **OK** |
| Outcome | `weak` | `weak` | — | **OK** |
| SK-A-4096 | Rank 2; **not** O04 | Rank 2; non-counting | ambiguous, rank 2 | **OK** |

Ranked summary table uses display rounding (e.g. 0.283) — acceptable for narrative; canonical O04 table uses full precision.

---

## 3. Must-fix checklist

| Criterion | Finding |
|---|---|
| False “works” / soft-pass | **None** — headline and §5/§10 forbid it; “engineering stands” ≠ scientific pass |
| Wrong O04 numbers/ranks | **None** — see §2 |
| Missing dataset link / broken acquire→score path | **None** — README Dataset (Rijksmuseum docs + `acquire.py`) + full pipeline order through `score.py`; `requirements.txt` present |
| Promoting SK-A-4096 into O04 | **None** — labeled ambiguous / exploratory / excluded |
| Leakage / retuning contradicts Phase 4 | **None** — cohort-only + LOO + “not retuned”; cites `phase4_review.md` PASS |

---

## 4. README (T070)

| Check | Result |
|---|---|
| Dataset link | Rijksmuseum Search docs + open-data attribution |
| Reproduce path | `acquire → preprocess → embed → features → score` |
| O04 honesty | Status line: `weak` + link to `validation_report.md` |
| Tables-only | Explicit; no Gradio/UI this cycle |
| Report pointer | Links `datathon_report.md` |

---

## 5. Datathon report (T071)

| Section | Gate |
|---|---|
| Headline / closing | Weak; method not claimed to work |
| Method / fit rules | Aligns with D30 + Phase 4 review |
| Sustainability §8 | Design-level, **not executed** — adequate (not thin) |
| Prior art §7 | Contingent novelty; gate did not fire |
| Deliverables map | Points at scores, validation_report, phase4_review |

---

## 6. Findings ranked

### Must-fix

*(none)*

### Should-fix (T055 — non-blocking)

1. **`README.md` Reports table** — add a row for [`results/phase4_review.md`](results/phase4_review.md) (leakage/scope PASS) so judges see the gate next to the validation report.  
2. **`results/datathon_report.md` §4 ranked summary** — optionally note that rank-table `combined` values are rounded; point readers to `scores_v1.csv` for exact floats (O04 table already exact).

### Nice-to-have

1. README Setup: one line on creating the `CohortScope` mamba env if missing (assumes env exists today).

---

## 7. Recommendation

| Gate | Call |
|---|---|
| Phase 5 Wave B (README + report) | **PASS** |
| Blocking defects | **None** |
| Next | **T055** cleanup + git push (D24/D28); **T072** demo video remains human |

Do **not** open T050. Do **not** change `score.py`.
