# Geometry note — preprocess_v1 Branch H

**Date:** 2026-08-06 · **Decision:** D27 · **Recipe:** `preprocess_v1`

## Width=1500 vs long-edge 1500

Phase 1 IIIF downloads use `full/{edge},` with `edge=1500` — that sets **width** to 1500, not the **long edge**. D12 wording said “long-edge 1500px”; actual acquisition is width-constrained.

On the scored cache (N=25 Branch H PNGs):

| Geometry | N | Meaning |
|---|---:|---|
| Long edge == 1500 | 5 | Landscape / wide; height ≤ 1500 |
| Long edge > 1500 | 20 | Tall portraits; width=1500, height > 1500 |

All 25 have `width == 1500`. Examples: SK-A-1935 `1500×1056` (long=1500); SK-A-3934 `1500×1854`; SK-A-5033 `1500×2349`.

## Branch H is identity

Branch H copies decoded JPEG geometry into lossless PNG (no resize/crop/pad). `src_eq_png` for all 25. Tall works therefore keep more pixels than a true long-edge-1500 downscale would — brushstroke survival is fine.

This is documentation honesty (D12 wording vs Phase 1 URL), not a Wave B transform bug (D27). Do **not** retune preprocess from validation appearance. Optional future re-acquire with true long-edge is a Data/human choice, not a Phase 2 fix.
