# Feature dictionary — `features_v1`

**Recipe:** `features_v1` · **Source:** Branch H `preprocess_v1/rgb/*.png` only  
**Locked:** D29 / O03 · **No** z-scores, fits, or Branch C

| Column | Meaning |
|---|---|
| `object_number` | Join key (same as SQLite `works`, preprocess caches) |
| `grad_mag_mean` | Average edge strength (Sobel) — overall surface busy-ness |
| `grad_mag_std` | Spread of edge strength — smooth passages vs local impasto/edge clusters |
| `grad_orient_entropy` | How evenly stroke/edge directions are spread — ordered vs chaotic |
| `laplacian_var` | High-frequency energy (Laplacian variance) — fine grain vs flat paint |
| `lbp_entropy` | Local Binary Pattern histogram entropy — micro-texture complexity |
| `glcm_contrast` | Gray-level co-occurrence contrast — local tonal jumps |
| `lab_chroma_mean` | Mean Lab chroma sqrt(a*^2+b*^2) — how colorful vs muted overall |
| `hue_circ_std` | Circular std of Lab hue (chroma-weighted; chroma<5 ignored) — palette coherence |

## Compute defaults (frozen)

- Grayscale luminance weights `(0.2989, 0.587, 0.114)`
- Sobel 3×3; orientation entropy on 8 bins over `[0, π)`
- Laplacian via `scipy.ndimage.laplace`
- Uniform LBP P=8, R=1; Shannon entropy of codes
- GLCM: 32 gray levels, distance=1, mean contrast over angles (0.0, 45.0, 90.0, 135.0)
- Lab chroma mean; hue circular std with Lab chroma ≥ 5.0
- **Note:** `hue_circ_std` uses **Lab** hue (`atan2(b*, a*)`), not HSV — do not describe it as HSV in Phase 4 write-ups.

## Geometry (D27)

Branch H is identity on width=1500 IIIF JPEGs; tall works may have height > 1500. No resize/crop/pad in this extractor.
