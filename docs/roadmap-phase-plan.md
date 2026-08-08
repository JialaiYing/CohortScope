# Cohortscope — Detailed Roadmap & Phase Plan

Companion to `docs/cohortscope-product-vision-roadmap.md` (product vision stays authoritative for *what*).  
This file is authoritative for *when*, *who*, and *done-when*.

Last updated: 2026-08-05  
Calendar anchor: **Day 1 = 2026-08-04** (D18). Buffer days are not schedulable (D17).

---

## 1. Outcome (one sentence)

A local pipeline that ranks Rembrandt-attributed Rijksmuseum paintings by decomposable anomaly (CNN embedding distance + interpretable texture/color stats), and only counts as successful if held-out circle/workshop/attributed works look unusually far from the cohort normal.

---

## 2. Calendar map

| Project day | Calendar | Phase | Primary owners |
|---|---|---|---|
| 0 (pre) | 2026-08-04 evening | Prerequisites | data + coordinator |
| 1–2 | 2026-08-04 → 08-05 | Data acquisition | data (+ literature parallel) |
| 3–4 | 2026-08-06 → 08-07 | Preprocessing | cv (+ features review) |
| 5–7 | 2026-08-08 → 08-10 | Feature extraction | cv + features (+ literature) |
| 8–9 | 2026-08-11 → 08-12 | Scoring + validation | stats (+ review) |
| 10–11 | 2026-08-13 → 08-14 | Iterate + write-up | literature + all (fixes) |
| 12–13 | 2026-08-15 → 08-16 | Buffer | — reserved for slip only |

Phase 0 consumed part of Days 1–2. Acquisition must still finish inside the Days 1–2 window or explicitly slip with human approval (do not silently eat Days 3–4).

---

## 3. Multi-agent operating model

One Project Manager (default chat) plus six specialists. Narrow scopes. Shared state in `docs/tasks.md` + `docs/decisions.md`. Launch specialists with `docs/launch/*.md`.

| Agent | Owns | Does not own |
|---|---|---|
| Project Manager | Status, routing, phase gates, shared-doc coherence | Deep parallel implementation streams |
| Data Engineer | API, download, metadata, splits, local store | Models, scores, write-up prose |
| Computer Vision | Image normalize, ResNet50 embeddings | Hand-built features, outlier math |
| Feature Engineering | Texture / brushstroke / palette stats | Network training, API harvest |
| Statistics | Cohort normals, decomposable scores, validation metrics | Data download, backbone choice |
| Literature | Prior art, novelty framing, methodology narrative | Production code paths |
| Code Reviewer | Leakage, scope creep, interface consistency | Implementing features unless asked to patch |

### Parallelism rules

- **Safe parallel:** Literature anytime; Reviewer after a phase deliverable; Features design while CV implements preprocess; Stats design while features extract.
- **Hard sequence:** No scoring before features exist. No claiming “working” before validation task T043.
- **Human gate:** Start of each phase = confirm design in chat before implementation code (briefing rule).

### Shared files every agent reads

1. `docs/decisions.md` — locked choices  
2. `docs/tasks.md` — live board  
3. This file — phase contracts  
4. Own prompt under `docs/agents/`

---

## 4. Phase contracts

### Phase 0 — Prerequisites (DONE)

**Goal:** Runtime + API path verified; key decisions locked.  
**Deliverables:** `config.py`, `smoke_api.py`, CUDA PyTorch in `CohortScope`, Phase 0 report.  
**Exit criteria:** Search → resolve → IIIF image works; filters/backbone/image size in `docs/decisions.md`.

### Phase 1 — Data acquisition (Days 1–2)

**Goal:** Local, labeled image+metadata corpus with clean cohort / validation / ambiguous / excluded split.  
**Owners:** Data Engineer (lead); Literature + Statistics (Wave A design); Code Reviewer (Wave C).

**Design gate:** DONE 2026-08-05 — T016/T017/T010 approved; O05→`ambiguous`; Wave B unlocked (D19–D24).

**Work (Wave B):**
1. Paginate Search API with locked filters (D10)
2. Resolve Linked Art; follow Object → VisualItem → DigitalObject → IIIF
3. Download IIIF at 1500px long edge (D12)
4. Assign splits per D19–D21 / T017 §1.2
5. Persist SQLite `works` + images (D22–D23)
6. Inventory report in `results/`

**Exit criteria:**
- [ ] Every scored split (`cohort`/`validation`/`ambiguous`) has local image + metadata row when IIIF available
- [ ] Split column is explicit: `cohort` \| `validation` \| `ambiguous` \| `excluded` (D19)
- [ ] Counts documented; tiny validation N acknowledged in `results/inventory.*`
- [ ] Disk use &lt; 5 GB
- [ ] Code Reviewer T018 signed off
- [ ] **Cleanup pass (D24)** — remove Phase 1-obsolete files before Phase 2

**Risk:** Validation N≈1–3 → null result ambiguous. Mitigate by documenting expected N before scoring.

### Post-phase cleanup (D24) — every phase

After a phase meets exit criteria and Reviewer (or orchestrator) signs off, run a cleanup before the next phase starts:

1. Delete one-off / superseded scripts and smoke leftovers no longer needed
2. Remove duplicate or abandoned draft results (keep the canonical memo + final artifacts)
3. Ensure `docs/tasks.md` marks the phase done and points at surviving files only
4. Do **not** delete locked decisions, role docs, or the phase’s final deliverables (images, DB, inventory, signed design memos)

Orchestrator issues an explicit cleanup checklist per phase; Data/CV/etc. execute deletions only from that list.

### Phase 2 — Preprocessing (Days 3–4)

**Goal:** Reduce scan/lighting confounds without destroying texture signal.  
**Owners:** Computer Vision (lead); Feature Engineering (signal-preservation review).

**Design gate:** Ops list (resize policy, color space, clipping) + what we deliberately will *not* do (e.g. heavy denoising).

**Exit criteria:**
- [ ] Deterministic preprocess cache
- [ ] QC sheet (sample grid + failures)
- [ ] Features agent sign-off that brushstroke stats remain meaningful

### Phase 3 — Feature extraction (Days 5–7)

**Goal:** Two independent feature matrices aligned by object ID.  
**Owners:** CV (embeddings); Feature Engineering (interpretable); Literature (prior art notes).

**Design gate:** Feature shortlist (O03) — prefer few strong, named stats over a kitchen sink.

**Exit criteria:**
- [ ] Embedding matrix for all scored images (ResNet50, no finetune)
- [ ] Interpretable feature matrix with named columns
- [ ] Schema note: how to join on object ID
- [ ] Literature stub on wavelet/brushstroke authentication vs this project’s novelty

### Phase 4 — Scoring + validation (Days 8–9)

**Goal:** Ranked, decomposable scores; honest check on held-out set.  
**Owners:** Statistics (lead); Code Reviewer (leakage/scope); Literature (results draft).

**Design gate:** Combination rule (O02) + success bar (O04). Cohort normals fit on **cohort only**.

**Exit criteria:**
- [ ] Ranked table with per-signal contributions
- [ ] Validation summary (what fraction flagged, at what threshold)
- [ ] Explicit statement: pass / weak / fail — no sugarcoating
- [ ] Reviewer note on leakage and split integrity

**Definition of “working”:** Only after this phase’s validation check (briefing).

### Phase 5 — Iterate + write-up (Days 10–11)

**Goal:** Fix only what validation proved broken; ship **datathon submission pack** (D25) minus demo video.  
**Owners:** Literature (report); Data/any (README runbook + dataset link); Reviewer (final gate); Human (video, GitHub publish).

**Exit criteria:**
- [ ] Report: methodology, crucial decisions, results/analysis, evaluation honesty (tiny-N; pretrained not scratch-trained)
- [ ] Root `README.md`: setup, reproduce acquire → features → scores, **dataset link** (Rijksmuseum + reproduce via `acquire.py`; optional archived `data/` link)
- [ ] Ranked results reproducible from repo instructions
- [ ] UX/Gradio decision recorded (default: still deferred unless validation passed and time remains)
- [ ] Cleanup pass (D24)
- [ ] Human checklist: publish repo + record demo video (agents do not own video)

### Phase 6 — Buffer / demo aid (Days 12–13)

Slip for science. **Exception (D31):** optional read-only Gradio viewer for human demo video (T080) — no method changes.

---

## 5. Deliverable map (artifacts)

| Phase | Expected artifacts |
|---|---|
| 0 | `config.py`, Phase 0 smoke (may be removed at T019), `data/meta/phase0_*` |
| 1 | `rijks_api.py`, `acquire.py`, `data/cohortscope.sqlite`, `data/images/*`, `results/inventory.*`, design memos, `results/phase1_review.md` |
| 2 | preprocess module, cached preprocessed images/tensors, QC outputs |
| 3 | `embeddings.*`, `features.*`, feature dictionary |
| 4 | `results/scores.*`, validation report |
| 5 | `README.md` (dataset link), datathon **report**, final ranked list; human: GitHub + demo video |

Exact filenames can be set during each phase design gate; update `docs/tasks.md` when chosen.

---

## 6. Judging rubric → phase ownership

| Criterion | How we hit it | Phase |
|---|---|---|
| Innovation | Two-signal decomposable scoring on live open corpus | 3–4 |
| Problem Solving | Recover validation anomalies with stated reasons | 4 |
| Sustainability | Pipeline structured for second artist without rewrites | 1, 5 |
| UX & Design | Deferred; clean ranked table this cycle | 5 decision |
| Bonus / Exceptionality | Honest prior-art + clear novelty statement | 3, 5 (literature) |

---

## 7. Escalation & scope creep

Flag immediately (do not wait until Day 11):

- Adding museums/artists before Rembrandt validation works
- Training/finetuning a backbone
- Building Gradio/FastAPI before T043 passes
- Expanding interpretable features past the agreed shortlist
- Planning work into Days 12–13

Code Reviewer owns calling these out; any agent may raise them.

---

## 8. Human checkpoints (mandatory)

| When | Checkpoint |
|---|---|
| Start Phase 1 | Acquisition design + O05 |
| Start Phase 2 | Preprocess design |
| Start Phase 3 | Feature shortlist + embedding details |
| Start Phase 4 | Score fusion + success bar |
| Start Phase 5 | What to fix vs document as limitation |
| After T043 | Is method “working”? Gradio/API now or not |

---

## 9. Quick status snapshot

| Phase | Status |
|---|---|
| 0 Prerequisites | **done** |
| 2 Preprocessing | **DONE** (pushed; D28) |
| 3 Feature extraction | **ACTIVE** — design gate (Wave A) |
| 4 | not started |
| 5 Write-up / datathon pack (D25) | **DONE** (pushed; O04=weak; video = human T072) |
| 6 Buffer / demo aid | **DONE** — Gradio viewer pushed (D31); T072 video = human |
