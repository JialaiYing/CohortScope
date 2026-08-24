## Inspiration

The first real test I ran told me the model was worse than a coin flip.

I had a ranking that flagged Rijksmuseum paintings as visually anomalous against a cohort of firmly attributed Rembrandts. It looked reasonable. The one held-out work I had scored `weak`, which is not a win but is not nothing either. So I went and harvested 67 paintings by documented Rembrandt pupils, the people who trained in his studio and painted in his manner, and ran them through. If the method worked at all, those should have surfaced.

AUC 0.419. Chance is 0.500. Precision at every _k_ I checked was below the base rate, which means a curator using my shortlist would have done better drawing names out of a hat.

That was disappointing but not interesting. What made it interesting was the confound check I had committed to running before I saw any of it. One of the columns I was required to test was `mm_per_px_analyzed`, which is just millimetres of canvas per pixel, a number describing how the museum photographed the object. On its own, with no model involved, it separated Rembrandts from pupils at **AUC 0.590**.

A column about the camera beat my entire two-signal pipeline.

I sat with that for a while, because it has an unpleasant implication. My model was not failing to find a weak signal. It was finding something, and the something was closer to photography metadata than to painting. The obvious next question was how that was even possible, and the answer turned out to be sitting in plain sight in every image file I had.

A JPEG hides physical scale completely. A 1500 pixel wide image looks like a 1500 pixel wide image whether the painting is a 15 centimetre panel or a 4 metre canvas. The pixels are commensurable. The things they depict are not. And a seventeenth-century brushstroke is roughly 0.3 to 3 millimetres wide, so whether a brushstroke exists in your image at all depends entirely on a quantity that no standard computer vision pipeline ever looks at:

$$\text{mm per pixel} = \frac{10 \times \text{canvas width in cm}}{\text{image width in pixels}}$$

I stopped trying to make the ranking work and started measuring what my images actually contained.

## What it does

CohortScope ranks Rijksmuseum Rembrandt oil paintings by how anomalous they look against a firm-attribution cohort, using a pretrained ResNet50 embedding (Signal A) and eight handcrafted texture and colour statistics (Signal B). Every row keeps both signals separately along with the named features that drove the score, so a flag reads as "flagged for gradient magnitude variance" rather than just "flagged".

**That ranking does not work, and the repository says so everywhere it appears,** including in the demo viewer's own banner. What the project actually delivers is the diagnosis and the tool that came out of it.

### The measurement

`dimensions.py` records catalogued canvas size, native IIIF pixel dimensions, analysed pixel dimensions, and the derived millimetres per pixel for all 108 works. The resulting audit is the centre of the project:

```
Stage                              mm of canvas per pixel   finer than 0.30 mm/px
-------------------------------------------------------------------------------
native IIIF, as published            0.015  to   0.812            85 / 108
the analysed derivative              0.100  to   3.467            19 / 108
the CNN input, after resize+crop     0.586  to  16.058             0 / 108
```

Zero out of 108. After a completely standard 256-resize and 224-crop, not one painting in the corpus reached brushstroke scale. The ResNet50 had never seen a brushstroke on any work in the dataset. Across the corpus, only **6.3 percent** of the resolution the museum already publishes was ever downloaded, and the analysed images varied **35-fold** in physical scale, so two files with identical dimensions could differ by more than an order of magnitude in what a pixel covered.

### The tool

Once you can measure that, you can answer a different and more useful question: _is this painting analysable at all from published imagery?_

```bash
python tiles.py --plan
```

Runs offline in under half a second against the committed database and returns a per-work verdict at a 0.20 mm/px floor. **64 of 108 works are answerable. 44 are not**, each with the reason it failed. Six of the physically largest firm Rembrandts fall out, including the Night Watch at 0.310 mm/px native, which takes the cohort from 23 works to 17.

Losing the Night Watch to my own eligibility rule felt bad and is the correct behaviour. Scoring it on inadequate pixels would have produced a number, and the number would have meant nothing.

### The record

Five pre-registered held-out outcomes, each with a design document committed to git _before_ the data it judges existed:

```
Test  Question                                                    AUC        Verdict
-----------------------------------------------------------------------------------
O04   Does one workshop work clear the cohort 95th percentile?     n/a       weak
O06   Does the ranking separate 67 documented pupils?             0.419      FAIL
O09   Does Signal B work once every pixel means 0.20 mm?          0.469      FAIL
O11   Does Signal A work at 0.20 mm/px, no resize or crop?        0.523      FAIL
O13   Was 0.20 simply the wrong scale? Sweep 0.15 to 0.30.        0.453-0.530 FAIL
```

And in all four pupil tests, the same kind of metadata column kept beating the model: **0.590, then 0.689, then 0.705, then 0.617.**

## How I built it

Python 3.13, PyTorch with CUDA on an RTX 3050, scikit-image and scipy for the handcrafted features, SQLite for metadata, and a static HTML findings page generated from committed artifacts. Flat modules at the repository root, no framework, no service layer.

**Data.** Rijksmuseum open collection API, no key required, filters locked in `config.py` and never changed after the first harvest. 108 scored works. Splits are assigned by priority rules over catalogue text rather than by hand: circle, workshop and school phrases go to `validation`, "attributed to" goes to `ambiguous`, and works whose creator matches a documented pupil roster go to `pupil`. Machine-readable provenance is a weaker label than expert judgement and a much more independent one, since deciding case by case which works "look like" workshop pieces would make the labels a function of the same visual intuition the model was supposed to test.

**Recipe contract.** Every stage has a frozen `RECIPE_ID` that names its output directory and is written into a `manifest.json`. Downstream stages assert the upstream recipe ID and take their worklist from that manifest, never from a filesystem glob or a fresh database query. Changing a recipe means bumping the ID and rerunning everything below it, not editing an output in place. Eleven recipes ended up in the final pipeline and none of them ever silently disagreed about which works they were processing.

**Two preprocessing branches that never cross.** One writes EXIF-corrected identity RGB whose only consumer is the handcrafted feature extractor. The other writes resized, cropped and ImageNet-normalised tensors whose only consumer is the CNN. Handcrafted features are therefore never computed on tensors a CNN transform has already distorted.

**Leakage control by construction.** Cohort works are scored leave-one-out: the centroid and the mean and standard deviation used to score work \\(i\\) come from the other 22. What is less standard is that every fit path branches on the split:

```python
# score.py — a split added later is non-fitting by construction,
# not by someone remembering to filter.
if meta[oid]["split"] == "cohort":
    mu, sigma = loo_stats(oid)      # leave-one-out
else:
    mu, sigma = full_cohort_stats   # never contributes to a fit
```

When I added the pupil split months later, it could not have leaked into a fit even if I had wanted it to.

**The fix for the scale problem.** IIIF serves arbitrary regions at arbitrary sizes, so instead of downloading one fixed-pixel image per painting I fetch 20 tiles, each covering 30 mm by 30 mm of canvas delivered at 150 by 150 pixels. Every tile is 0.20 mm/px on a 15 centimetre panel and on a 4 metre canvas alike. Tile positions are evenly spaced over the grid with no randomness, so the same database yields the same tiles every run.

Signal B was then recomputed on those tiles by calling the _same_ feature function with the _same_ constants. The only difference between arms is what a pixel means, which is the experimental control. For Signal A the tile size is arithmetic rather than a choice: 224 pixels fixed by the backbone, times the locked floor, so \\(224 \times 0.20 = 44.8\\) mm of canvas. Because the region arrives at the backbone's native input size, the embedding stage applies **only ImageNet normalisation. No resize, no crop, no interpolation of any kind.**

**Every ΔAUC re-fits its own baseline.** When I compare tiled Signal B against the fixed-pixel version, the fixed-pixel number is recomputed from scratch on the same 55 works rather than quoted from the earlier report. Otherwise the two arms differ in population as well as in pixels and the comparison means nothing.

**Reproducibility.** Everything except two regenerable caches is committed, so a clone reproduces the entire result with no network access. Stages refuse to overwrite existing outputs without `--force`. Verification is re-running a stage and diffing its manifest against the committed one. Every number on the findings page is read out of a committed artifact at build time rather than typed in, so if a figure on the page is wrong, the artifact it came from is wrong.

## Challenges I ran into

### A bug that would have invented data, caught with about an hour to spare

The final experiment sweeps the resolution floor across 0.15, 0.20, 0.25 and 0.30 mm/px to answer whether 0.20 was simply the wrong scale. Before fetching any tile I ran a verification pass over the eligibility logic, and found that the function deciding which paintings qualify was testing against the hardcoded 0.20 constant rather than the floor the current recipe was asking for.

At floor 0.15 that would have admitted paintings whose published resolution is coarser than 0.15 mm/px. The IIIF server does not refuse those requests. **It upsamples to fill the region.** It would have handed me a 150 by 150 pixel tile that looked exactly like every other tile and contained detail that was never photographed.

Inventing resolution is the precise failure this entire line of work exists to prevent, and my own sweep was about to do it silently, in a run I would have had no reason to distrust. The fix moves the floor onto the recipe object and makes the geometry unfakeable:

```python
def __post_init__(self):
    derived = self.size_px * self.floor_mm_per_px
    if abs(derived - self.size_mm) > 1e-6:
        raise ValueError(
            f"{self.recipe_id}: the tile size is derived from the floor, "
            "not chosen independently of it."
        )
```

Then I re-ran both already-published tile recipes and confirmed they reproduced with zero differences before fetching a single new tile.

I have thought about that one a lot. The result would have been a clean curve, in a report with a pre-registration attached, and completely fake.

### A gap in my own pre-registration, found at the worst possible moment

Computing tile features, 77 tiles came back with an undefined value for `hue_circ_std`, the circular standard deviation of hue. Perfectly explicable: that feature needs at least one pixel with meaningful colour saturation, and 77 tiles happened to land on near-grey passages of paint.

The design document said nothing about it. The obvious fix was to drop those tiles.

I checked the drop rate first, and it was 7 of 17 cohort works against 11 of 38 pupils. **Class-correlated.** Dropping them would have been content-based filtering at different rates for the two classes I was trying to compare, which the design explicitly forbids for exactly this reason.

So before computing a single aggregate, z-score or AUC, I wrote a dated addendum to the pre-registration: a tile is never dropped for what it depicts, each work-level median is taken over the tiles where that feature is defined, and if a feature is undefined on every tile the work is dropped and the loss recorded. I wrote down the rejected alternative and why. _Then_ I ran the numbers.

The sequencing is the entire value of it. That same rule, written after seeing which direction the AUC moved, would have been worthless.

### A confound rule that fired in a way it was never designed for

My pre-registered rule said a result is confounded if any metadata column achieves an AUC at or above the pipeline's. Sensible, until the pipeline scores 0.469, below chance, at which point literally any column sitting near chance trivially "beats" it and the rule fires vacuously.

I did not amend the rule. I reported the breach literally as written and added a paragraph explaining that the clause exists to override an otherwise-positive result, which is not the situation here, and that the substantive confound is the one scoring 0.689 rather than the ties at 0.50. Editing a locked rule the first time it behaved awkwardly would have set the precedent that locked rules are negotiable, which is worth more than any single clean paragraph.

### The experiment I wanted was mathematically impossible

I wanted to sweep resolution from 0.05 to 0.40 mm/px on a fixed population. Eligibility turns out to be **non-monotonic** in the floor: a coarser floor admits more paintings by the resolution test while excluding more by the "20 tiles must fit on the canvas" test. So the eligible sets are not nested, and the intersection across 0.05 to 0.40 is 6 works for Signal B and _zero_ for Signal A.

Re-deriving the population at each floor would have been easy and would have confounded resolution with which paintings entered the sample, producing a curve nobody could interpret. Holding the population fixed cost me sample size and narrowed the range to 0.15 to 0.30, and it is the only version of the experiment that answers the question I asked.

## Accomplishments I'm proud of

### Publishing five failures without softening any of them

Not one threshold in this repository was edited after seeing a result. That claim is checkable, and it is checkable by anyone with the repo:

```bash
git log --format='%h %ad %s' --date=short
# c17f78b 2026-08-23 Pre-register the resolution-floor sweep (D37) ...
# ebd42ca 2026-08-23 Sweep the resolution floor (D37); O13 = fail ...
```

Pre-register, then result, then pre-register, then result. Five times over.

The clearest test of it came early. My pupil pre-registration contained a clause forbidding re-splitting a work already claimed by an earlier phase. When I ran the harvest, that clause cost me three usable pupil paintings, on a project where sample size was the thing I most needed. Amending it after seeing which three would have been a post-hoc edit to a pre-registered rule, so I did not, and the loss is recorded in the report instead of quietly fixed.

### Building the multiplicity correction before it could favour me

The final sweep runs eight tests, four floors by two signals. Reading the best of eight against an uncorrected interval inflates the false-positive rate to

$$1 - (1 - 0.05)^{8} \approx 0.34$$

which is a very comfortable way to find a result that is not there. So the design locked a Bonferroni correction to a 99.375 percent interval before any point existed, and both intervals are computed from the same bootstrap draws at every point so the correction cannot be applied selectively to a winner.

In the end it did not matter, and I like that it did not matter. All eight corrected intervals contain chance, and so do all eight _uncorrected_ ones. Not a single point cleared even the unadjusted bar. The correction never had to do any work, which is the only circumstance under which nobody can accuse it of having been chosen conveniently.

### Reporting the number that made my best result look worse

The largest movement any change produced in this project was Signal A on commensurable pixels, ΔAUC of **+0.132**. That is a real headline if you want one. It is also the number where I most had to watch myself, because the honest reading is that the fixed-pixel arm was clearly _below_ chance at 0.391 and physically commensurable pixels brought it back _to_ chance at 0.523. The confidence interval runs from \\(-0.092\\) to \\(+0.352\\) and contains zero.

My first draft of that paragraph said "the signal improved". I rewrote it, because it did not improve, it stopped being actively wrong, and those are different claims.

### Excluding the Night Watch

The eligibility floor removes the six physically largest firm Rembrandts, the most famous painting in the collection among them, and takes my cohort from 23 works down to 17 in the process. Every instinct said carve out an exception for the flagship object. Reporting a painting as unanswerable from published imagery is a more honest and more useful answer than returning a confident-looking number computed from pixels that cannot support the question, and a rule with a celebrity exemption is not a rule.

### Being specific about the failure

"Our model did not work" is worth nothing. What this project can actually say is: the method fails, here is the AUC and its interval at each of eight resolutions, here is the metadata column that beat it in all four tests, here is the arithmetic showing zero of 108 paintings ever reached brushstroke scale at the network input, and here is a checker that tells you which paintings could ever answer this question. **That is a negative result somebody else can build on.**

## What I learned

**Pixels are not a unit of anything.** Every metric I had was computed over a corpus that varied 35-fold in physical scale, and nothing in a normal pipeline surfaces that. Accuracy, AUC and loss all report happily on incommensurable inputs. I now think "what does one pixel physically cover, and how much does that vary across my dataset" is a question worth asking on any dataset of photographs of real objects, and I had never once asked it before this project.

**A metric cannot distinguish "the model cannot separate these classes" from "the model was never shown the evidence".** Those two produce identical numbers and demand completely different responses. The first says try a better model. The second says your model is fine and your data collection is the problem. Six months of architecture search would not have distinguished them, and one afternoon of recording canvas dimensions did.

**Pre-registration is a tool for the moment you are on your own.** It sounds like bureaucratic overhead until you are alone at 1am looking at a rule that just cost you three samples, with nobody to notice if you widen it. The document is not there to convince a reviewer. It is there so that the version of you that has seen the data does not get a vote.

**Capture data and change scores in separate commits.** The decision to record physical geometry while explicitly not letting any scoring stage read those columns felt overcautious when I made it. It is the reason the diagnosis is credible. It changed no number and it explained every number, and if I had bundled it with a scoring change I would never have been able to attribute the difference to either one.

**A confound that beats your model is a pointer, not an embarrassment.** The 0.590 was the most useful number in the project. Everything worth reporting came out of taking it seriously rather than filing it as noise.

**Knowing when to stop is a result.** After the sweep came back flat at eight points, the tempting move was a sixth variant: a different backbone, a different aggregation, a different tile count. I wrote into the repository that no sixth variant should be proposed without new evidence, and that the imagery required to test a finer hypothesis does not exist in this collection, since nine works in the entire corpus have imagery finer than 0.05 mm/px and zero of them support a full sweep for the embedding signal. Closing a question is a contribution. Keeping it open by trying variants until one clears a threshold is how irreproducible results get made.

## What's next for CohortScope

**Make the adequacy checker a standalone tool.** The eligibility verdict is the piece that generalises. It depends on IIIF metadata and catalogued dimensions, not on Rembrandt, not on my features, and not on the ranking being correct. A digitisation team pointing it at their own collection would get back a straight answer to "is our imagery good enough for this class of analysis, and if not, what would we need to re-photograph". That is a real question with a budget attached, and right now the tool that answers it is hardcoded to one museum's API and one artist's corpus.

**Ask museums to publish millimetres per pixel in the manifest.** Every number in this project came from joining catalogued canvas dimensions in centimetres against IIIF `info.json` pixel dimensions, and both are already public. Nobody publishes the ratio, so nobody computes it, so every downstream analysis silently inherits the problem I spent a month finding. It is one derived field.

**Do not build a sixth variant of the method.** The honest next scientific step is not a different backbone on the same imagery. It is raking-light or macro photography at 0.05 mm/px or better, which exists for individual famous paintings and not for corpora, combined with a representation trained on handling rather than on object categories, and a held-out set an order of magnitude larger with provenance-grade labels. Those are research programmes rather than a next sprint, and none of them is reachable by retuning what is in this repository. Saying so plainly is part of the deliverable.

**The one open statistical question I would answer first.** My samples are 40 and 35 in the sweep, which is well powered for a large effect and badly powered for a small one. Failing to find an effect is not the same as showing there is none, and the intervals are wide enough to admit a real AUC around 0.65 at some floors. The claim I actually defend is narrow, that no effect large enough to be useful for triage was detectable under these conditions, and the way to tighten it is more paintings above the floor rather than more clever scoring of the ones I have.

---

**Repository:** [github.com/JialaiYing/CohortScope](https://github.com/JialaiYing/CohortScope) · **Findings page:** [jialaiying.github.io/CohortScope](https://jialaiying.github.io/CohortScope/) · **Full report:** [`results/datathon_report.md`](https://github.com/JialaiYing/CohortScope/blob/main/results/datathon_report.md)
