# Cohortscope — Product Vision & Roadmap

*(working name — swap it for anything you like, nothing downstream depends on it)*

## Problem

Museums publish huge open collections of high-resolution artwork photos with full metadata, but have no automated way to flag which pieces in their own collection might be misattributed. Physical re-examination (X-ray, infrared, pigment dating) is slow and expensive, so it only happens when a human already suspects a specific piece. There is no tool that scans an entire open collection and produces a ranked, explainable list of candidates worth that expensive process.

## Vision

A pipeline that takes a claimed-attribution group of paintings (Rembrandt, plus works historically attributed to his workshop or circle), measures each painting against the statistical "normal" of that group on two independent axes — general visual similarity and interpretable physical features (brushstroke texture, color palette) — and produces a ranked, explainable flag list instead of a single opaque score.

## Who this is for

Primary: competition judges evaluating the method's soundness and originality.
Secondary (real-world framing): museum curators and conservators triaging a large open collection with limited expert re-examination capacity.

## Value proposition

Turns "look at everything or nothing" into a sorted to-do list, built entirely from data the museum already published for free, with each flag traceable to a specific measurable reason.

## Scope — 13 days, paintings only, one artist

**In scope**
- Rijksmuseum collection only (single imaging pipeline, avoids cross-museum confounds)
- Paintings labeled "Rembrandt van Rijn" as the primary cohort
- Paintings labeled "circle of / workshop of Rembrandt" pulled separately, held out as a validation set (not part of the "normal" cohort)
- Two independent feature signals: pretrained-CNN visual embeddings + hand-built interpretable texture/brushstroke statistics
- A decomposable outlier score per painting (which signal drove the flag, not just a number)
- Validation step: does the system flag the circle-of/workshop-of paintings as anomalous relative to the Rembrandt cohort?

**Out of scope for now**
- Other artists, other museums, non-painting media (drawings, prints)
- Any frontend beyond what's needed to inspect results (Gradio, not Next.js — revisit after the method is proven; UX/Design judging criteria applies to that later phase, not this one)
- Model fine-tuning / training a custom backbone from scratch

## Success criteria (mapped to judging rubric)

| Criterion | What "done" looks like |
|---|---|
| Innovation | Two-signal decomposable scoring on a live open corpus, not a single-artist forensic study |
| Problem Solving | System recovers a meaningful fraction of the known circle-of/workshop-of paintings as anomalous, with a stated reason per flag |
| Sustainability/Scalability | Same pipeline runs on a second artist without code changes, even if not executed |
| UX & Design | Deferred by design this phase — result is a clean, legible ranked list, not a polished app |
| Bonus | Honest acknowledgment of prior art (wavelet-based brushstroke authentication) with a clear statement of what's actually new here |

## Roadmap

| Days | Milestone | Deliverable |
|---|---|---|
| 1–2 | Data acquisition | Rembrandt cohort + circle-of/workshop-of validation set downloaded and stored locally |
| 3–4 | Preprocessing | Images normalized (scale, lighting/color consistency) so scan differences don't masquerade as signal |
| 5–7 | Feature extraction | CNN embeddings + texture/brushstroke statistics computed for every image |
| 8–9 | Scoring + validation | Per-cohort outlier scores computed; check against the held-out validation set |
| 10–11 | Iterate + write-up | Fix what's broken, document results and methodology |
| 12–13 | Buffer | Always gets used — do not plan around not needing it |

## Known risks

- **API instability**: Rijksmuseum's data services documentation shows active changes as recently as this year — confirm the exact request/response shape against current docs before writing extraction code, don't assume the examples below are frozen.
- **Small validation set**: the circle-of/workshop-of cohort may be small enough that a null result (nothing flagged) is ambiguous rather than informative. Know this going in, don't be surprised by it.
- **Interpretability tradeoff**: hand-built texture features are more explainable but weaker than deep embeddings on subtle cases — this is a deliberate tradeoff to name explicitly in the write-up, not a flaw to hide.
