# CohortScope

Anomaly-detection pipeline for art attribution on the [Rijksmuseum](https://www.rijksmuseum.nl/) open collection: Rembrandt-attributed paintings vs held-out circle/workshop works, using two decomposable signals (pretrained ResNet50 embeddings + handcrafted texture/color features).

> Working name — subject to change.

## Dataset

- **Source:** Rijksmuseum Data Services (Search API + Linked Art resolve + IIIF). No API key required.  
  Docs: https://data.rijksmuseum.nl/docs/search  
- **Local snapshot in this repo:** `data/cohortscope.sqlite` + `data/images/` (~30 oil paintings; see `results/inventory.md`).  
- **Reproduce / refresh from the live API:**

```bash
mamba activate CohortScope
python acquire.py           # full harvest
python acquire.py --inventory
```

## Setup

```bash
mamba activate CohortScope   # or create env from Python 3.13
python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
python -m pip install -r requirements.txt
```

## Status

- **Phase 0–3 complete:** data, preprocess, ResNet50 embeddings, 8 hand-built features.  
- **Phase 4+** (scoring / validation / write-up): not started.  
- After each finished phase: cleanup + push to GitHub (D28).  
- Project docs: `docs/`.

## License / attribution

Rijksmuseum collection data and images are used under the museum’s open data terms. Attributions welcomed; see museum guidance on data.rijksmuseum.nl.
