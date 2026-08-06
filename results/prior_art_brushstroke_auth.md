# Prior art: brushstroke / wavelet auth vs Cohortscope novelty

**Task:** T034 · **Role:** literature · **Date:** 2026-08-06  
**Companion:** `results/prior_art_dataset_practices.md` (corpus/split only).  
**Aligns with:** proposed O03 shortlist in `results/phase3_feature_shortlist.md` (8 scalars; **no** wavelet banks in v1).  
**Claim gate:** Framing only. Empirical “works” waits on T043 / T045.

---

## 1. What is already done (do not claim as new)

| Lineage | What they did | Takeaway |
|---|---|---|
| Wavelet / multi-scale brushwork (Johnson et al. 2008; related van Gogh / Duke groups) | Wavelet & related descriptors on **controlled high-res museum scans**; authentic vs non / questioned | Gold-standard computational auth assumes forensic imaging + classical texture |
| Digital authentication stats (Lyu, Rockmore & Farid 2004) | Handcrafted image statistics for artist separation / forgery | Non-deep, statistics-first auth predates CNNs |
| Explicit brushstroke geometry (e.g. Berezhnoy et al. 2008) | Stroke orientation / extraction as named physical proxies | “Brushstroke features” as interpretable signals is established |
| Deep artist recognition (WikiArt baselines; Rijksmuseum Challenge; Reuter 2023 Rembrandt+pupils) | Supervised multi-class (often CNN/ResNet-style); sometimes probe disputed attributions after training | Embeddings + Rembrandt-workshop ML are **not** novel |
| Museum open-data CV (Mensink & van Gemert 2014) | Creator / type / material / year on Rijksmuseum dumps | Using Rijksmuseum for ML is standard |

**Honest sentence for judges:** Computational brushstroke authentication and museum-attribution ML are mature. Wavelets, texture stats, and CNN artist classifiers already exist. Cohortscope does **not** invent brushstroke analysis, wavelet auth, or Rembrandt ML.

---

## 2. What Cohortscope adds (intended novelty)

Product vision / D05 — **two-signal decomposable cohort anomaly on a live open corpus**, with a held-out reattribution-style check:

1. **Cohort normals, not a multi-class head** — Fit on currently attributed Rembrandt oils only; score distance-to-cohort. Circle / workshop / school works are **held-out probes**, not training classes (contrast Reuter: Rembrandt + pupils as supervised labels).
2. **Two reportable signals** — (A) pretrained ResNet50 embedding distance (no finetune by default, D13); (B) short hand-built texture / brushstroke / palette scalars (O03: gradients, Laplacian, LBP entropy, GLCM contrast, Lab chroma, hue spread — **not** a Johnson wavelet bank). Ranks must show **which signal drove** the flag (D05).
3. **Live Rijksmuseum Search → Linked Art → IIIF** — Oil-painting filters, explicit split enum, inventory provenance — vs frozen dumps or RKD scrapes (T016).
4. **Triage framing** — Ranked candidates for human re-examination, not a replacement for conservators.

**Compression:** Prior art often asks “which artist?” or “authentic vs fake?” on curated scans. We ask “which works look anomalous vs *this museum’s current Rembrandt cohort*, and *why* (embedding vs hand-built)?”

---

## 3. Explicit non-claims / limits

- We are **not** reproducing Johnson-style wavelet forensics on 16-bit ~196 dpi scans. Branch H @ IIIF ~1500 px (D12/D27) is weaker for fine stroke microstructure — say so in the report.
- v1 hand-built features deliberately skip wavelet packet banks (O03 rejected list); they are **explainable proxies**, not forensic-parity brushwork analysis.
- Tiny validation N (inventory: validation=1, ambiguous=1) → a null or single hit is **weak/inconclusive**, not strong proof.
- If T043 fails or is inconclusive, write that plainly; novelty framing does not survive a failed validation gate.
- “Second artist without code change” is a **design claim** (T052), not demonstrated unless executed.

---

## 4. Novelty one-liner (Bonus / write-up)

> Brushstroke, wavelet, and CNN attribution methods are prior art; Cohortscope’s contribution is a **decomposable two-signal anomaly ranker** over a **live Rijksmuseum Rembrandt cohort**, counted as successful only if held-out circle/workshop works look unusually far from that cohort — contingent on Phase 4 outcomes.

---

## 5. Citations (short)

1. C. R. Johnson Jr. et al., “Image processing for artist identification…,” *IEEE Signal Processing Magazine*, 2008. https://doi.org/10.1109/MSP.2008.923513  
2. S. Lyu, D. Rockmore, H. Farid, “A digital technique for art authentication,” *PNAS*, 2004. https://doi.org/10.1073/pnas.0406398101  
3. I. Berezhnoy, E. Postma, H. van den Herik, “Automatic extraction of brushstroke orientation…,” *Machine Vision and Applications*, 2008.  
4. A. Reuter, “Original or Pupil?… Rembrandt Research Project,” *Kunstgeschichte OPJ*, 2023. https://www.kunstgeschichte-ejournal.net/601/  
5. T. Mensink & J. van Gemert, “The Rijksmuseum Challenge…,” ACM ICMR, 2014.  

Dataset-practice detail: `results/prior_art_dataset_practices.md`.

---

## 6. Hand-off

- **Features:** Keep few named scalars; do not imply Johnson-parity resolution or ship wavelet banks unless T043 fails and human reopens O03.  
- **Stats (T035/T040):** Decomposability is the literature hook — fusion must preserve per-signal drivers.  
- **Literature next:** T045 after validation; T051–T052 / T071 for full report.
