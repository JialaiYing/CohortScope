# Tasks — Cohortscope

Shared board. **Update status here when you finish or unblock work.**  
Statuses: `todo` | `in_progress` | `blocked` | `done` | `cancelled`

Last updated: 2026-08-06 (Phase 2 DONE + GitHub push; Phase 3 design gate OPEN)

---

## How to use (all agents)

1. Read `docs/decisions.md` and this file at session start.
2. Only pick tasks tagged with your role (or marked `any`).
3. Set status to `in_progress` before coding; `done` when deliverable exists on disk.
4. If blocked, set `blocked` and name the blocker in Notes.
5. Do not expand scope into another role’s column — hand off via a new task instead.

---

## Current phase

**Phase 0–2 — DONE** (on GitHub; D28 push-after-phase)  
**Phase 3 — Feature extraction: ACTIVE — Wave A design gate** (no extract code until human lock)  
**Datathon (D25):** https://github.com/JialaiYing/CohortScope.git

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
| T070 | Root README: run instructions + dataset link (Rijksmuseum / acquire reproduce) | data + literature | todo | Datathon required |
| T071 | Datathon report (method, decisions, results, evaluation) | literature | todo | Feed from Stats T045 |
| T072 | Human: publish GitHub + record demo video | human | todo | Agents do not produce the video |

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
| T030 | Design ResNet50 embedding extract I/O | cv | todo | **Wave A** — Branch C inputs; no forward until lock |
| T031 | Shortlist interpretable features (O03 confirm) | features | todo | **Wave A** — Branch H only |
| T034 | Literature notes on wavelet/brushstroke auth | literature | todo | **Wave A parallel** |
| T035 | Stats note: embedding/feature matrix contract for Phase 4 | stats | todo | **Wave A parallel** — join keys, no premature scoring |
| T032 | Implement texture / brushstroke / palette stats | features | todo | **Wave B** after human lock |
| T033 | Feature matrix export + schema doc | features | todo | Wave B |
| T036 | Implement ResNet50 embedding extractor | cv | todo | Wave B; was T030 implement |
| T037 | Review Phase 3 artifacts | review | todo | Wave C |
| T038 | Phase 3 cleanup + git push (D24/D28) | any | todo | After T037 |

### Phase 4 — Scoring + validation (Days 8–9)

| ID | Task | Role | Status | Notes |
|---|---|---|---|---|
| T040 | Design decomposable outlier score (confirm) | stats | todo | Resolve O02, O04 |
| T041 | Fit cohort normals on **main cohort only** | stats | todo | Never fit on validation |
| T042 | Score all works; emit ranked table + per-signal drivers | stats | todo | |
| T043 | Validate vs held-out circle/workshop set | stats | todo | Provisional until this passes |
| T044 | Critique stats method + leakage risks | review | todo | |
| T045 | Draft results narrative (pass/fail honesty) | literature | todo | |

### Phase 5 — Iterate + write-up (Days 10–11)

| ID | Task | Role | Status | Notes |
|---|---|---|---|---|
| T050 | Fix failures from validation | stats+cv+features | todo | Scope-tight fixes only |
| T051 | Methodology + limits write-up | literature | todo | |
| T052 | Sustainability claim (second artist without code change) | literature | todo | Design-level, may not execute |
| T053 | Final code review + scope check | review | todo | |
| T054 | Decide Gradio/API or stay tables-only | any | todo | Only if method validated |

### Phase 6 — Buffer (Days 12–13)

| ID | Task | Role | Status | Notes |
|---|---|---|---|---|
| T060 | Buffer — do not schedule new features here | any | cancelled | D17 |

---

## Active blockers

| Blocker | Blocks | Owner |
|---|---|---|
| Phase 3 Wave A incomplete (T030/T031/T034/T035 + human lock) | T032/T036 implement | cv + features + literature + stats + human |

## Parallel work allowed now

- **CV T030**, **Features T031**, **Literature T034**, **Stats T035** — design only, in parallel  
- No embedding/feature extraction code until human locks O03 + embed I/O  


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
