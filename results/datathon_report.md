# Cohortscope — Datathon report

**Working name:** Cohortscope  
**Repo:** https://github.com/JialaiYing/CohortScope.git  
**Report path:** `results/datathon_report.md` (folds T071 + T051 + T052)  
**Date:** 2026-08-08, superseded 2026-08-23  
**Scores recipe:** `scores_v1` (D30)

> **Status note (2026-08-23).** This document is the Phase 0-5 snapshot, written when
> O04 was the only held-out result the project had. Four further pre-registered tests
> have run since, and all four returned `fail`. Sections 1-3 (problem, method, decisions)
> still describe the shipped pipeline accurately; sections 4-10 describe a state of
> knowledge the project has moved past. Read section 4.1 first, then go to
> `results/dossier/index.html` for the assembled current record.

**Headline (2026-08-23):** The method does not work and the question is closed. Five
pre-registered held-out outcomes: O04 `weak` on a single work, then O06, O09, O11 and O13
all `fail`. Neither half of the pipeline separates firm Rembrandts from their documented
pupils, at any of four physical resolutions, and in all four pupil tests a single
digitization column out-predicts the whole pipeline.

*Original headline, 2026-08-08:* End-to-end pipeline delivered a decomposable ranked
anomaly table. Pre-registered held-out check **O04 = `weak`** on the sole validation work.
**We do not claim the method works or passes.**

---

## 1. Problem

Museums publish open high-resolution images and metadata, but lack an automated, *explainable* way to triage which pieces in an attribution group might warrant expensive physical or documentary re-examination. Cohortscope asks a narrow question on one museum and one artist:

> Relative to Rijksmuseum oils *currently attributed* to Rembrandt van Rijn, which works look statistically unusual — and *which measurable signal* drove that flag?

Held-out circle / workshop–style labels are the intended check that the ranking is not just noise. Success was pre-defined (O04 / D30); this cycle **did not meet** that bar.

---

## 2. Method

### Pipeline

```
acquire (Search → Linked Art → IIIF)
  → preprocess_v1 (Branch H RGB + Branch C 224)
  → embed_v1 (ResNet50) + features_v1 (8 scalars)
  → score (cohort-only normals, LOO self-scores)
  → ranked CSV + validation report
```

No Gradio / FastAPI (T054 = tables-only). No custom backbone training.

### Two signals (D05, D29, D30)

| Signal | Input | Distance | Standardized score |
|---|---|---|---|
| **A** | Pretrained ResNet50 (`IMAGENET1K_V2`), **no finetune** | Cosine distance of L2-normalized embedding to cohort centroid | `z_A` |
| **B** | Eight hand-built texture/color scalars on Branch H | RMS of per-feature cohort z-scores | `z_B` |

**O03 / D29 feature columns:**  
`grad_mag_mean`, `grad_mag_std`, `grad_orient_entropy`, `laplacian_var`, `lbp_entropy`, `glcm_contrast`, `lab_chroma_mean`, `hue_circ_std`.

**Fusion (O02 / D30):** `combined = z_A + z_B`.  
Each row keeps `dominant_signal`, `driver_A`, `driver_B_1` / `driver_B_2`, and per-feature `z_*` — decomposable, not a single opaque authenticity probability.

### Fit rules (leakage-aware)

- Fit **μ / σ / centroid on `split=cohort` only** (N=23).
- Cohort self-scores use **leave-one-out** (exclude self from that work’s normal).
- `validation` and `ambiguous` use the full cohort fit; they **never** enter estimation.
- Confirmed in `results/phase4_review.md` (PASS; no must-fix).

### Corpus counts (`scores_v1`)

| Split | N | Role |
|---|---:|---|
| cohort | 23 | Fit normals |
| validation | 1 | O04 only (`SK-A-3934`) |
| ambiguous | 1 | Scored, **excluded** from O04 (`SK-A-4096`) |

---

## 3. Crucial decisions (short)

| ID | Choice | Why it matters here |
|---|---|---|
| **D10–D11** | Search: painting + oil paint + image; **no** `technique` filter | Medium-clean oils; API `technique` ≠ medium |
| **D12** (+ D27) | IIIF width=1500 (tall works may have long edge >1500) | Budget/quality tradeoff; weaker than forensic scans |
| **D13** | ResNet50 ImageNet weights, no finetune | Fits 4GB VRAM; “pretrained pipeline eval,” not scratch training |
| **D19–D20** | Splits: `cohort` \| `validation` \| `ambiguous` \| `excluded`; priority rules | Explicit contamination control |
| **D21** | *Attributed to Rembrandt* → `ambiguous` | Never fit; never count in O04 |
| **D26** | `preprocess_v1`: Branch H identity @ acquired JPEG; Branch C 224 for CNN | No corpus-level pixel fit |
| **D29** | `embed_v1` + 8 O03 features | Locked extract contract before scoring |
| **D30** | `combined=z_A+z_B`; O04 = val vs cohort median / **p95** | Pre-registered; **not retuned** after seeing val scores |

Full ledger: `docs/decisions.md`.

---

## 4. Results

Primary artifacts: `results/scores/scores_v1.csv`, `results/validation_report.md`, `results/phase4_results_narrative.md`.

### 4.1 What the four later tests found (2026-08-23)

Written after this report's original body. The numbers below come from the reports named
at the end of this subsection, not from anything else in this document.

| Outcome | What it tested | Works ranked | AUC | Verdict |
|---|---|---:|---:|---|
| O04 | one circle/workshop work against the cohort | 1 | n/a | `weak` |
| O06 | 67 documented Rembrandt pupils, fixed-1500 px pipeline | 67 | 0.419 | **`fail`** |
| O09 | Signal B on tiles held at a constant 0.20 mm/px | 55 | 0.469 | **`fail`** |
| O11 | Signal A on 224 px tiles with no resize and no crop | 52 | 0.523 | **`fail`** |
| O13 | both signals swept over 0.15 / 0.20 / 0.25 / 0.30 mm/px | 40 and 35 | 0.453-0.530 | **`fail`** |

Three escape hatches were opened and closed in order. Too few samples: N went from 1 to 67
and the result got worse. A scale confound: the images really did vary 35-fold in
millimetres of canvas per pixel, D34 removed that by fetching fixed physical areas instead
of fixed pixel counts, and both halves of the method were then retested on commensurable
pixels. The wrong scale: the sweep covered a 2x range with the population held fixed, and
all eight points landed within 0.047 of chance.

What survives is a negative result with a clear cause. Camera metadata, specifically
`mm_per_px_native`, separates the two classes better than the model in every pupil test
run: 0.590 in O06, 0.689 in O09, 0.705 in O11, 0.617 in O13. The published imagery does not
carry brushwork at the scale the hypothesis needs, and for 44 of 108 works, the Night Watch
among them, it never can at the resolution the museum currently publishes.

Reports, each with a design document committed before its data existed:
`pupil_validation_report.md`, `tile_validation_report.md`, `tile_embedding_report.md`,
`resolution_sweep_report.md`.

---

### O04 held-out check — **`weak`**

**Object:** `SK-A-3934` (*Borstbeeld van een lachende jonge man*), `split=validation`.

| Quantity | Value |
|---|---|
| `combined` | 0.282608 |
| `z_A` / `z_B` | 0.022581 / 0.260027 |
| Dominant | **B** (`hue_circ_std`, `grad_mag_std`) |
| Rank among 25 | **10** |
| Cohort median / p95 | −0.116810 / **2.106898** |
| Clears median / p95 | Yes / **No** |
| **O04** | **`weak`** |

Pre-registered rule: pass ≥ cohort p95; weak median ≤ score < p95; fail < median. Rules unchanged after scoring (`validation_report.md`; review confirmed).

**Reading:** Slightly above the cohort median, far from the p95 bar; embedding channel near null. This is **not** recovery of a clear anomaly and **not** a soft pass (`phase4_results_narrative.md`).

### Ranked table summary (descriptive)

Rank 1 = highest `combined` (most anomalous vs fitted Rembrandt cohort normals):

| Rank | Object | Split | `combined` | Dom. | Note |
|---:|---|---|---:|---|---|
| 1 | SK-A-4674 | cohort | 3.064 | B | Top cohort outlier (texture) |
| 2 | SK-A-4096 | **ambiguous** | 2.277 | B | Exploratory only — **not** O04 |
| 3 | SK-C-597 | cohort | 2.127 | B | |
| 4 | SK-A-1935 | cohort | 1.927 | A | |
| … | … | … | … | … | … |
| **10** | **SK-A-3934** | **validation** | **0.283** | **B** | **O04 probe** |
| 25 | SK-A-5092 | cohort | −1.911 | B | Closest to cohort normal |

Display `combined` values above are **rounded**; exact floats are in `results/scores/scores_v1.csv` (O04 table in this section uses full precision).

High ranks mean “far from this cohort’s fitted normal,” **not** “museum-confirmed misattribution.” Top ranks are mostly **cohort** works; the validation probe sits **mid-pack**.

### Ambiguous (excluded from success)

`SK-A-4096` (*Simson en Delila*) ranks **#2** (`combined`≈2.28) but per **D21** does not confirm or refute the method. We do not promote it into O04.

---

## 5. Evaluation honesty

| Claim type | Status |
|---|---|
| Method “works” / O04 pass | **No** |
| Soft pass / rescued by ambiguous | **No** |
| Pipeline reproducible; scores decomposable | Yes — `scores_v1` + `fit_manifest.json` |
| Model trained from scratch on this set | **No** — pretrained ResNet50, frozen |
| Validation sample size | **N_val = 1** — no recovery-rate estimate; weak is inconclusive for “never works” and insufficient for “works” |
| AUC / learned fusion weights | Not used (by design; avoids leakage, limits power) |
| Phase 4 leakage review | PASS (`results/phase4_review.md`) |

Language for judges: this is **pretrained pipeline / cohort-anomaly evaluation**, not a Kaggle-style from-scratch classifier contest.

---

## 6. Limitations and what a stronger claim would need

**Limits of this cycle**

1. **N_val = 1** — One weak case cannot establish triage utility.
2. **IIIF ~1500 px** — Far from Johnson-style forensic scans; fine brush microstructure is under-resolved.
3. **Hand-built B is explainable but weak** on this probe; A contributed almost nothing for SK-A-3934.
4. **Single museum / single attribution group** — Confound control by design; no multi-collection stress test.
5. **Novelty framing was contingent on a held-out pass** — that contingency did not fire (see §7).

**What would be needed for a stronger claim** (future work; **not** opened as T050 here)

- Larger held-out set of circle/workshop/school oils with locked labels *before* scoring.
- Possibly higher-resolution imaging or a second backbone only if pre-registered (D13: DINOv2 only if ResNet50 fails — still needs human reopen).
- Pre-registered multi-probe metrics (e.g. fraction above p95) with N large enough that one case is not decisive.
- Optional second-artist dry run to turn §8 from design claim into evidence.

We deliberately **did not** retune O02/O04 or fold ambiguous into T043 after seeing scores.

---

## 7. Novelty vs prior art (honest)

Sources: `results/prior_art_brushstroke_auth.md`, `results/prior_art_dataset_practices.md`.

**Not new**

- Wavelet / statistical brushstroke authentication (Johnson et al. 2008; Lyu et al. 2004; Berezhnoy et al.).
- CNN / ResNet artist recognition and Rembrandt–pupil supervised models (e.g. Reuter 2023).
- Using Rijksmuseum open data for CV (Mensink & van Gemert 2014 Challenge dumps).

**What this project attempted to add**

A **decomposable two-signal cohort anomaly ranker** on a **live** Rijksmuseum Rembrandt oil cohort (Search → Linked Art → IIIF), with circle/workshop-style works as **held-out anomaly probes** rather than training classes — success defined only if those probes clear a pre-registered tail bar.

**After Phase 4:** That empirical gate returned **`weak`**. The engineering contribution (transparent split, LOO cohort fits, driver columns, live acquisition) stands; the **scientific “works for reattribution triage” claim does not.** Bonus honesty: prior art is mature; we do not invent brushstroke analysis or Rembrandt ML.

---

## 8. Sustainability — second artist without rewriting core logic (T052)

**Status:** Design-level claim only — **not executed** in this cycle.

The modules are artist-agnostic once metadata and splits are supplied:

| Stage | Module(s) | What changes for artist #2 | What stays |
|---|---|---|---|
| Acquire | `rijks_api.py`, `acquire.py` | Creator / description probes + split rules in config/DB | Pagination, Linked Art resolve, IIIF download |
| Preprocess | `preprocess.py` | Nothing structural (`preprocess_v1`) | Branch H / Branch C recipes |
| Embed | `embed.py` | Nothing (same ResNet50) | `embed_v1` tensor layout |
| Features | `features.py` | Nothing (same 8 O03 columns) | Branch H stats |
| Score | `score.py` | Refit cohort normals on the new `split=cohort` rows | LOO, `z_A+z_B`, drivers, O04-style tiers if re-locked |

**Human / config work, not core rewrites:** new Search filters and label-priority rules (analogs of D10, D19–D21); inventory of cohort vs validation; optional re-lock of O04 thresholds for the new cohort size. Same path: acquire → preprocess → embed → features → score → ranked table.

Until someone runs that path on a second artist, sustainability remains an **architecture argument**, not a demonstrated result.

---

## 9. Deliverables map (for reviewers)

| Artifact | Role |
|---|---|
| `results/scores/scores_v1.csv` | Full ranked, decomposable scores |
| `results/scores/fit_manifest.json` | Fit recipe / LOO flags |
| `results/validation_report.md` | O04 = weak numbers |
| `results/phase4_results_narrative.md` | Short honesty narrative |
| `results/phase4_review.md` | Leakage / scope PASS |
| `results/prior_art_*.md` | Prior art + dataset practice |
| `docs/decisions.md` | Locked decisions |
| Root README (T070) | Reproduce + dataset link |

Demo video: **human-owned** (T072). UI: tables-only (T054).

---

## 10. Closing statement

**Closing statement, 2026-08-23.** The ranking does not work and should not be used. What
the project produced instead is a measurement and a tool. The measurement: on this corpus,
model-based attribution triage is limited not by architecture and not by sample size but by
how much canvas a published pixel covers, and that quantity turns out to be recorded,
auditable, and worse than most people assume. The tool: `python tiles.py --plan` reads the
museum's own IIIF metadata and returns a per-work verdict on whether the question can be
answered from published imagery at all, with a stated reason when it cannot. That verdict
is reusable on any IIIF collection and does not depend on the ranking being right.

Five outcomes, five design documents committed before their data, no threshold edited after
the fact. The whole record is assembled in `results/dossier/index.html`.

*(Original 2026-08-08 closing, kept for the record: "Cohortscope ships a transparent,
decomposable anomaly-ranking pipeline on a live Rembrandt oil cohort from the Rijksmuseum.
Under the locked success rule, the single held-out validation work scores `weak`
(rank 10/25; above median, below p95). The method is not claimed to work.")*
