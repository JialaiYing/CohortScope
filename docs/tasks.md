# Tasks — Cohortscope

Shared board. **Update status here when you finish or unblock work.**  
Statuses: `todo` | `in_progress` | `blocked` | `done` | `cancelled`

Last updated: 2026-08-05 (T019 cleanup done; Phase 2 design gate may open)

---

## How to use (all agents)

1. Read `docs/decisions.md` and this file at session start.
2. Only pick tasks tagged with your role (or marked `any`).
3. Set status to `in_progress` before coding; `done` when deliverable exists on disk.
4. If blocked, set `blocked` and name the blocker in Notes.
5. Do not expand scope into another role’s column — hand off via a new task instead.

---

## Current phase

**Phase 0 — DONE**  
**Phase 1 — DONE** (T018 PASS + T019 cleanup) → **Phase 2 ON HOLD** (human hold after GitHub publish)  
**Datathon (D25):** https://github.com/JialaiYing/CohortScope.git — README dataset link stubbed; report/video later

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
| T020 | Design normalize pipeline (scale, color) | cv | todo | Confirm before code |
| T021 | Implement preprocess → cached tensors/images | cv | todo | |
| T022 | QC: before/after samples + failure log | cv | todo | |
| T023 | Confirm preprocess does not erase brushstroke signal | features | todo | Review CV design |

### Phase 3 — Feature extraction (Days 5–7)

| ID | Task | Role | Status | Notes |
|---|---|---|---|---|
| T030 | ResNet50 embedding extractor (no finetune) | cv | todo | D13 |
| T031 | Shortlist interpretable features (confirm) | features | todo | O03 — design notes OK in parallel; **no code until Phase 3 gate** |
| T032 | Implement texture / brushstroke / palette stats | features | todo | Hand-built only |
| T033 | Feature matrix export + schema doc | features | todo | Align IDs with data layer |
| T034 | Literature notes on wavelet/brushstroke auth | literature | todo | Honest prior art |

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
| Human Phase 2 design confirm (T020) | T021+ implement | cv + human |

## Parallel work allowed now

- **CV:** Phase 2 preprocess design (T020) — confirm with human before code  
- Feature Engineering may review preprocess design (T023) once drafted  
- Data Engineer idle on Phase 1; no Phase 2 acquisition work unless CV asks  
- Do **not** implement Phase 2 until human opens that gate  
- Do **not** start Phase 2 code until T019 complete  

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
