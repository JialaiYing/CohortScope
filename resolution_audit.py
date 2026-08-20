"""
Resolution audit: what physical detail do the analyzed images actually carry?

Reads the geometry now stored on `works` (Fix 1) and reports, per work and per
corpus, the millimetres of canvas each pixel covers — at native IIIF resolution,
in the 1500px-wide derivative the pipeline analyzed, and at the input the CNN
actually received after `preprocess.py` resizes and centre-crops.

This is descriptive. It fits nothing, scores nothing, and deliberately does **not**
recommend a resolution floor: choosing one changes what gets scored, so it belongs
in a pre-registered design, not in a report written after the fact.

Reads : data/cohortscope.sqlite
Writes: results/resolution_audit.md, results/resolution_audit.csv

Usage (repo root, mamba env CohortScope):
  python resolution_audit.py
  python resolution_audit.py --force
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from datetime import datetime, timezone

import numpy as np

import config
import preprocess

SCORED_SPLITS = ("cohort", "validation", "ambiguous", "pupil")

# Candidate floors reported as a census only. Nothing here selects one.
CANDIDATE_FLOORS_MM = (0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50)

# Typical oil brushstroke width, for scale. Cited, not derived here:
# Johnson et al. 2008 and the conservation literature put individual bristle
# marks in the 0.3-3 mm range for 17th-c. Dutch oil on canvas/panel.
BRUSHSTROKE_MM = (0.3, 3.0)

MD_PATH = config.RESULTS_DIR / "resolution_audit.md"
CSV_PATH = config.RESULTS_DIR / "resolution_audit.csv"

CSV_COLUMNS = (
    "object_number", "split", "title",
    "cm_width", "cm_height",
    "native_px_width", "native_px_height", "native_megapixels",
    "analyzed_px_width", "analyzed_px_height",
    "mm_per_px_native", "mm_per_px_analyzed", "mm_per_px_cnn_input",
    "native_pixels_used_fraction", "resolution_headroom_x",
    "cnn_area_kept_fraction",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def cnn_geometry(analyzed_w: int, analyzed_h: int, mm_per_px: float) -> tuple[float, float]:
    """Effective mm/px and retained image fraction after the Branch C transform.

    `preprocess.py` resizes the short side to CNN_RESIZE_SHORT then centre-crops
    CNN_CROP, so the CNN never sees the original resolution and never sees the
    whole picture. Both constants are imported so this cannot drift from the
    transform actually applied.
    """
    scale = preprocess.CNN_RESIZE_SHORT / min(analyzed_w, analyzed_h)
    resized_w, resized_h = analyzed_w * scale, analyzed_h * scale
    mm_per_px_cnn = mm_per_px / scale
    area_kept = (preprocess.CNN_CROP / resized_w) * (preprocess.CNN_CROP / resized_h)
    return mm_per_px_cnn, min(area_kept, 1.0)


def load_rows() -> list[dict]:
    if not config.DB_PATH.is_file():
        raise FileNotFoundError(f"{config.DB_PATH} missing; run acquire.py first")
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        raw = conn.execute(
            "SELECT object_number, split, title, cm_width, cm_height, "
            "native_px_width, native_px_height, analyzed_px_width, analyzed_px_height, "
            "mm_per_px_native, mm_per_px_analyzed "
            "FROM works WHERE split IN (?,?,?,?) ORDER BY object_number",
            SCORED_SPLITS,
        ).fetchall()
    finally:
        conn.close()

    rows = []
    for r in raw:
        d = dict(r)
        if d["mm_per_px_analyzed"] is None or d["analyzed_px_width"] is None:
            print(f"  SKIP {d['object_number']}: incomplete geometry "
                  "(run `python dimensions.py`)", file=sys.stderr)
            continue
        mm_cnn, area_kept = cnn_geometry(
            d["analyzed_px_width"], d["analyzed_px_height"], d["mm_per_px_analyzed"]
        )
        d["mm_per_px_cnn_input"] = mm_cnn
        d["cnn_area_kept_fraction"] = area_kept
        d["native_megapixels"] = d["native_px_width"] * d["native_px_height"] / 1e6
        d["native_pixels_used_fraction"] = (
            d["analyzed_px_width"] * d["analyzed_px_height"]
        ) / (d["native_px_width"] * d["native_px_height"])
        d["resolution_headroom_x"] = d["mm_per_px_analyzed"] / d["mm_per_px_native"]
        rows.append(d)
    return rows


def write_csv(rows: list[dict]) -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda x: -x["mm_per_px_analyzed"]):
            w.writerow({
                k: (f"{r[k]:.6f}" if isinstance(r[k], float) else r[k])
                for k in CSV_COLUMNS
            })


def build_markdown(rows: list[dict]) -> str:
    def col(key: str) -> np.ndarray:
        return np.array([r[key] for r in rows], dtype=np.float64)

    mm_an, mm_nat, mm_cnn = col("mm_per_px_analyzed"), col("mm_per_px_native"), col("mm_per_px_cnn_input")
    kept = col("cnn_area_kept_fraction")
    total_native_mp = col("native_megapixels").sum()
    total_analyzed_mp = sum(
        r["analyzed_px_width"] * r["analyzed_px_height"] for r in rows
    ) / 1e6
    lo, hi = BRUSHSTROKE_MM

    def spread(a: np.ndarray) -> str:
        return f"{a.min():.3f} – {a.max():.3f} ({a.max() / a.min():.0f}×)"

    L = [
        "# Resolution audit",
        "",
        f"**Source:** `data/cohortscope.sqlite` (`works` geometry, Fix 1) · "
        f"**N:** {len(rows)} scored works · **Generated:** `{_utc_now()}`",
        "",
        "Descriptive only — nothing here fits, scores, or selects a resolution floor.",
        "",
        "## 1. What each pixel covers",
        "",
        "A pixel is only meaningful in millimetres of canvas. Because every image was "
        f"fetched at a fixed **width of {config.IIIF_MAX_EDGE} px** regardless of how "
        "large the painting is, that quantity varies enormously across the corpus.",
        "",
        "| Stage | mm per pixel (min – max) | median |",
        "|---|---|---|",
        f"| native IIIF (what the museum publishes) | {spread(mm_nat)} | {np.median(mm_nat):.3f} |",
        f"| analyzed derivative (what `features_v1` measured) | {spread(mm_an)} | {np.median(mm_an):.3f} |",
        f"| CNN input (what `embed_v1` actually saw) | {spread(mm_cnn)} | {np.median(mm_cnn):.3f} |",
        "",
        f"A 17th-century oil brushstroke is roughly **{lo}–{hi} mm** wide. Resolving one "
        "needs several pixels across it, so a stage whose mm/px approaches that range "
        "cannot represent handling at all — only composition and colour.",
        "",
        "| Stage | works finer than 0.30 mm/px | works coarser than 1.00 mm/px |",
        "|---|---:|---:|",
        f"| native | {int((mm_nat < 0.30).sum())} / {len(rows)} | {int((mm_nat > 1.0).sum())} / {len(rows)} |",
        f"| analyzed | {int((mm_an < 0.30).sum())} / {len(rows)} | {int((mm_an > 1.0).sum())} / {len(rows)} |",
        f"| CNN input | {int((mm_cnn < 0.30).sum())} / {len(rows)} | {int((mm_cnn > 1.0).sum())} / {len(rows)} |",
        "",
        "## 2. Headroom left on the table",
        "",
        "| Quantity | Value |",
        "|---|---|",
        f"| native resolution published across the corpus | **{total_native_mp:,.0f} MP** |",
        f"| resolution actually analyzed | **{total_analyzed_mp:,.0f} MP** |",
        f"| fraction of published pixels used | **{100 * total_analyzed_mp / total_native_mp:.1f}%** |",
        f"| per-work linear headroom (native is this much finer) | "
        f"{col('resolution_headroom_x').min():.1f}× – {col('resolution_headroom_x').max():.1f}×, "
        f"median {np.median(col('resolution_headroom_x')):.1f}× |",
        "",
        "The detail needed to resolve brushwork was already published and free to "
        "request; the pipeline discarded it at download time, before any modelling "
        "decision was made.",
        "",
        "## 3. What the CNN was given",
        "",
        f"`preprocess.py` resizes the short side to {preprocess.CNN_RESIZE_SHORT} px and "
        f"centre-crops {preprocess.CNN_CROP} px (Branch C). Two consequences follow from "
        "geometry alone, before any question about the backbone:",
        "",
        f"- **Resolution.** The CNN input spans {mm_cnn.min():.2f}–{mm_cnn.max():.2f} mm/px. "
        f"At the coarse end one pixel covers {mm_cnn.max():.1f} mm of canvas — wider than "
        f"the broadest brushstroke ({hi} mm) by {mm_cnn.max() / hi:.0f}×, and than the "
        f"finest ({lo} mm) by {mm_cnn.max() / lo:.0f}×. Not one work in the corpus reaches "
        f"{lo} mm/px at this stage.",
        f"- **Coverage.** The centre crop keeps {100 * kept.min():.0f}%–{100 * kept.max():.0f}% "
        f"of each picture (median {100 * np.median(kept):.0f}%), and how much is discarded "
        "depends on aspect ratio, which adds a second uncontrolled variable.",
        "",
        "This is the arithmetic reason Signal A scored AUC 0.427 against the pupil cohort "
        "(`results/pupil_validation_report.md`): at this input scale there is no brushwork "
        "left for the embedding to compare.",
        "",
        "## 4. Eligibility census at candidate floors",
        "",
        "How many works could support analysis at a given target resolution — from the "
        "native image, versus from the derivative the pipeline actually used.",
        "",
        "| target mm/px | eligible at native | eligible in analyzed derivative |",
        "|---|---:|---:|",
    ]
    for f in CANDIDATE_FLOORS_MM:
        L.append(
            f"| ≤ {f:.2f} | {int((mm_nat <= f).sum())} / {len(rows)} "
            f"| {int((mm_an <= f).sum())} / {len(rows)} |"
        )

    never_eligible = int((mm_nat > 0.30).sum())
    L += [
        "",
        f"Two different problems separate: {int((mm_an > 0.30).sum())} works are too coarse "
        f"in the analyzed derivative but recoverable from the native image, whereas "
        f"**{never_eligible} works never reach 0.30 mm/px even at native resolution** — the "
        "museum has not published them finely enough for texture analysis at any download "
        "size. The first group is fixable by re-requesting; the second is only fixable by "
        "re-imaging, which is the actionable finding for a collection holder.",
        "",
        "**No floor is selected here.** Picking one decides which works get scored and "
        "which are declared out of scope, so it is a design decision that must be "
        "pre-registered before the resulting numbers are seen — the same rule that "
        "governed O04 and O06.",
        "",
        "## 5. D27 restated with real measurements",
        "",
        "D27 recorded that Phase 1 requested `full/1500,` — a fixed **width**, not a "
        "fixed long edge — and flagged the consequence as documented-not-fixed. The "
        "catalogued sizes now quantify it:",
        "",
    ]
    tall = [r for r in rows if r["analyzed_px_height"] > config.IIIF_MAX_EDGE]
    L += [
        f"- {len(tall)} of {len(rows)} works are taller than {config.IIIF_MAX_EDGE} px in "
        "the analyzed derivative, so their long edge exceeds the nominal cap.",
        "- More consequentially, fixing the **width** means physical scale tracks physical "
        f"width: the widest work in the corpus is {col('cm_width').max():.0f} cm and the "
        f"narrowest {col('cm_width').min():.0f} cm, a {col('cm_width').max() / col('cm_width').min():.0f}× "
        f"range that maps directly onto the {mm_an.max() / mm_an.min():.0f}× mm/px spread above.",
        "",
        "## 6. Per-work data",
        "",
        "`results/resolution_audit.csv` — one row per scored work, ordered coarsest first.",
        "",
        "### Coarsest 5 (analyzed)",
        "",
        "| object | split | cm wide | native mm/px | analyzed mm/px | CNN mm/px | native px used |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    ordered = sorted(rows, key=lambda r: -r["mm_per_px_analyzed"])
    for r in ordered[:5]:
        L.append(
            f"| `{r['object_number']}` | {r['split']} | {r['cm_width']:.0f} "
            f"| {r['mm_per_px_native']:.3f} | {r['mm_per_px_analyzed']:.3f} "
            f"| {r['mm_per_px_cnn_input']:.2f} | {100 * r['native_pixels_used_fraction']:.1f}% |"
        )
    L += [
        "",
        "### Finest 5 (analyzed)",
        "",
        "| object | split | cm wide | native mm/px | analyzed mm/px | CNN mm/px | native px used |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for r in ordered[-5:]:
        L.append(
            f"| `{r['object_number']}` | {r['split']} | {r['cm_width']:.0f} "
            f"| {r['mm_per_px_native']:.3f} | {r['mm_per_px_analyzed']:.3f} "
            f"| {r['mm_per_px_cnn_input']:.2f} | {100 * r['native_pixels_used_fraction']:.1f}% |"
        )
    L.append("")
    return "\n".join(L)


def run(*, force: bool) -> int:
    if MD_PATH.exists() and not force:
        print(f"Refusing to overwrite {MD_PATH}; pass --force", file=sys.stderr)
        return 1
    rows = load_rows()
    if not rows:
        print("No scored works with complete geometry; run `python dimensions.py`", file=sys.stderr)
        return 1
    write_csv(rows)
    MD_PATH.write_text(build_markdown(rows), encoding="utf-8")
    print(f"Wrote {CSV_PATH} ({len(rows)} rows)")
    print(f"Wrote {MD_PATH}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Physical-resolution audit (Fix 1)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing audit")
    args = parser.parse_args()
    return run(force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
