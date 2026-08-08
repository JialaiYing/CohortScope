# CohortScope

Decomposable anomaly ranking for Rijksmuseum Rembrandt oils: pretrained ResNet50 embeddings + handcrafted texture/color features, scored against a firm-attribution cohort (held-out circle/workshop validation).

**Repo:** https://github.com/JialaiYing/CohortScope.git

**Status:** Phases 0–5 done. Validation **O04 = `weak`** (N=1; see [`results/validation_report.md`](results/validation_report.md)). Science deliverable is **tables/CSV**; an optional read-only Gradio **demo viewer** exists for the human demo video (D31) — not a product claim.

---

## Dataset

| Item | Location |
|---|---|
| Museum open data / Search API docs | https://data.rijksmuseum.nl/docs/search |
| Local metadata (splits) | `data/cohortscope.sqlite` |
| Local images (IIIF ~1500 px width) | `data/images/{object_number}.jpg` |
| Inventory | [`results/inventory.md`](results/inventory.md) |

No API key. Filters: `type=painting`, `material=oil paint`, `imageAvailable=true` (see `config.py`). Split rules: `cohort` \| `validation` \| `ambiguous` \| `excluded` (D19–D21).

**Refresh from the live API** (rewrites SQLite + images; network required):

```bash
mamba activate CohortScope
python acquire.py
python acquire.py --inventory
```

Downstream steps use scored splits only (`cohort` ∪ `validation` ∪ `ambiguous`, N=25 in the shipped snapshot).

---

## Setup

```bash
mamba activate CohortScope   # Python 3.13; CUDA torch used in development (RTX 3050)
python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
python -m pip install -r requirements.txt
```

CPU torch also works for reproduce; `embed.py` picks CUDA if available.

---

## Full pipeline (order)

Run from repo root with the env active. Shipped artifacts already exist; use `--force` only when you intend to overwrite.

```bash
python acquire.py          # → data/cohortscope.sqlite, data/images/
python preprocess.py       # → data/preprocessed/preprocess_v1/
python embed.py            # → data/embeddings/embed_v1/
python features.py         # → data/features/features_v1.csv
python score.py            # → results/scores/, results/validation_report.md
```

Optional flags: `--dry-run` / `--inventory` on `acquire.py`; `--force` on preprocess / embed / features / score.

---

## Where outputs land

| Stage | Path |
|---|---|
| SQLite + raw JPEGs | `data/cohortscope.sqlite`, `data/images/` |
| Preprocess (Branch H RGB + Branch C 224 CNN) | `data/preprocessed/preprocess_v1/` |
| ResNet50 embeddings | `data/embeddings/embed_v1/` |
| Hand-built features | `data/features/features_v1.csv` (+ dictionary/manifest) |
| Ranked scores + fit manifest | `results/scores/scores_v1.csv`, `results/scores/fit_manifest.json` |
| Validation outcome | [`results/validation_report.md`](results/validation_report.md) |
| QC logs | `results/qc_preprocess_v1/`, `results/qc_embed_v1/`, `results/qc_features_v1/` |

---

## Reports

| Doc | Role |
|---|---|
| [`results/datathon_report.md`](results/datathon_report.md) | Datathon write-up (method, limits, sustainability) — Literature T071 |
| [`results/validation_report.md`](results/validation_report.md) | O04 / T043 outcome (`weak`) |
| [`results/phase4_review.md`](results/phase4_review.md) | Phase 4 leakage / scope gate (**PASS**) |
| [`results/phase4_results_narrative.md`](results/phase4_results_narrative.md) | Short Phase 4 honesty note |
| [`docs/`](docs/) | Decisions, tasks, agent briefs |

---

## Demo viewer (optional)

Read-only Gradio UI over `results/scores/scores_v1.csv` + `data/images/`. Does **not** recompute scores or claim the method works (O04 = `weak`).

_Purpose: presentation aid for the human demo video (T072). The science deliverable remains `results/scores/scores_v1.csv` and `results/validation_report.md` (tables/CSV)._

```bash
mamba activate CohortScope
python -m pip install -r requirements.txt   # includes gradio
python demo_app.py                          # local; share=False
```

Opens a local Gradio page: rank table, work detail (image + z_A/z_B + drivers), and a Validation spotlight for SK-A-3934.

---

## License / attribution

Rijksmuseum collection data and images under the museum’s open data terms. See https://data.rijksmuseum.nl/.
