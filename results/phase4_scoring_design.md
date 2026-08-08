# Phase 4 scoring design (decomposable outlier rank)

**Task:** T040 · **Role:** stats · **Date:** 2026-08-07  
**Status:** **LOCKED (D30)** — human approved 2026-08-07; implemented as `scores_v1`  
**Inputs:** D05, D13, D19–D21, D29; `results/phase3_matrix_contract.md`; T017 tiny-N + L1–L8; `data/features/features_v1_dictionary.md`  
**Wave B:** T041–T043 implemented; O04 outcome recorded as `weak` (not retuned)

---

## Verdict

| Topic | Recommendation |
|---|---|
| Signal A | L2-normalize ResNet50 vectors → **cosine distance to cohort centroid**; then cohort-referenced z of that distance |
| Signal B | Per-column **mean/std on cohort** → 8 z-scores → **RMS \|z\|** as oddness; drivers = top \|z\| columns |
| O02 fusion | **`combined = z_A + z_B`** (equal-weight sum of signal z-scores). Keep `z_A`, `z_B`, and feature drivers in the table |
| O04 (N_val=1) | **Pass** if SK-A-3934 `combined` ≥ cohort **p95** of `combined`; else **weak** / **fail** by tier below — **no AUC** |
| Fit | **`split=cohort` only** (N=23). Never tune cutoffs or formulas on validation/ambiguous |
| Outputs | `results/scores/scores_v1.csv` + `results/validation_report.md` (+ fit manifest) |

---

## 0. Inputs and masks

| Item | Source |
|---|---|
| Embeddings | `data/embeddings/embed_v1/matrix.pt` — `X[N,2048]`, `object_numbers` |
| Features | `data/features/features_v1.csv` — 8 O03 columns |
| Splits | SQLite `works.split` (authoritative) |
| Scored set | cohort ∪ validation ∪ ambiguous (N=25) |
| Fit set | `split == "cohort"` only (N=23) |

Integrity (M1–M3 from matrix contract) must pass before fitting. No imputation.

**Leave-one-out (LOO) for cohort self-scores:** when scoring a cohort row for A (and for the cohort distribution of raw scores used to build z_A / z_B), compute that row’s distance/features relative to parameters fit on the **other 22** cohort rows. Validation and ambiguous always use the **full** cohort fit (N=23). Prevents optimistic “near own mean” bias without touching held-out labels.

---

## 1. Signal A — embeddings (“odd vs cohort”)

**Problem:** dim=2048, N_cohort=23 → full covariance / Mahalanobis is singular and unstable. **Do not** use sample covariance in 2048-d.

### Fit (cohort only)

1. L2-normalize each embedding: \(\hat{x} = x / \|x\|_2\).  
2. Cohort centroid \(\mu_A = \mathrm{mean}_i \hat{x}_i\) over fit rows (LOO: exclude the row being scored when that row is cohort).  
3. Optional: L2-normalize \(\mu_A\) after averaging.

### Score

\[
d_A(i) = 1 - \cos(\hat{x}_i, \mu_A) = 1 - \hat{x}_i^\top \mu_A
\]

(Higher = farther from cohort center in embedding space.)

### Cohort-referenced signal z

Let \(\{d_A(j)\}\) for cohort rows (each with LOO centroid).  
\(\mu_{dA}, \sigma_{dA}\) = mean and sample std of those cohort \(d_A\) values (ddof=1). If \(\sigma_{dA}=0\), set \(z_A=0\) and log a QC warning.

\[
z_A(i) = \frac{d_A(i) - \mu_{dA}}{\sigma_{dA}}
\]

**Driver string A:** `embed_cosine_to_centroid` (single embedding driver; no per-dim dump).

**Rejected for v1:** PCA→Mahalanobis (extra knobs, L6 risk if components chosen post-val); kNN distance with k tuned on val; learning a linear probe.

---

## 2. Signal B — eight hand-built features

Columns (fixed order, D29):  
`grad_mag_mean`, `grad_mag_std`, `grad_orient_entropy`, `laplacian_var`, `lbp_entropy`, `glcm_contrast`, `lab_chroma_mean`, `hue_circ_std`

### Fit (cohort only)

For each column \(c\): \(\mu_c, \sigma_c\) = mean and sample std on cohort (LOO: when scoring cohort row \(i\), fit \(\mu_c,\sigma_c\) on cohort \ \(\{i\}\)). Cap: if \(\sigma_c < \varepsilon\) (e.g. `1e-12`), treat \(z_c=0\) for that column and warn.

### Per-column z (all scored rows)

\[
z_c(i) = \frac{x_c(i) - \mu_c}{\sigma_c}
\]

### Aggregate oddness

\[
d_B(i) = \sqrt{\frac{1}{8}\sum_c z_c(i)^2}
\]

(RMS of z-scores — uses all columns; scale-free across units.)

Then cohort-referenced:

\[
z_B(i) = \frac{d_B(i) - \mu_{dB}}{\sigma_{dB}}
\]

where \(\mu_{dB},\sigma_{dB}\) are mean/std of cohort \(d_B\) (LOO-consistent as above).

### Drivers (decomposability)

- `driver_B_1`, `driver_B_2`: column names with largest and second-largest \(|z_c(i)|\)  
- Optional columns in CSV: all eight `z_*` for audit (wide but honest)

**Rejected for v1:** max-\|z\| alone as the only B score (ignores multi-column drift); learned weights on columns; dropping columns after seeing SK-A-3934.

---

## 3. O02 — combine into one rank, keep drivers

### Proposed lock text

> **O02:** `combined = z_A + z_B` (equal weight). Rank all scored works by `combined` descending (higher = more anomalous). Table must retain `z_A`, `z_B`, `d_A`, `d_B`, and feature driver columns — never export combined alone.

### Why sum (not max / not rank-average)

| Rule | Pros | Cons |
|---|---|---|
| **Sum `z_A+z_B` (choose)** | Both signals can contribute; simple; matches “two-signal” story | One large signal can dominate — still visible via drivers |
| Max(`z_A`,`z_B`) | Emphasizes either channel firing | Hides joint evidence; more brittle with N=1 storytelling |
| Rank average | Scale-robust | Ranks among full N=25 mix cohort+val in the rank denominator; prefer z vs **cohort** distribution |

Primary sort key: **`combined`**. Secondary: `z_A` then `z_B` for ties.

**Dominant signal** column: `A` if \(z_A \ge z_B\), else `B` (for narrative; not a third score).

---

## 4. O04 — success with validation N=1

Inventory: **validation = SK-A-3934 only**. Ambiguous SK-A-4096 is scored but **never** enters O04/T043 (D21).

**Forbidden:** ROC-AUC, PR-AUC, “X% recall,” treating ambiguous as a second validation count.

### Pre-registered bar (proposed lock)

Let \(F_{\mathrm{cohort}}\) = empirical CDF of `combined` on the **23 cohort** LOO scores.  
Let \(c_{\mathrm{val}}\) = `combined` for SK-A-3934.

| Outcome | Rule |
|---|---|
| **Pass** | \(c_{\mathrm{val}} \ge\) cohort **95th percentile** of `combined` (i.e. at least as extreme as the top ~5% of cohort self-scores) |
| **Weak** | Cohort **median** \(\le c_{\mathrm{val}} <\) cohort p95 |
| **Fail** | \(c_{\mathrm{val}} <\) cohort median |

### Mandatory sensitivity (report, do not retune)

In `validation_report.md`, also state whether val clears cohort **p90** and **p99**, and its **rank among 25** scored works (1 = most anomalous). Sensitivity is descriptive; **O04 decision uses p95 only**.

### Honesty clause

With N_val=1, **Pass** is a single-case tail hit, not a population rate. **Fail/weak** is inconclusive for “method never works” — document as such (T017 §3). Do not claim the method is “working” until T043 records one of {pass, weak, fail} explicitly.

### Proposed lock text

> **O04:** Success = SK-A-3934 `combined` ≥ cohort p95 of LOO `combined`. Weak = ≥ median but &lt; p95. Fail = &lt; median. Ambiguous excluded. No AUC.

---

## 5. Leakage / no peeking (L1–L6)

| Rule | Phase 4 action |
|---|---|
| L1–L2 | Fit μ, σ, centroids, percentiles **only** on cohort (LOO as specified) |
| L5 | p95 / median cutoffs are **pre-registered here**; do not move them after seeing SK-A-3934 |
| L6 | Do not change A/B formulas, column set, or fusion after looking at val/ambiguous scores |
| D21 | SK-A-4096 in ranked table; omit from pass/weak/fail |
| Implement order | Write fit code → score all → **then** read validation row for T043 report (no iterative redesign) |

If Pass fails and human opens T050: scope-tight fixes only; reopen O02/O04 explicitly — no silent threshold slide.

---

## 6. Output artifacts

Recipe id: **`scores_v1`**.

```text
results/scores/
  scores_v1.csv
  fit_manifest.json
results/validation_report.md
```

### `scores_v1.csv` (one row per scored work)

| Column | Meaning |
|---|---|
| `object_number` | Join key |
| `split` | cohort / validation / ambiguous |
| `title` | From DB (reporting) |
| `d_A` | Cosine distance to cohort centroid |
| `z_A` | Cohort-referenced embedding oddness |
| `d_B` | RMS of feature z-scores |
| `z_B` | Cohort-referenced feature oddness |
| `combined` | `z_A + z_B` |
| `rank_combined` | 1 = most anomalous among N=25 |
| `dominant_signal` | `A` or `B` |
| `driver_A` | Constant `embed_cosine_to_centroid` (symmetry with B) |
| `driver_B_1`, `driver_B_2` | Top \|z\| feature names |
| `z_<feature>` ×8 | Optional but **recommended** for decomposability |

Sort CSV by `rank_combined` ascending.

### `fit_manifest.json`

- `recipe_id`, date, N_cohort, N_scored  
- Embedding: `metric=cosine_distance_to_centroid`, LOO=true  
- Features: column list, `aggregate=rms_z`, LOO=true  
- O02: `combined = z_A + z_B`  
- O04: p95 / median rules as locked  
- Paths to embed_v1 + features_v1  
- **No** validation metrics inside the fit file (keep fit vs evaluate separate)

### `validation_report.md`

- Counts; identity of validation + ambiguous  
- SK-A-3934: `combined`, `z_A`, `z_B`, drivers, rank, vs cohort median/p90/p95/p99  
- Explicit **pass / weak / fail** per O04  
- One paragraph limits (N=1; IIIF≠forensic scan; D27 geometry)  
- Ambiguous SK-A-4096: scores only, non-counting

---

## 7. Implementation sketch (after lock — not now)

1. `score.py` (flat module): load matrices + splits → fit cohort → score 25 → write CSV + manifest.  
2. Separate function or flag for `validation_report.md` generation (T043) so fit artifacts stay label-clean.  
3. Deterministic: fixed seed unused (no RNG); sorted IDs.

---

## 8. Lock record

Human locked **D30** (2026-08-07): Signal A cosine-to-centroid + z; Signal B RMS of 8 cohort z; **O02** `combined = z_A + z_B`; **O04** pass ≥ cohort p95 / weak median–p95 / fail &lt; median (SK-A-3934 only). Do not change these rules after seeing validation (T050 only if human reopens).
