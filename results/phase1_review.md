# Phase 1 review (Wave C / T018)

**Role:** Code Reviewer  
**Date:** 2026-08-05  
**Artifacts reviewed:** `acquire.py`, `rijks_api.py`, `smoke_api.py`, `config.py`, `data/cohortscope.sqlite`, `data/images/*.jpg`, `results/inventory.*`, T017/T010 memos, D19–D24  

---

## Verdict (orchestrator)

**PASS with patches**

Phase 1 acquisition meets D19–D23, T017 §1.2 split integrity, and L1–L8 *structural* leakage gates for this phase. Counts match the claimed Wave B summary (cohort=23, validation=1, ambiguous=1, excluded=5, 0 missing images, ~11.3 MB). Tiny validation N is documented honestly.

No **must-fix** split/leakage defects found. Listed **should-fix** items are small and fit **T019 cleanup** (or a short Data Engineer follow-up) before Phase 2 — they do not reopen Wave B harvest.

---

## 1. Split integrity (T017 §1.2 / D19–D21)

Spot-checked DB rows + on-disk JPEGs against priority rules (first match wins).

| object_number | Expected | Observed `split` / `split_reason` / family | Image | Result |
|---|---|---|---|---|
| SK-A-3934 | `validation` (circle/omgeving KEEP) | `validation` / `circle_keep` / `circle_workshop` | present (276 KB) | **OK** |
| SK-A-4096 | `ambiguous` (O05 / D21) | `ambiguous` / `attributed_o05` / `attributed` | present (674 KB) | **OK** |
| SK-A-1935 | `cohort` (firm, main search) | `cohort` / `firm_main_search` / `firm` | present | **OK** |
| SK-A-3138 | `cohort` via main search (not probe FP) | `cohort` / `firm_main_search` / `firm` | present | **OK** |
| SK-A-3982 | same | `cohort` / `firm_main_search` / `firm` | present | **OK** |
| SK-A-1627 | `excluded` (Lievens) | `excluded` / `other_artist` / `other` | present | **OK** |
| SK-C-371 | `excluded` (Flinck) | `excluded` / `other_artist` / `other` | present | **OK** |
| SK-A-3014 | `excluded` (anonymous) | `excluded` / `other_artist` / `other` | present | **OK** |

**Aggregate checks (SQLite):**

- Counts: cohort 23 · validation 1 · ambiguous 1 · excluded 5 · total 30  
- Unique `object_uri` / `object_number`: 30 / 30 (L7)  
- All cohort rows: `creator_label_family=firm` and `source_query_type=creator`  
- No hedge phrases (`circle` / `workshop` / `attributed` / …) in any cohort `creators_json` (L3)  
- All `iiif_max_edge=1500` (D12)  
- 30 production images ↔ 30 DB rows with `image_path`; 0 orphans; 1 leftover `smoke_*.jpg` (Phase 0)

**Rule notes (correct behavior):**

- Main creator search runs first; SK-A-3138 / SK-A-3982 stay `cohort` even though they were smoke examples of *probe-only* firm false positives — consistent with §1.2 (probe-only firm → excluded; main-search firm → cohort).  
- SK-A-4096 keeps firm-looking strings *plus* attributed hedges → family `attributed` → `ambiguous` (D21), not cohort.  
- Circle beats attributed in `classify_creator_family` / `assign_split` (no both-present row in this harvest).

Tiny-N honesty: inventory.md/json call out validation N=1 and forbid AUC-style claims — **do not weaken**.

---

## 2. Leakage checklist L1–L8 (structural)

Phase 4 scoring does not exist yet. Assessment is whether acquisition/schema make leakage hard to commit by accident.

| # | Rule | Phase 1 status | Notes |
|---|---|---|---|
| L1 | Fit normals on `split=cohort` only | **Structural OK** | `split` CHECK + inventory; no fit code yet. Downstream must filter explicitly (convention until Stats helpers). |
| L2 | validation/ambiguous downloadable & scored, never in fit | **OK** | Correct splits stored; SK-A-3934 / SK-A-4096 not cohort. |
| L3 | No hedge Rembrandt-search hits in cohort | **OK** | Spot-check + full cohort hedge scan clean. |
| L4 | Probe FPs → excluded | **OK** | 5× `other_artist` (Lievens, Flinck, anonymous). |
| L5 | No threshold tuning on val/ambiguous | **N/A → defer** | No scoring; re-check at T044. |
| L6 | No val-driven preprocess/features/backbone | **OK** | No Phase 2+ code; D13 locked; scope clean. |
| L7 | One canonical ID; no double-count | **OK** | Unique PK + `object_number`; harvest dedupes URI/number. |
| L8 | Inventory lists split + raw creators | **OK** | `results/inventory.json` + `.md` complete before scoring. |

**Residual risk (not a Phase 1 fail):** nothing in the DB *enforces* that a future `fit_*` rejects non-cohort rows. Recommend Stats (Phase 4) hard-fail if `split != 'cohort'` is passed into fit paths.

---

## 3. Schema vs SQLite / implementation

T010 §1.1 DDL vs live `works` table: **match**.

| Column | Design | Live | Notes |
|---|---|---|---|
| `object_uri` PK | yes | yes | |
| `object_number` UNIQUE | yes | yes (autoindex) | |
| `creators_json` | yes | yes | JSON array of raw strings |
| `creator_label_family` | yes | yes | `firm` \| `circle_workshop` \| `attributed` \| `other` \| `missing` |
| `split` CHECK 4-way | yes | yes | D19 |
| `split_reason` | yes | yes | Unified keep/exclude reason (T017’s dual reason fields collapsed — acceptable) |
| `source_query_type` / `source_query` | yes | yes | |
| `iiif_*` / `image_*` / `filters_json` / `acquired_at` | yes | yes | |
| Index on `split` | yes | `idx_works_split` | |

**Minor naming drift (documented, not defects):** Stats T017 §5 used `uri` / `creator_label_normalized` / separate keep|exclude reasons; T010 + code use `object_uri` / `creator_label_family` / `split_reason`. Implementation follows the locked acquisition design.

**Behavioral note:** excluded probe hits still receive IIIF downloads. Not leakage; slight disk waste (~excluded share of 11.3 MB). Optional future skip — not required for Phase 1 exit.

---

## 4. Module boundaries (D23)

| Module | Expectation | Finding |
|---|---|---|
| `rijks_api.py` | Shared HTTP / resolve / IIIF | Clear, no acquisition/split logic |
| `acquire.py` | Harvest, split, SQLite, inventory CLI | Owns Wave B; CLI matches design (`--dry-run`, `--inventory`) |
| `smoke_api.py` | Phase 0 smoke only | Still smoke-only (filter variants, sample download to `smoke_*.jpg`, report). **Not** the downloader. Duplicate HTTP helpers vs `rijks_api` — acceptable for Phase 0 fossil; candidate for T019 thin/delete decision |
| `config.py` | Locks | FILTERS / queries / IIIF / DB_PATH present |

No Gradio, FastAPI, preprocess, embeddings, or DINOv2 in Phase 1 code paths. Scope creep: **none**.

---

## 5. Reproducibility

| Capability | Status |
|---|---|
| Full harvest | `python acquire.py` (rewrites SQLite authoritatively) |
| Dry-run splits | `python acquire.py --dry-run` (no DB/image/inventory overwrite) |
| Inventory regen | `python acquire.py --inventory` from existing DB |
| Filters snapshot | Per-row `filters_json` + inventory top-level `filters` |
| Disk budget | ~11.3 MB ≪ 5 GB |

**Caveat:** full re-harvest depends on live Rijksmuseum API stability; local DB + images are the reproducible corpus for Phase 2+.

---

## 6. Findings ranked

### Must-fix

*(none)*

### Should-fix (T019 / Data Engineer — before Phase 2)

1. **Smoke leftover image** — `data/images/smoke_*.jpg` still present; inventory correctly ignores it, but D24 cleanup should remove Phase 0 smoke binaries (and decide whether `smoke_api.py` stays as historical smoke or is thinned to call `rijks_api`).  
2. **Stale `config.py` comment** — still says storage is “provisional”; D22 locked SQLite.  
3. **Anonymous exclude reason** — anonymous rows use `split_reason=other_artist`; functionally correct (L4) but audit-noisy. Prefer `anonymous` (or similar) on next harvest if cheap.  
4. **Orchestrator doc drift** — `docs/roadmap-phase-plan.md` §9 still says Phase 1 “design gate open”; refresh status after T018/T019 (not a code defect).

### Nice-to-have

1. Skip IIIF download once split is known-excluded (save a few MB; needs assign-before-download reorder).  
2. Mutual exclusion of `--dry-run` and `--inventory` in argparse.  
3. Phase 4: shared `load_cohort_only()` that raises if non-cohort rows slip in (hardens L1).

---

## 7. Recommendation

| Gate | Call |
|---|---|
| Phase 1 Wave B quality | **PASS** |
| Blocking defects | **None** |
| Overall for orchestrator | **PASS with patches** → run **T019** (D24 cleanup + should-fix #1–2 at minimum), then open Phase 2 design gate |

Do **not** start Phase 2 implementation until T019 completes. Do **not** inflate validation N or fold SK-A-4096 into T043.
