# Resolution audit

**Source:** `data/cohortscope.sqlite` (`works` geometry, Fix 1) · **N:** 108 scored works · **Generated:** `2026-08-20T00:55:45.208440+00:00`

Descriptive only — nothing here fits, scores, or selects a resolution floor.

## 1. What each pixel covers

A pixel is only meaningful in millimetres of canvas. Because every image was fetched at a fixed **width of 1500 px** regardless of how large the painting is, that quantity varies enormously across the corpus.

| Stage | mm per pixel (min – max) | median |
|---|---|---|
| native IIIF (what the museum publishes) | 0.015 – 0.812 (53×) | 0.179 |
| analyzed derivative (what `features_v1` measured) | 0.100 – 3.467 (35×) | 0.642 |
| CNN input (what `embed_v1` actually saw) | 0.586 – 16.058 (27×) | 3.655 |

A 17th-century oil brushstroke is roughly **0.3–3.0 mm** wide. Resolving one needs several pixels across it, so a stage whose mm/px approaches that range cannot represent handling at all — only composition and colour.

| Stage | works finer than 0.30 mm/px | works coarser than 1.00 mm/px |
|---|---:|---:|
| native | 85 / 108 | 0 / 108 |
| analyzed | 19 / 108 | 25 / 108 |
| CNN input | 0 / 108 | 102 / 108 |

## 2. Headroom left on the table

| Quantity | Value |
|---|---|
| native resolution published across the corpus | **4,408 MP** |
| resolution actually analyzed | **278 MP** |
| fraction of published pixels used | **6.3%** |
| per-work linear headroom (native is this much finer) | 1.6× – 9.8×, median 3.4× |

The detail needed to resolve brushwork was already published and free to request; the pipeline discarded it at download time, before any modelling decision was made.

## 3. What the CNN was given

`preprocess.py` resizes the short side to 256 px and centre-crops 224 px (Branch C). Two consequences follow from geometry alone, before any question about the backbone:

- **Resolution.** The CNN input spans 0.59–16.06 mm/px. At the coarse end one pixel covers 16.1 mm of canvas — wider than the broadest brushstroke (3.0 mm) by 5×, and than the finest (0.3 mm) by 54×. Not one work in the corpus reaches 0.3 mm/px at this stage.
- **Coverage.** The centre crop keeps 25%–76% of each picture (median 62%), and how much is discarded depends on aspect ratio, which adds a second uncontrolled variable.

This is the arithmetic reason Signal A scored AUC 0.427 against the pupil cohort (`results/pupil_validation_report.md`): at this input scale there is no brushwork left for the embedding to compare.

## 4. Eligibility census at candidate floors

How many works could support analysis at a given target resolution — from the native image, versus from the derivative the pipeline actually used.

| target mm/px | eligible at native | eligible in analyzed derivative |
|---|---:|---:|
| ≤ 0.05 | 9 / 108 | 0 / 108 |
| ≤ 0.10 | 24 / 108 | 1 / 108 |
| ≤ 0.15 | 46 / 108 | 3 / 108 |
| ≤ 0.20 | 64 / 108 | 10 / 108 |
| ≤ 0.25 | 78 / 108 | 15 / 108 |
| ≤ 0.30 | 85 / 108 | 19 / 108 |
| ≤ 0.40 | 96 / 108 | 38 / 108 |
| ≤ 0.50 | 102 / 108 | 46 / 108 |

Two different problems separate: 89 works are too coarse in the analyzed derivative but recoverable from the native image, whereas **23 works never reach 0.30 mm/px even at native resolution** — the museum has not published them finely enough for texture analysis at any download size. The first group is fixable by re-requesting; the second is only fixable by re-imaging, which is the actionable finding for a collection holder.

**No floor is selected here.** Picking one decides which works get scored and which are declared out of scope, so it is a design decision that must be pre-registered before the resulting numbers are seen — the same rule that governed O04 and O06.

## 5. D27 restated with real measurements

D27 recorded that Phase 1 requested `full/1500,` — a fixed **width**, not a fixed long edge — and flagged the consequence as documented-not-fixed. The catalogued sizes now quantify it:

- 83 of 108 works are taller than 1500 px in the analyzed derivative, so their long edge exceeds the nominal cap.
- More consequentially, fixing the **width** means physical scale tracks physical width: the widest work in the corpus is 520 cm and the narrowest 15 cm, a 35× range that maps directly onto the 35× mm/px spread above.

## 6. Per-work data

`results/resolution_audit.csv` — one row per scored work, ordered coarsest first.

### Coarsest 5 (analyzed)

| object | split | cm wide | native mm/px | analyzed mm/px | CNN mm/px | native px used |
|---|---|---:|---:|---:|---:|---:|
| `SK-C-1174` | pupil | 520 | 0.812 | 3.467 | 14.53 | 5.5% |
| `SK-A-1575` | pupil | 493 | 0.447 | 3.287 | 16.01 | 1.8% |
| `SK-C-5` | cohort | 454 | 0.310 | 3.023 | 14.72 | 1.0% |
| `SK-A-1576` | pupil | 413 | 0.376 | 2.753 | 16.06 | 1.9% |
| `SK-A-1579` | pupil | 409 | 0.358 | 2.727 | 15.84 | 1.7% |

### Finest 5 (analyzed)

| object | split | cm wide | native mm/px | analyzed mm/px | CNN mm/px | native px used |
|---|---|---:|---:|---:|---:|---:|
| `SK-A-4096` | ambiguous | 24 | 0.053 | 0.157 | 0.92 | 11.5% |
| `SK-C-127` | pupil | 23 | 0.053 | 0.152 | 0.89 | 12.1% |
| `SK-A-88` | pupil | 19 | 0.044 | 0.127 | 0.74 | 12.1% |
| `SK-A-89` | pupil | 17 | 0.039 | 0.115 | 0.67 | 11.5% |
| `SK-A-3982` | cohort | 15 | 0.015 | 0.100 | 0.59 | 2.3% |
