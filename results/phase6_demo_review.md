# Phase 6 demo review (T082)

**Reviewer:** Code Reviewer  
**Date:** 2026-08-08  
**Task:** T082 — Quick demo viewer review (D31)  
**Scope:** `demo_app.py`, `README.md` "## Demo viewer (optional)", `requirements.txt`

---

## Summary

**Verdict: PASS**

The demo viewer is a clean read-only Gradio UI that correctly:
- States O04 = `weak` and explicitly disclaims product status
- Hard-codes cohort reference values from `validation_report.md` (median −0.116810, p95 2.106898) without recomputation
- Handles SK-A-4096 (ambiguous) correctly per D21 (excluded from O04)
- Loads only precomputed `scores_v1.csv` + local JPEGs
- Does not import or call `score.py`, `embed.py`, or `acquire.py`
- Launches with `share=False` by default (no FastAPI scope creep)

No must-fix issues. Two minor should-fix notes below for UX clarity.

---

## Must-fix checklist (all clear)

| Risk | Status | Evidence |
|---|---|---|
| Claims method works / soft-pass | ✓ Clear | Line 27 banner: "O04 = weak ... Not a validated product"; line 104: "O04 = \`weak\` (pre-registered rule; not retuned)" |
| Imports/calls `score.py` / `embed.py` / `acquire.py` | ✓ Clear | Only stdlib/gradio/pandas/matplotlib/pathlib imports; loads CSV only (line 41) |
| Recomputes or retunes scores | ✓ Clear | Line 21–22 hard-codes median/p95 from `validation_report.md`; no scoring logic in app |
| Wrong O04 numbers vs validation_report | ✓ Clear | Line 21: `-0.116810` (correct); line 22: `2.106898` (correct); both match `validation_report.md` lines 29+31 |
| Promotes SK-A-4096 into O04 | ✓ Clear | Line 31–35: explicit banner stating ambiguous excluded from O04 per D21; line 120: banner swap logic |
| `share=True` by default or FastAPI | ✓ Clear | Line 194: `app.launch(share=False)`; no FastAPI imports or routes |

---

## Should-fix (UX clarity)

### 1. README demo section: reinforce tables-only science

**File:** `README.md` line 88–99  
**Current:** States "Does **not** recompute scores or claim the method works (O04 = \`weak\`)."  
**Suggest:** Add explicit sentence after line 90: "_Purpose: presentation aid for the human demo video (T072). The science deliverable remains `results/scores/scores_v1.csv` and `results/validation_report.md` (tables/CSV)._"  
**Rationale:** Line 7 already says science is tables/CSV, but repeating in the demo section reinforces D31 / T054 scope lock for future readers.

**Patch:**
```markdown
## Demo viewer (optional)

Read-only Gradio UI over `results/scores/scores_v1.csv` + `data/images/`. Does **not** recompute scores or claim the method works (O04 = `weak`).

_Purpose: presentation aid for the human demo video (T072). The science deliverable remains `results/scores/scores_v1.csv` and `results/validation_report.md` (tables/CSV)._

```bash
mamba activate CohortScope
python -m pip install -r requirements.txt   # includes gradio
python demo_app.py                          # local; share=False
```

Opens a local Gradio page: rank table, work detail (image + z_A/z_B + drivers), and a Validation spotlight for SK-A-3934.
```

---

### 2. demo_app.py docstring: add T072 video context

**File:** `demo_app.py` line 1–6  
**Current:** States "for the human demo video" but doesn't clarify that T072 video is the only intended use.  
**Suggest:** Expand line 3 docstring:
```python
"""
CohortScope demo viewer (D31 / T080) — read-only Gradio UI for the human demo video (T072).

Loads precomputed scores + local JPEGs only. Does not import score/embed/acquire
or recompute anything. Not a product claim: O04 = weak on SK-A-3934.
Created solely as a presentation aid for the datathon video submission.
"""
```
**Rationale:** Future maintainers should understand this was built for a specific datathon video requirement, not as a deployable product feature.

---

## Detailed findings

### File: `demo_app.py`

**Lines 21–22 (hard-coded reference values):**
```python
COHORT_MEDIAN_COMBINED = -0.116810
COHORT_P95_COMBINED = 2.106898
```
✓ Correct vs `results/validation_report.md` (lines 29+31). Comment on line 20 labels these as "from results/validation_report.md ... not recomputed" — excellent honesty.

**Lines 23–24 (validation + ambiguous IDs):**
```python
VALIDATION_ID = "SK-A-3934"
AMBIGUOUS_ID = "SK-A-4096"
```
✓ Correct per D21 / `validation_report.md`.

**Lines 26–30 (default banner):**
```python
BANNER_DEFAULT = (
    "**Demo viewer — O04 = weak on SK-A-3934. Not a validated product.**\n\n"
    "Read-only view of `scores_v1.csv` + `data/images/`. "
    "Scores are not recomputed; science deliverable remains tables/CSV."
)
```
✓ Explicitly disclaims product status and states O04 = `weak`. No "works" or "soft pass" language.

**Lines 31–35 (ambiguous banner):**
```python
BANNER_AMBIGUOUS = (
    "**ambiguous — excluded from O04 (D21)**\n\n"
    f"`{AMBIGUOUS_ID}` is scored exploratorily only. "
    "It never fits normals and never counts toward O04 / T043."
)
```
✓ Correctly implements D21 exclusion for SK-A-4096. Does not claim ambiguous validates the method.

**Lines 96–114 (validation spotlight logic):**
```python
def _validation_spotlight_md(row) -> str:
    clears_median = row.combined >= COHORT_MEDIAN_COMBINED
    clears_p95 = row.combined >= COHORT_P95_COMBINED
    return "\n".join([
        "### Validation spotlight — SK-A-3934",
        ...
        "- **O04 = `weak`** (pre-registered rule; not retuned)",
        ...
        f"- cohort median combined = `{COHORT_MEDIAN_COMBINED}`",
        f"- cohort p95 combined (O04 bar) = `{COHORT_P95_COMBINED}`",
        ...
        "**Explicit:** clears median, does **NOT** clear p95 → **weak**",
    ])
```
✓ Correct O04 logic: SK-A-3934 combined = 0.282608 (from CSV line 11) clears median −0.116810 but not p95 2.106898 → `weak` per D30 rule. Line 104 explicitly states rule was not retuned.

**Line 194 (launch call):**
```python
app.launch(share=False)
```
✓ No `share=True` by default; respects D31 scope (local-only demo for video).

**No scoring imports:**
```python
from pathlib import Path
import gradio as gr
import matplotlib.pyplot as plt
import pandas as pd
```
✓ Only stdlib + gradio/plotting/dataframe libraries. No `score`, `embed`, `acquire`, or `features` imports.

**Line 41 (score loading):**
```python
df = pd.read_csv(SCORES_CSV)
```
✓ Loads precomputed `scores_v1.csv`; does not invoke `score.py` or recompute z-scores.

---

### File: `README.md` — "## Demo viewer (optional)" (lines 88–99)

**Line 90:**
```markdown
Read-only Gradio UI over `results/scores/scores_v1.csv` + `data/images/`. Does **not** recompute scores or claim the method works (O04 = `weak`).
```
✓ Clearly states read-only + weak outcome. Does not claim "works" or "soft pass."

**Lines 92–96 (launch instructions):**
```bash
mamba activate CohortScope
python -m pip install -r requirements.txt   # includes gradio
python demo_app.py                          # local; share=False
```
✓ Correct runbook; comment confirms `share=False`.

**Line 98:**
```markdown
Opens a local Gradio page: rank table, work detail (image + z_A/z_B + drivers), and a Validation spotlight for SK-A-3934.
```
✓ Describes UI features without claiming validation success. SK-A-3934 spotlight is appropriate (D30 O04 target).

**Line 7 (repo status banner):**
```markdown
**Status:** Phases 0–5 done. Validation **O04 = `weak`** (N=1; see [`results/validation_report.md`](results/validation_report.md)). Science deliverable is **tables/CSV**; an optional read-only Gradio **demo viewer** exists for the human demo video (D31) — not a product claim.
```
✓ Top-level README already states science is tables/CSV and demo is optional + not a product. Should-fix #1 above is to reinforce this in the demo section itself for clarity.

---

### File: `requirements.txt` (line 14)

```
gradio>=4.0.0
```
✓ Present. Gradio introduced for D31 / T080 demo viewer only, as expected.

---

## Scope adherence (D31 / T054)

| Decision | Requirement | Status |
|---|---|---|
| D31 | Optional read-only Gradio demo viewer for T072 | ✓ Implemented as specified |
| D31 | Presentation aid only — not a product claim | ✓ Explicit disclaimers in banner + README |
| D31 | Does not reopen T050 or change O04 | ✓ No scoring logic; O04 = `weak` unchanged |
| T054 | Science deliverable remains CSV/tables | ✓ README line 7 + demo banner state this |
| D08 | No FastAPI | ✓ No Flask/FastAPI imports or routes |

---

## Leakage / retuning risks (all clear)

| Risk | Evidence |
|---|---|
| Validation-driven retuning | Hard-coded median/p95 match `validation_report.md`; no parameter fitting in app |
| Score recomputation | No imports of `score.py` / `embed.py` / `acquire.py`; loads CSV only |
| Ambiguous leakage into O04 | Lines 31–35 + 120: SK-A-4096 banner explicitly states excluded per D21 |

---

## Reproducibility check

**Launch smoke test (from T082 notes):**
- Expected: 25 dropdown choices, SK-A-3934 as default selection, image path resolves.
- Evidence: `demo_app.py` line 51 builds 25 labels from `scores_v1.csv`; line 52–55 sets default to SK-A-3934; line 58–60 resolves `data/images/{object_number}.jpg`.
- ✓ Runbook in README lines 92–96 is complete.

---

## Recommendations

**Must-fix:** None.

**Should-fix:**
1. README demo section: add explicit "purpose: T072 video; science remains tables" sentence (see patch above).
2. `demo_app.py` docstring: expand line 3 to clarify T072 video context (see patch above).

**Nice-to-have:**
- Future: if the repo gains non-datathon users, consider moving `demo_app.py` to `extras/` or `demo/` to signal it's not part of the core pipeline.

---

## Verdict

**PASS**

The demo viewer adheres strictly to D31 scope:
- Read-only visualization of precomputed artifacts
- Honest about O04 = `weak` outcome
- No scoring logic, imports, or retuning
- No FastAPI / `share=True` scope creep
- Correct handling of ambiguous SK-A-4096 per D21

The two should-fix items are documentation clarity improvements, not correctness issues. The code and README are safe to publish and use for the T072 human demo video.

**Next steps:**
- Apply should-fix patches if desired (optional; not blockers).
- T083: cleanup pass (D24) — verify no leftover dev files before git push (D28).
- T072: human records demo video using this viewer + validation `weak` commentary.
