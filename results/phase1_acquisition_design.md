# Phase 1 acquisition design (schema, split, modules)

**Task:** T010 · **Role:** data · **Date:** 2026-08-05  
**Status:** proposed — **Wave A only**; no bulk download until human unlocks Wave B  
**Aligns with:** `results/phase1_experimental_design.md` (T017), `results/prior_art_dataset_practices.md` (T016), `config.py`, `smoke_api.py`  
**Locked inputs:** D01, D10–D12, D14–D15, P01–P03

---

## Verdict (yes/no checklist for human)

| # | Proposal | Default |
|---|---|---|
| 1 | Split enum = **four** values: `cohort` \| `validation` \| `ambiguous` \| `excluded` (match Stats T017; extends roadmap’s 3-way) | **Yes** |
| 2 | O05 SK-A-4096 → `ambiguous` (score later; never fit; never T043) | **Yes** (Stats) — needs human lock |
| 3 | Storage = SQLite at `data/cohortscope.sqlite` (P01) | **Yes** |
| 4 | Flat modules: `rijks_api.py` + `acquire.py` (+ thin `inventory.py` or CLI flag) | **Yes** |
| 5 | IIIF long-edge 1500; English D10 filters; no `technique` search | Locked |

**Wave B (T011–T015) must not start until human confirms this memo + O05.**

---

## 1. Schema

### 1.1 Table `works` (SQLite)

Primary key: `object_uri` (Linked Art / Rijksmuseum id URL).  
Join key for CV/features/stats: `object_number` (e.g. `SK-A-3934`).

| Column | Type | Required | Notes |
|---|---|---|---|
| `object_uri` | TEXT PK | yes | Canonical id (`https://id.rijksmuseum.nl/...`) |
| `object_number` | TEXT UNIQUE | yes | Inventory number; filename stem |
| `title` | TEXT | nullable | From Linked Art Name |
| `creators_json` | TEXT | yes | JSON array of raw creator strings (audit) |
| `creator_label_family` | TEXT | yes | `firm` \| `circle_workshop` \| `attributed` \| `other` \| `missing` — which family fired (Stats §5) |
| `split` | TEXT | yes | `cohort` \| `validation` \| `ambiguous` \| `excluded` |
| `split_reason` | TEXT | yes | Short code, e.g. `firm_main_search`, `circle_keep`, `attributed_o05`, `other_artist`, `missing_image`, `probe_false_positive` |
| `source_query_type` | TEXT | yes | `creator` \| `description` |
| `source_query` | TEXT | yes | Exact query string (`Rembrandt van Rijn` or a D14 probe) |
| `iiif_id` | TEXT | nullable | micr.io identifier; null if unresolved |
| `iiif_max_edge` | INTEGER | yes | Always `1500` (D12) when downloaded |
| `image_path` | TEXT | nullable | Repo-relative, e.g. `data/images/SK-A-3934.jpg` |
| `image_bytes` | INTEGER | nullable | On-disk size after download |
| `filters_json` | TEXT | yes | Snapshot of D10 (+ creator/description) params used |
| `acquired_at` | TEXT | yes | ISO-8601 UTC |

**Indexes:** `split`, `object_number`.

**Not stored in v1 (avoid scope):** raw Linked Art JSON blobs, embeddings, scores, preprocess paths.

### 1.2 On-disk layout

```
data/
  cohortscope.sqlite          # works table
  images/{object_number}.jpg  # IIIF @ 1500 long edge
  meta/                       # optional run logs (JSON), not the source of truth
results/
  inventory.json              # machine-readable counts + row list
  inventory.md                # human-readable summary (tiny-N callout)
```

Image naming: `{object_number}.jpg` only (no smoke_ prefix in production). Smoke file `smoke_*.jpg` ignored by inventory.

### 1.3 Downstream contract

| Consumer | Filter |
|---|---|
| Stats fit normals | `split = 'cohort'` **only** |
| Stats score / rank | `split IN ('cohort','validation','ambiguous')` **and** `image_path IS NOT NULL` |
| T043 success fraction | `split = 'validation'` only |
| Inventory | all rows |

---

## 2. Split assignment algorithm

Matches Stats T017 §1.2. Run **after** resolve + creator extraction. Description probes are discovery only; probe text alone never assigns `cohort`.

### 2.1 Label families (case-insensitive substring on joined creator strings)

Reuse / refine `config.VALIDATION_CREATOR_HINTS`:

| Family | Match |
|---|---|
| **circle_workshop** | `circle of`, `workshop of`, `school of`, `omgeving van`, `atelier van`, `school van`, `follower`, `studio`, `navolger` (with Rembrandt context preferred; fail closed to `excluded` if Rembrandt absent and named other artist) |
| **attributed** | `attributed to`, `toegeschreven` (+ Rembrandt) |
| **firm** | `Rembrandt van Rijn` / `Rijn, Rembrandt van` / signed or mentioned-on-object variants, **and** no hedge family |

### 2.2 Priority (first match wins)

```
1. excluded  — missing image / failed IIIF after retry
             OR description-probe hit with named other artist / anonymous only
             OR firm Rembrandt that appeared *only* via description probe
                with no hedge (smoke patterns: SK-A-3982, SK-A-3138)
             OR duplicate URI/object_number (keep first)

2. validation — circle_workshop family matches
                (circle/workshop beats attributed if both present)

3. ambiguous  — attributed family matches (O05 / SK-A-4096)

4. cohort     — firm family, no hedge, and source_query_type == creator
                (main search: Rembrandt van Rijn + D10)

5. excluded   — fail closed
```

### 2.3 Acquisition order (Wave B implementation sketch)

1. **Main search:** paginate `{**FILTERS, creator=MAIN_CREATOR_QUERY}`; resolve each; download IIIF; assign split via §2.2.  
2. **Validation probes:** for each `VALIDATION_DESCRIPTION_QUERIES`, paginate `{imageAvailable, type=painting, description=...}` (**no material filter on probes** — match Phase 0 smoke; oil filter re-checked after resolve if material present, else keep if painting+image and KEEP label). Deduplicate by `object_uri` against existing rows.  
3. Re-apply §2.2 on merged set (idempotent).  
4. Write SQLite + images + inventory.

**Expected N (phase0):** ~24 main hits → most `cohort`, 1 `ambiguous` (SK-A-4096 if in search), probes add **SK-A-3934** as `validation`; many probe hits → `excluded`. Validation N ≈ **1–3**. Disk ≪ 5 GB (~30 × ~237 KB).

### 2.4 O05 (pending human lock)

Per Stats: **SK-A-4096 → `ambiguous`**. Data Engineer will implement that default unless human chooses otherwise before Wave B. No change to `docs/decisions.md` until human approves.

---

## 3. Module plan (flat layout, D15)

| File | Role | Reuse from `smoke_api.py` |
|---|---|---|
| `config.py` | Unchanged locks (FILTERS, queries, IIIF, `DB_PATH`) | — |
| `smoke_api.py` | Keep as Phase 0 smoke only; do **not** grow into downloader | — |
| **`rijks_api.py`** *(new)* | Shared HTTP session, `search`, `resolve`, `paginate_ids`, `extract_*`, `get_iiif_identifier`, `iiif_url`, download helper | Move/copy proven functions |
| **`acquire.py`** *(new)* | CLI: run acquisition, assign splits, upsert SQLite, write images | Calls `rijks_api` |
| **`inventory.py`** *(new, optional)* | Or `python acquire.py --inventory-only`: emit `results/inventory.*` | Reads SQLite |

**Out of scope for Wave B:** preprocess, embeddings, scoring, FastAPI, Gradio.

**CLI sketch:**

```text
python acquire.py              # full Wave B harvest (after unlock)
python acquire.py --dry-run    # resolve + split assignment, no image write
python acquire.py --inventory  # regenerate results/inventory.* from DB
```

---

## 4. Storage recommendation

| Option | Pros | Cons |
|---|---|---|
| **SQLite `data/cohortscope.sqlite` (P01)** | Single file; SQL filter on `split`; easy audit; matches config | Tiny ceremony for ~30 rows |
| Parquet + JSON sidecars | Friendly to pandas later | Two formats; easier to desync image paths vs labels |
| CSV only | Simple | Weak typing; no PK enforcement; poor for L7 duplicate rule |

**Recommend: SQLite (P01).** Optional export: `results/works.csv` generated from SQLite for humans (not source of truth).

Schema DDL (Wave B):

```sql
CREATE TABLE works (
  object_uri TEXT PRIMARY KEY,
  object_number TEXT NOT NULL UNIQUE,
  title TEXT,
  creators_json TEXT NOT NULL,
  creator_label_family TEXT NOT NULL,
  split TEXT NOT NULL CHECK (split IN ('cohort','validation','ambiguous','excluded')),
  split_reason TEXT NOT NULL,
  source_query_type TEXT NOT NULL,
  source_query TEXT NOT NULL,
  iiif_id TEXT,
  iiif_max_edge INTEGER NOT NULL,
  image_path TEXT,
  image_bytes INTEGER,
  filters_json TEXT NOT NULL,
  acquired_at TEXT NOT NULL
);
CREATE INDEX idx_works_split ON works(split);
```

---

## 5. Inventory report (`results/`)

### 5.1 `inventory.json`

- `generated_at`
- `filters` / `iiif_max_edge` / `db_path`
- `counts`: per `split`, plus `with_image` / `missing_image`
- `disk_bytes_images` + note vs 5 GB budget
- `expected_validation_n_note`: tiny N (1–3); cite T017
- `works`: array of `{object_number, title, split, split_reason, creators, source_query, image_path}`

### 5.2 `inventory.md`

Human summary:

1. Counts table by split  
2. Explicit **tiny validation N** warning (Literature T016 §4 / Stats T017 §3)  
3. Full list of `validation` + `ambiguous` rows with creator strings  
4. Cohort N and excluded top reasons  
5. Missing-image list (should be empty for kept scored splits)  
6. Pointer: split rules live in T017 + this design

---

## 6. Alignment notes

| Source | How this design follows it |
|---|---|
| Stats T017 | 4-way split; O05→ambiguous; field list §5; leakage L1–L8 structurally via `split` |
| Literature T016 | Live API only; provenance fields; document tiny N in inventory |
| Roadmap Phase 1 exit | Local image + metadata; explicit split; counts; &lt;5 GB — **update exit checklist to 4-way after human lock** |
| smoke_api | Same resolve/IIIF chain; same description-probe KEEP hints |

**Roadmap still lists 3-way split** (`cohort` \| `validation` \| `excluded`). After human approval, Project Manager should refresh roadmap exit criteria to include `ambiguous`.

---

## 7. Human decisions required

1. Approve schema §1 (fields + SQLite)?  
2. Approve split algorithm §2 (4-way + priority)?  
3. Lock **O05** = `ambiguous` for SK-A-4096 (and future attributed-to Rembrandt oils)?  
4. Unlock **Wave B** (T011–T015)?

No download code until (3) and (4) are yes.
