# CohortScope

**A negative result about Rembrandt, and a resolution audit that explains it.**

CohortScope set out to rank Rijksmuseum Rembrandt oil paintings by how anomalous they look
against a firm-attribution cohort, using pretrained ResNet50 embeddings (Signal A) plus eight
handcrafted texture and colour features (Signal B). It ran five pre-registered held-out tests
over three weeks. Four of them failed, one was inconclusive at N=1, and the repository says so
in every report, in the decision log, and on the findings page.

The useful output is not the ranking. It is the reason the ranking cannot work: for most of
this collection, the published image does not carry a brushstroke.

**Findings page:** `results/dossier/index.html` (build with `python dossier.py`)
**Repo:** https://github.com/JialaiYing/CohortScope.git

---

## The five outcomes

| Test | What it asked | Works ranked | AUC | Verdict |
|---|---|---:|---:|---|
| **O04** | Does one circle/workshop work rank above the cohort p95? | 1 | n/a | `weak` |
| **O06** | Does the ranking separate 67 documented Rembrandt pupils? | 67 | 0.419 | **`fail`** |
| **O09** | Does Signal B work once every pixel means 0.20 mm of canvas? | 55 | 0.469 | **`fail`** |
| **O11** | Does Signal A work with no resize and no crop, at 0.20 mm/px? | 52 | 0.523 | **`fail`** |
| **O13** | Was 0.20 mm/px simply the wrong scale? Sweep 0.15 to 0.30. | 40 and 35 | 0.453-0.530 | **`fail`** |

Each outcome has a design document committed to git *before* the data it evaluates existed.
Thresholds, seeds and k values in the scoring code are transcribed from those documents. When
a locked rule cost samples (O06 lost three works to its own §3.1) the loss went into the report
rather than the rule being amended.

Reports: [`validation_report.md`](results/validation_report.md) ·
[`pupil_validation_report.md`](results/pupil_validation_report.md) ·
[`tile_validation_report.md`](results/tile_validation_report.md) ·
[`tile_embedding_report.md`](results/tile_embedding_report.md) ·
[`resolution_sweep_report.md`](results/resolution_sweep_report.md)

---

## Why it fails

The obvious explanations were tested and eliminated one at a time.

**"N was too small."** O06 raised held-out N from 1 to 67 by harvesting works by documented
Rembrandt pupils. The result got worse, not better: AUC 0.419, below chance, with precision@k
under the base rate. A ranking below base rate is worse than a random shortlist for triage.

**"The images were not comparable."** They were not. `dimensions.py` and
[`resolution_audit.md`](results/resolution_audit.md) put a number on it by recording catalogued
canvas size alongside native and analysed pixel dimensions for all 108 works:

| Stage | mm of canvas per pixel | works finer than 0.30 mm/px |
|---|---|---:|
| native IIIF, as the museum publishes it | 0.015 to 0.812 | 85 / 108 |
| the analysed derivative (`features_v1`) | 0.100 to 3.467 | 19 / 108 |
| the CNN input (`embed_v1`) | 0.586 to 16.058 | **0 / 108** |

A 17th-century brushstroke is roughly 0.3 to 3 mm wide. After a 256-resize and a 224 centre
crop, not one painting in the corpus reaches 0.3 mm/px. The ResNet50 never saw a brushstroke
on any work, which is a sufficient explanation for Signal A scoring at chance. Across the
corpus only 6.3% of the resolution the museum already publishes was ever downloaded, and the
spread between the coarsest and finest analysed work was 35-fold.

**"Fix the scale and it will work."** IIIF serves arbitrary regions at arbitrary sizes, so a
patch of known *physical* size can be fetched without downloading a gigapixel file. `tiles.py`
takes 20 tiles per painting, each covering 30 mm × 30 mm of canvas delivered at 150 × 150 px,
which is 0.20 mm/px on a 15 cm panel and on a 4 m canvas alike. Signal B was recomputed on
those tiles with the identical feature code and the identical constants, so the only thing that
differed between arms was what a pixel means. O09: AUC 0.469, still chance. Signal A got the
same treatment at 224 px tiles (44.8 mm of canvas, derived as 224 × 0.20) with ImageNet
normalisation and no geometric step at all. O11: AUC 0.523, still chance.

**"0.20 was the wrong scale."** `sweep.py` re-ran both signals at 0.15, 0.20, 0.25 and 0.30
mm/px, holding each signal's pixel count fixed so only millimetres per pixel varied, and holding
the *population* fixed across floors so resolution was not confounded with which paintings
entered the sample. Eight points, all within 0.047 of chance, with Bonferroni correction applied
at every point from the same bootstrap draws. O13: `fail`, and the curve is flat rather than
noisy-but-trending.

**What did separate the classes.** In all four pupil tests a single acquisition-metadata column
beat the entire pipeline: `mm_per_px_analyzed` at AUC 0.590 in O06, then `mm_per_px_native` at
0.689, 0.705 and 0.617. The model was, at best, reading how the photograph was taken.

---

## The part that does work: the adequacy checker

The reusable deliverable is a per-work verdict on whether the question is answerable at all.

```bash
python tiles.py --plan
```

Runs offline in under a second against the shipped SQLite database. It reports **64 of 108
works eligible** at the 0.20 mm/px floor and **44 below floor**, each with the reason it failed.
The six physically largest firm Rembrandts fall out, the Night Watch among them at 0.310 mm/px
native, which takes the cohort from 23 to 17.

That exclusion is the point. Reporting a painting as unanswerable from published imagery is a
more honest and more useful answer than scoring it on pixels that cannot support the question.
Eligibility is derived at query time and never stored on the `works` table, because the table
holds measured facts while the floor is policy, and cached policy goes stale without saying so.

---

## Setup

```bash
mamba activate CohortScope   # Python 3.13; developed with CUDA torch on an RTX 3050
python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
python -m pip install -r requirements.txt
```

CPU torch is fine for reproduction. `embed.py` uses CUDA when it finds it.

## Pipeline

Stages run in order; each reads the previous stage's `manifest.json` for its worklist rather
than re-globbing the filesystem. Shipped artifacts already exist in the repo, so pass `--force`
only when you mean to overwrite them.

```bash
python acquire.py          # Rijksmuseum API  → data/cohortscope.sqlite, data/images/
python preprocess.py       #                  → data/preprocessed/preprocess_v1/
python embed.py            # ResNet50         → data/embeddings/embed_v1/
python features.py         # 8 scalars        → data/features/features_v1.csv
python score.py            #                  → results/scores/, validation_report.md   (O04)
python dimensions.py       # geometry backfill for pre-D33 rows; no-op after a fresh harvest
python evaluate_pupils.py  #                  → results/pupil_validation_report.md      (O06)
python resolution_audit.py #                  → results/resolution_audit.{md,csv}
```

Physically normalised arms:

```bash
python tiles.py            # 150 px / 30 mm tiles → data/tiles/tiles_v1/, tiling_report.md
python tile_features.py    #                      → data/features/tile_features_v1.csv
python tile_score.py       # Signal B             → results/tile_validation_report.md   (O09)

python cnn_tiles.py        # 224 px / 44.8 mm tiles for the backbone
python tile_embed.py       #                      → data/embeddings/tile_embed_v1/
python tile_score_a.py     # Signal A             → results/tile_embedding_report.md    (O11)

python sweep.py --plan     # population census, offline
python sweep.py --fetch    # 4,800 sweep tiles, roughly 85 minutes, resumable
python sweep.py            #                      → results/resolution_sweep_report.md  (O13)

python dossier.py          #                      → results/dossier/index.html
```

`acquire.py` needs network and takes `--dry-run`, `--inventory` and `--pupils-only`.
`--pupils-only` adds the pupil cohort additively against an existing database, leaving every
existing row and image byte-identical, which is much safer than a full re-harvest.
`dimensions.py` also needs network; nothing else does.

There is no test suite and no CI. Verification is by re-running a stage with `--force` and
diffing its manifest against the committed one.

---

## How the repository is organised

Flat Python modules at the repository root, documentation in `docs/`, artifacts in `data/` and
`results/`.

Three conventions carry most of the weight:

**Recipe IDs.** Every stage has a frozen `RECIPE_ID` that names its output directory and is
written into its manifest. Downstream stages assert the upstream ID and take their worklist
from it. Changing a recipe means bumping the ID and rerunning everything below it, never
editing an output in place.

**Two disjoint preprocessing branches.** `rgb/*.png` is EXIF-corrected identity RGB and its
only consumer is `features.py`. `cnn/*.pt` is resized, cropped and ImageNet-normalised and its
only consumer is `embed.py`. Handcrafted features never read CNN tensors and the CNN never
reads the RGB branch.

**Numbers are read, never transcribed.** `dossier.py` pulls every figure on the findings page
out of a committed artifact at build time. If a number on the page is wrong, the artifact it
came from is wrong. Regenerating is the entire update path.

| What | Where |
|---|---|
| Locked decisions D01 to D38 | [`docs/decisions.md`](docs/decisions.md) |
| Task board and phase plan | [`docs/tasks.md`](docs/tasks.md), [`docs/roadmap-phase-plan.md`](docs/roadmap-phase-plan.md) |
| Pre-registrations | `results/phase{4,7,8,9,10,11}_*_design.md` |
| Outcome reports | `results/*_report.md` |
| Findings page | `results/dossier/index.html` |
| Ranked scores and fit manifest | `results/scores/` |
| QC logs, one directory per recipe | `results/qc_*/` |

Two directories are gitignored because they regenerate exactly: `data/preprocessed/` (about
340 MB, rebuilt byte-identically by `python preprocess.py`) and `data/tiles/` (rebuilt from
IIIF by `python tiles.py`). Everything else in `data/` is tracked, so a fresh clone reproduces
the whole result with one preprocessing command and no network.

---

## Dataset

Rijksmuseum open data, no API key. Filters are locked in `config.py`: `type=painting`,
`material=oil paint`, `imageAvailable=true`.

108 scored works across four splits assigned by priority rules in `acquire.py`. Circle,
workshop and school phrases go to `validation`; "attributed to" goes to `ambiguous`; works whose
creator matches a documented pupil go to `pupil`. Statistical normals are fitted on
`split=cohort` alone, and `score.py` enforces that structurally by branching on the split at
every fit path, so a newly added split is non-fitting by construction. Cohort works are scored
leave-one-out so no painting contributes to the normal it is measured against.

| Item | Location |
|---|---|
| Museum API documentation | https://data.rijksmuseum.nl/docs/search |
| Metadata, splits and geometry | `data/cohortscope.sqlite` |
| Images, IIIF at about 1500 px | `data/images/{object_number}.jpg` |
| Inventory | [`results/inventory.md`](results/inventory.md) |

---

## Demo viewer (optional)

```bash
python demo_app.py
```

A read-only Gradio view over `results/scores/scores_v1.csv` and `data/images/`. It recomputes
nothing and its banner states the outcome plainly. It exists as a presentation aid, not as a
product claim, and the ranking it displays is the one the five tests say does not work.

---

## Scope that stays closed

Deferred deliberately and not to be reopened without new evidence: a FastAPI service layer,
DINOv2 or other backbones, finetuning, multi-museum cohorts, and folding "attributed to" works
into primary validation. A sixth variant of the same method is not on the list either. Five
tests at chance across a 2x resolution range is not a tuning problem.

## License and attribution

Rijksmuseum collection data and images are used under the museum's open data terms; see
https://data.rijksmuseum.nl/. Analysis code in this repository is the author's own.
