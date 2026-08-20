# Phase 8 pre-registration — physically-normalized tiling (D34 / O07 resolved)

**Status:** pre-registered. Written and committed **before** any tile was fetched.
**Does not modify:** D04, D19–D21, D30, D32, O04, O06. `preprocess_v1`, `embed_v1`, `features_v1`, and `scores_v1` are left intact and keep their current outputs.

---

## 1. Why

`results/resolution_audit.md` established that the analyzed corpus spans **0.100–3.467 mm/px** — a 35× range — because every image was fetched at a fixed *pixel* width of 1500 regardless of how large the painting is. Texture statistics computed across that corpus are not measuring the same physical quantity from one work to the next. After the Branch C resize and centre-crop, **0 of 108 works** reach 0.30 mm/px, so the embedding never had brushwork to compare on any painting.

Both problems have the same fix: stop requesting a fixed number of pixels and start requesting a fixed **area of canvas**. IIIF serves arbitrary regions at arbitrary sizes, so a patch of known physical size can be fetched directly at a known physical resolution, for every work, without downloading a gigapixel file.

This phase builds that acquisition path and records which works cannot reach the target. It computes no feature, no embedding, and no score.

---

## 2. Locked parameters

| Parameter | Value | Why |
|---|---|---|
| **Resolution floor** | **0.20 mm/px** | O07, decided by the human 2026-08-19 from the eligibility census in `results/resolution_audit.md` §4. A 1 mm stroke spans 5 px and a 2 mm stroke 10 px, comfortably above Nyquist for the stroke widths that carry handling. The 0.15 floor admits the *same* 17 cohort works while costing 12 Tier-1 pupils, so it is dominated. |
| **Tile size** | **30 mm × 30 mm** of canvas | Large enough that GLCM/LBP statistics over 22,500 px are stable; small enough that the physically smallest eligible work still supplies 20 non-overlapping tiles. |
| **Tile pixels** | **150 × 150** | Determined: 30 mm ÷ 0.20 mm/px. Not a free parameter. |
| **Edge inset** | **5% of each edge** | Excludes frame rebate, canvas tacking margins, and lining artefacts at the perimeter. |
| **Tiles per work** | **N = 20**, non-overlapping | Equal weight per work. Set by the binding constraint: `SK-A-3982` (15 × 19 cm) supplies exactly 4 × 5 = 20 tiles inside the inset. A per-work cap is required so that a 453 cm painting (2,418 available tiles) does not dominate a tile population. |
| **Recipe ID** | `tiles_v1` | Frozen, per the standing recipe-ID contract. |

### Tile selection (deterministic, no RNG)

1. Inset region in native pixels: `x ∈ [0.05·W, 0.95·W)`, `y ∈ [0.05·H, 0.95·H)`.
2. Native-pixel tile side `s = round(30.0 / mm_per_px_native)`.
3. Grid `cols = ⌊inset_width / s⌋`, `rows = ⌊inset_height / s⌋`, giving `M = rows · cols` candidate positions enumerated row-major.
4. Select indices `⌊i · M / N⌋` for `i = 0 … N−1`. Strictly increasing for `M ≥ N`, so no position repeats, and the stride spreads the sample across rows.
5. Fetch each as IIIF `{x},{y},{s},{s}/150,150/0/default.jpg`.

No random seed is involved; the same database yields the same tiles on every run.

---

## 3. Eligibility and the below-floor verdict

A work is **eligible** for `tiles_v1` iff all hold:

1. `split` ∈ {`cohort`, `validation`, `ambiguous`, `pupil`}.
2. `mm_per_px_native` is known and **≤ 0.20**.
3. The inset region yields `M ≥ 20` candidate tiles.
4. Its IIIF identifier resolves.

Everything else is recorded as **below floor** with an explicit reason and is **excluded from `tiles_v1` entirely** — not tiled, and (in later phases) not fitted, not scored, and not counted in any metric computed on this recipe. A work the source imagery cannot support is reported as unanswerable rather than given a number.

The verdict is **derived, not stored on `works`**. `works` holds measured facts about an object; the floor is a policy that can change, and a policy value cached next to a fact goes stale silently. Eligibility is recomputed from `mm_per_px_native` and written into `data/tiles/tiles_v1/manifest.json`.

### Expected population (from geometry already recorded; no tile fetched to produce this)

| Split | Eligible at 0.20 mm/px | Total |
|---|---:|---:|
| cohort | 17 | 23 |
| pupil — Tier 1 | 38 | 67 |
| pupil — Tier 2 | 7 | 16 |
| validation | 1 | 1 |
| ambiguous | 1 | 1 |
| **Total** | **64** | **108** |

---

## 4. Consequences accepted in advance

1. **The cohort shrinks from 23 to 17.** Six firm Rembrandts — the physically largest, including the Night Watch at 0.310 mm/px native — are below floor. Any later fit on `tiles_v1` therefore rests on 17 works, and the resulting normals are **not** comparable to the `scores_v1` normals fitted on 23.
2. **Tier-2 pupils collapse to 7.** The Tier-2 sensitivity analysis becomes correspondingly weaker under this recipe and will be reported with its reduced N, not quietly dropped.
3. **`scores_v1` remains the baseline and is not superseded.** It stays exactly as published so that the change in separation between the fixed-1500 pipeline and the physically-normalized one can be measured. Deleting it would destroy the comparison that motivates this phase.
4. **20 tiles is a sample, not a census.** For the largest works it is under 1% of the available surface. Per-work statistics computed from it carry sampling error that grows with painting size, and that must be acknowledged wherever such statistics are reported.
5. **The floor is a choice, and a different floor gives a different corpus.** It was fixed before any tile was seen, and it will not be moved to improve a downstream number. Re-running at another floor is legitimate only as a declared sweep reported in full (planned separately), never as a substitution.

---

## 5. Explicitly out of scope for this phase

No feature extraction, no embedding, no z-score, no anomaly score, no change to any existing recipe or report. Statistics over the tile population are a separate decision and will be pre-registered on their own before being computed.

---

## 6. Artifacts

| Artifact | Path |
|---|---|
| Tile cache (gitignored; regenerable) | `data/tiles/tiles_v1/{object_number}/{row}_{col}.jpg` |
| Manifest incl. every below-floor verdict | `data/tiles/tiles_v1/manifest.json` |
| Coverage / failure QC | `results/qc_tiles_v1/` |
| Human-readable report | `results/tiling_report.md` |
| This pre-registration | `results/phase8_tiling_design.md` |
