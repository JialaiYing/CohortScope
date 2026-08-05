# Phase 1 experimental design (split, O05, tiny-N honesty)

**Task:** T017 · **Role:** stats · **Date:** 2026-08-05  
**Status:** proposed — human must lock O05 + split rules into `docs/decisions.md` before Wave B download  
**Inputs:** D01–D05, D10–D14, P02–P03; `data/meta/phase0_smoke_report.json`; `results/prior_art_dataset_practices.md`

---

## Verdict (read this first)

| Topic | Recommendation |
|---|---|
| Split labels | Exactly four: `cohort` \| `validation` \| `ambiguous` \| `excluded` |
| O05 (SK-A-4096) | **`ambiguous`** — download & score; **never** fit into cohort normals; **never** count toward T043 pass/fail |
| Primary validation | Clear circle / workshop / school / omgeving / atelier labels only (D14 KEEP) |
| Tiny N | Expect **1–3** validation keepers; do not claim AUC / “meaningful fraction” as if N were large |
| Normals | Fit **only** on `split=cohort` (P03). No exceptions. |

Do **not** invent a second validation path (no random Rembrandt holdout, no multi-class Rembrandt-vs-pupils, no other museums).

---

## 1. Exact split rules

Apply after locked filters (D10): `type=painting`, `material=oil paint`, `imageAvailable=true`. Scope: Rijksmuseum only (D01). One object → one `split` value. Prefer explicit creator strings over free-text description alone.

### 1.1 Label vocabulary (English ∪ Dutch)

| Family | Match if creator / attribution text contains (case-insensitive) |
|---|---|
| **Firm Rembrandt** | `Rembrandt van Rijn`, `Rijn, Rembrandt van`, plus signed / mentioned-on-object variants that do **not** also match hedge families below |
| **Hedge — circle/workshop** | `circle of`, `workshop of`, `school of`, `omgeving van`, `atelier van`, `school van` + Rembrandt |
| **Hedge — attributed** | `attributed to Rembrandt`, `toegeschreven aan Rembrandt` |

Description probes (D14) are **discovery only**. Final KEEP/REJECT uses the label families above (and oil+painting+image). Probe text alone never assigns `cohort`.

### 1.2 Assignment rules (priority order)

Evaluate top-down; first match wins.

1. **`excluded`** if any of:
   - Missing local image after resolve/IIIF, or fails D10 filters
   - Description-probe hit whose creators are a **named other artist** (e.g. Lievens, Flinck) or `anonymous` / `anoniem` with no Rembrandt-hedge KEEP label
   - Firm Rembrandt that only appeared because a probe string matched description prose, with **no** circle/workshop/school/attributed hedge on the creator field (smoke example pattern: SK-A-3982, SK-A-3138)
   - Duplicate URI / object_number already assigned (keep first canonical row)

2. **`validation`** if:
   - Hedge — circle/workshop family matches, **and**
   - Creator is not a firmly attributed other master as the sole author (if both “circle of Rembrandt” and a pupil name appear, still KEEP as validation — the museum is marking Rembrandt-orbit authorship, which is the anomaly probe we want)

3. **`ambiguous`** if:
   - Hedge — attributed family matches, **and**
   - Not already `validation` (circle/workshop beats attributed if both present — treat as `validation`)

4. **`cohort`** if:
   - Firm Rembrandt family matches, **and**
   - No hedge family matches, **and**
   - Object comes from the main creator search (`Rembrandt van Rijn`, P02), not solely from a validation probe

5. Else **`excluded`** (fail closed).

### 1.3 What each split is for

| Split | Fit cohort normals? | Score / rank? | Count in T043 success? |
|---|---|---|---|
| `cohort` | **Yes (only these)** | Yes | No (they define “normal”) |
| `validation` | No | Yes | **Yes** |
| `ambiguous` | No | Yes (exploratory) | **No** |
| `excluded` | No | No (metadata OK for inventory) | No |

---

## 2. O05 — SK-A-4096 (“attributed to Rembrandt”)

**Object:** SK-A-4096 · *Simson en Delila* · creators include `attributed to Rembrandt van Rijn` / `toegeschreven aan Rembrandt van Rijn` (phase0 smoke; also hit via `school of Rembrandt` description probe).

### Recommendation: `ambiguous` (not `cohort`, not `validation`)

**Why not `cohort`:** D03 defines the statistical normal as *currently attributed Rembrandt*. “Attributed to” is a weaker catalog claim. Putting it in normals contaminates the center we later use to call others anomalous (violates P03 intent).

**Why not `validation`:** Validation (D04) asks whether works the museum marks as **circle / workshop / school** look far from firm Rembrandt. “Attributed to” is a different hypothesis (uncertain autograph). Counting it in the success fraction mixes two questions and makes a 1–3-item pass/fail uninterpretable: a normal score could mean “looks like Rembrandt” *or* “method failed”; an extreme score could mean “not Rembrandt” *or* “method over-flags.” Prior forensic practice keeps questioned works as a separate probe class (Johnson et al. pattern; see T016), not as accuracy numerator filler.

**Operational rule for SK-A-4096 and any future `attributed to` Rembrandt oil under D10:** store as `ambiguous`; download image; score in Phase 4; report separately; **exclude from mean/covariance/quantile fits**; **exclude from O04/T043 fraction**.

If human prefers maximum validation N over purity: alternative is `validation` with a **mandatory** footnote that O04 is then “hedged Rembrandt-orbit,” not circle-only. Stats **does not** recommend that default.

### Proposed decision text (for human lock)

> **O05 resolved:** Objects labeled *attributed to / toegeschreven aan Rembrandt* (including SK-A-4096) receive `split=ambiguous`. They are never used to fit cohort normals and never counted in held-out validation success (T043). Primary validation remains circle / workshop / school / omgeving / atelier KEEP rules (D14).

> **Split enum (Phase 1):** `cohort` | `validation` | `ambiguous` | `excluded`, assigned by the priority rules in `results/phase1_experimental_design.md` §1.2.

---

## 3. Tiny validation N — what we may and may not claim

Phase0 description probes yield **very few** KEEP candidates (smoke: SK-A-3934 clear circle; SK-A-4096 attributed → ambiguous under this memo). Realistic **`validation` N ≈ 1–3** after filters.

### Allowed later (Phase 4 / write-up)

- Ranked table of all scored works with **per-signal** drivers (embedding distance + hand-built features) — decomposable, not one opaque number (D05)
- For each `validation` object: its ranks/scores vs cohort distribution, with threshold sensitivity (“flagged at τ = …; not at …”)
- Qualitative outcome: **pass / weak / fail** on whether held-out keepers sit in the extreme tail of the cohort-fitted scores
- Explicit statement that N is too small for stable rates

### Not allowed (non-claims)

- ROC-AUC, PR-AUC, or “X% recall” as if validation were a proper test set
- “Meaningful fraction flagged” without fixing O04 to a **count-based** bar (e.g. “≥1 of N validation in top-k or above cohort p95”) — defer exact O04 to Phase 4 gate, but it must be count/tail language, not AUC
- Claiming the method “works” before T043 completes
- Treating `ambiguous` outcomes as confirmation or refutation of the method
- Generalizing beyond Rijksmuseum Rembrandt oils

**Null / weak result is informative:** with N≈1–3, failure to flag can mean no signal *or* unlucky tiny sample. Document as **inconclusive/weak**, not as proof of absence.

---

## 4. Leakage checklist (acquisition)

Anything that can move the fitted “normal” must not see non-cohort labels.

| # | Rule | Fail mode if violated |
|---|---|---|
| L1 | Cohort normals (mean, std, robust center/scale, kNN graph, PCA, thresholds derived from data) fit on **`split=cohort` rows only** | Contaminated normal; validation looks too close |
| L2 | `validation` and `ambiguous` may be **downloaded and scored** but never enter fit code paths | Silent leakage via “fit on all Rembrandt search hits” |
| L3 | Do not drop hedge-labeled works into cohort because they appeared under `creator=Rembrandt van Rijn` search (P03) | Search ≠ firm attribution |
| L4 | Description-probe false positives (other artists, anonymous, firm Rembrandt prose hits) → `excluded`, not soft-cohort | Wrong negative class / label noise |
| L5 | No threshold tuning on validation/ambiguous labels; thresholds from cohort quantiles or pre-registered rule (O02/O04 at Phase 4) | Selection bias; fake pass |
| L6 | No using validation images to choose preprocess / features / backbone (D13 already locked; don’t reopen from val scores) | Researcher degrees of freedom |
| L7 | One canonical `object_number` / URI; no double-counting same painting in cohort and validation | Inflated N, dependent scores |
| L8 | Inventory must list every kept object’s `split` + raw creator strings before scoring | Un-auditable labels |

Code Reviewer (T018) signs off on L1–L8 after Wave B; Stats still designs to make L1–L5 structurally hard to violate.

---

## 5. What Data Engineer must store (Phase 4 validity)

Minimum fields so scoring can join, audit splits, and refuse leakage:

| Field | Why |
|---|---|
| `object_number` (e.g. SK-A-…) | Human-stable ID |
| `uri` (Rijksmuseum id) | Canonical Linked Art identity |
| `split` ∈ {`cohort`,`validation`,`ambiguous`,`excluded`} | Hard gate for fits |
| `title` | Reporting |
| `creators` (full list, as returned) | Audit hedge vs firm |
| `creator_label_normalized` | Optional; which family fired (firm / circle_workshop / attributed / other) |
| `source_query` | Main creator query vs which D14 description probe |
| `validation_keep_reason` or `exclude_reason` | Short code/string; reproducibility |
| `image_path` + `iiif_id` + `iiif_max_edge` (1500) | Join to pixels; D12 |
| `filters_snapshot` | D10 params used when acquired |
| `acquired_at` | Provenance |

**Hard constraint for downstream code:** any `fit_*` function accepts only rows with `split=="cohort"`. Scoring iterates `cohort ∪ validation ∪ ambiguous`.

Inventory (`results/inventory.*`) must publish counts per split **before** Phase 4, including expected tiny `validation` N.

---

## 6. Rejected weak alternatives (do not reopen without human + stats)

- Random holdout of firm Rembrandt as “validation” — tests reconstruction, not D04
- Putting all Rembrandt-search hits in cohort, scoring probes only informally — violates P03
- Folding SK-A-4096 into `validation` by default to inflate N — pollutes success metric
- Multi-museum or multi-artist negatives this cycle — out of scope (D01, deferred list)
- Supervised Rembrandt-vs-pupils classifier — different method; not this project’s validation strategy (T016)

---

## 7. Hand-off

| Who | Action |
|---|---|
| **Human** | Approve or amend O05 + split enum; lock into `docs/decisions.md` |
| **Data Engineer (T010)** | Align schema with §5; implement assignment rules §1.2 in Wave B |
| **Stats** | O02/O04 design at Phase 4 gate; no scoring code until features exist |
| **Review (T018)** | Leakage audit against §4 after download |

**Wave B download must not start until this memo + T010 schema + O05 are human-approved.**
