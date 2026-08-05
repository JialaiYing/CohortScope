# Prior-art dataset practices (Phase 1 note)

**Task:** T016 · **Role:** literature · **Date:** 2026-08-05  
**Scope:** How comparable projects build painting corpora and splits — not method novelty (see T034) or results claims (see T045).

---

## 1. What prior work typically does

| Practice | Pattern in literature | Representative sources |
|---|---|---|
| Source | Frozen museum dump, specialist archive, or scraped web gallery | Van Gogh Museum / Kröller-Müller scan set (Johnson et al. 2008); Rijksmuseum Challenge 2014 dump; RKD downloads (Reuter 2023); WikiArt / Kaggle mirrors |
| Media mix | Often mixed object types unless filtered | Rijksmuseum Challenge: paintings + drawings + sculpture, etc. |
| Labels | Unique artist ID as classification target | Multi-painter recognition; Rembrandt + pupils as separate classes |
| Resolution | Forensic sets = high-res controlled scans; ML classification often web/archive size | Johnson: ~196 dpi gray-scale museum films; Reuter: RKD long-edge ≤650 px; WikiArt: heterogeneous web JPEGs |
| Split | Random train / val / test on uniquely attributed works | e.g. 85:15 train–test then CV inside train (Reuter); standard holdouts on WikiArt subsets |
| Validation of “hard” cases | Disputed works scored *after* training a multi-class model, or left out of accuracy | Johnson set: 82 van Gogh / 6 non / 13 questioned; Reuter: RRP decisions as external probe |
| Imaging confounds | Controlled scan sets reduce them; open web sets usually ignore museum pipeline differences | Single-museum forensic sets vs multi-source scrapes |

**Honest baseline:** Dataset practice for attribution ML is mature. Using museum open data, Rembrandt-circle labels, ResNet-style backbones, and held-out disputed works is **not** new by itself.

---

## 2. Key precedents (dataset angle only)

### Johnson et al. (2008) — closed forensic scan set
- **Data:** 101 high-res gray-scale scans from Van Gogh and Kröller-Müller museums (fixed density, 16-bit).
- **Labels:** Expert-consensus van Gogh / non–van Gogh / questioned.
- **Practice lesson:** Gold-standard attribution work prefers *controlled imaging* and *tiny, curator-vetted* N — not live API harvest. Wavelet / brushstroke pipelines assume that quality.

### Mensink & van Gemert (2014) — Rijksmuseum Challenge
- **Data:** ~100k Rijksmuseum objects (XML + images) released as a **challenge dump**, plus precomputed Fisher vectors.
- **Tasks:** Creator / material / type / year *classification*, not anomaly ranking within one attribution.
- **Practice lesson:** Rijksmuseum has long been a standard open corpus for CV; frozen dumps and pre-extracted features were the norm for reproducibility.

### Reuter (2023) — Rembrandt vs pupils (RKD)
- **Data:** ~2,258 works by Rembrandt + 14 students from RKD websites; long edge ~650 px.
- **Split:** 85:15 train/test on uniquely attributed works; ensemble CNNs; soft confidence thresholds.
- **External probe:** Rembrandt Research Project (RRP) decisions tested after training — closest structural cousin to “held-out attribution check,” but still **supervised multi-class**, not cohort-outlier scoring on one museum catalog.

### WikiArt-style multi-painter sets
- Large scraped galleries; artists kept only above a painting-count floor; random stratified splits.
- **Practice lesson:** Scale and multi-artist coverage over museum-metadata fidelity; attribution nuance (“circle of”, “workshop of”) is usually flattened or dropped.

### Live Rijksmuseum Data Services (current)
- Search → Linked Art resolve → IIIF; CC0 / public-domain reuse; metadata and APIs still evolving.
- Historical dumps (EDM, LIDO, CSV) exist alongside APIs — prior CV challenge used dumps; live Linked Art + IIIF is the current path Cohortscope uses (D10–D12, D14).

---

## 3. Where Cohortscope’s *dataset* practice differs

Relative to the table above — claim only what acquisition actually implements:

| Cohortscope choice | vs typical prior art |
|---|---|
| **Live** Rijksmuseum Search + Linked Art + IIIF (1500 px long edge) | vs frozen dumps / scrape mirrors |
| Paintings + oil paint + image-available filters (D10); no `technique` filter (D11) | Explicit medium gate; many challenges mix media |
| Main cohort = currently attributed Rembrandt oils; **exclude** circle/workshop/attributed labels from cohort stats (P03, D03–D04) | vs training a multi-class model on Rembrandt + pupils |
| Validation = description-probe circle / workshop / school / attributed, held out (D14) | Similar *intent* to RRP probes / questioned van Goghs, but as **anomaly checks against cohort normals**, not class accuracy |
| Single museum imaging pipeline (D01) | Reduces cross-institution confounds; smaller N than WikiArt |
| Expected validation N tiny (~1–3) | Must document before scoring; null result may be ambiguous (product vision risk) |

**Not claimed here as novel dataset practice alone:** using Rembrandt, using Rijksmuseum, or holding out disputed attributions. Those are established. The project’s novelty framing (for later write-up) is the **two-signal decomposable outlier score on that live split** — contingent on T043, not asserted in this note.

---

## 4. Implications for Phase 1 acquisition / inventory

1. **Record provenance:** object ID, query that found it, label text, split (`cohort` | `validation` | `excluded`), IIIF size — judges compare us to dump-based challenges.
2. **Do not silently mix dump + live:** pick live API path and stick to it for reproducibility narrative.
3. **Document tiny validation N in `results/` inventory** before Phase 4 — prior forensic sets were also small; honesty is expected.
4. **O05 (attributed-to):** prior work treats ambiguous labels carefully (exclude from accuracy or score as probe). Resolve with human before contaminating cohort normals.

---

## 5. Citations (short)

1. C. R. Johnson Jr. et al., “Image processing for artist identification: Computerized analysis of Vincent van Gogh’s painting brushstrokes,” *IEEE Signal Processing Magazine*, 25(4), 2008. https://doi.org/10.1109/MSP.2008.923513  
2. T. Mensink & J. van Gemert, “The Rijksmuseum Challenge: Museum-Centered Visual Recognition,” ACM ICMR, 2014. Dataset: https://doi.org/10.21942/uva.5660617  
3. A. Reuter, “Original or Pupil? Possible applications of Artificial Intelligence in attribution issues using the example of the Rembrandt Research Project,” *Kunstgeschichte. Open Peer Reviewed Journal*, 2023. https://www.kunstgeschichte-ejournal.net/601/  
4. Rijksmuseum Data Services (Search / dumps / open data policy): https://data.rijksmuseum.nl/  
5. WikiArt-derived multi-painter recognition (representative): e.g. arXiv:2304.14773 and common Kaggle/WikiArt subsets — web-scale scrapes, not museum Linked Art.

---

## 6. Hand-off

- **Data Engineer:** inventory report should cite expected tiny validation N and explicit split column (Phase 1 exit).  
- **Literature next:** T034 (wavelet / brushstroke method prior art + novelty statement), after features design firms up.  
- **Do not block** acquisition on this note.
