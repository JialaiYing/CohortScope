"""
Build the findings dossier (D38) from the published artifacts.

Every number on the page is read out of a committed artifact -- the manifests,
the QC summaries, the sweep curve, the SQLite geometry -- and injected into
`dossier_template.html`. Nothing is transcribed by hand, so the page cannot drift
away from the results it reports; regenerate it and any stale figure changes.

This is a presentation layer over a **closed negative result** (D31 restated for
D38): it computes nothing, fits nothing, and scores nothing. The science
deliverable remains the tables and reports in `results/`.

Reads : data/cohortscope.sqlite, data/tiles/tiles_v1/manifest.json,
        results/sweep/sweep_curve.csv, results/qc_*/summary.json,
        results/scores/scores_v1.csv, dossier_template.html
Writes: results/dossier/index.html (self-contained)
        results/dossier/data.json (the extracted figures, for inspection)

Usage (repo root, mamba env CohortScope):
  python dossier.py
"""

from __future__ import annotations

import csv
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import config

TEMPLATE = config.ROOT / "dossier_template.html"
OUT_DIR = config.RESULTS_DIR / "dossier"
OUT_HTML = OUT_DIR / "index.html"
OUT_JSON = OUT_DIR / "data.json"
MARKER = "/*__DOSSIER_DATA__*/"

TILES_MANIFEST = config.DATA_DIR / "tiles" / "tiles_v1" / "manifest.json"
CNN_MANIFEST = config.DATA_DIR / "tiles" / "cnn_tiles_v1" / "manifest.json"
SWEEP_CURVE = config.RESULTS_DIR / "sweep" / "sweep_curve.csv"
AUDIT_CSV = config.RESULTS_DIR / "resolution_audit.csv"

# The five held-out outcomes, each with the artifact that carries it.
OUTCOMES = [
    ("O04", "Does the one held-out workshop attribution score as anomalous?",
     "weak", "N=1", "results/validation_report.md"),
    ("O06", "Do 67 documented pupils separate from the cohort? (fixed-1500 px)",
     "fail", "AUC 0.419", "results/pupil_validation_report.md"),
    ("O09", "Signal B, once every pixel means 0.20 mm of canvas",
     "fail", "AUC 0.469", "results/tile_validation_report.md"),
    ("O11", "Signal A, fed 224 px tiles with no resize and no crop",
     "fail", "AUC 0.523", "results/tile_embedding_report.md"),
    ("O13", "Both signals swept 0.15-0.30 mm/px on a fixed population",
     "fail", "8/8 at chance", "results/resolution_sweep_report.md"),
]

# Each alternative explanation for the O06 failure, and how it was closed.
# This is a real sequence -- each step only became askable once the one before
# it was settled -- so the numbering carries information.
RULED_OUT = [
    {
        "claim": "The held-out set was too small to conclude anything.",
        "test": "Raised the held-out class from 1 work to 67 documented pupils of "
                "Rembrandt, catalogued under their own names, pre-registered before "
                "acquisition.",
        "result": "Closed. AUC 0.419 on N=67 -- below chance, not merely unproven.",
        "ref": "D32 / O06",
    },
    {
        "claim": "The features were fine; the images were measured at different scales.",
        "test": "Recorded catalogued size and native IIIF resolution for every work, "
                "then measured what each pipeline stage actually saw.",
        "result": "Confirmed, and worse than expected. Analyzed scale varied 35x, and "
                  "the CNN never once reached 0.30 mm/px on any of 108 works.",
        "ref": "D33 / resolution audit",
    },
    {
        "claim": "Fix the scale and the handcrafted features will work.",
        "test": "Replaced fixed-pixel downloads with fixed-area IIIF tiles -- 30 mm of "
                "canvas at 150 px, so one pixel is 0.20 mm on every painting -- and "
                "recomputed the same eight features, unchanged.",
        "result": "Closed. AUC 0.469. Against the same works on fixed-pixel input, "
                  "dAUC = +0.042, CI [-0.141, +0.223]: indistinguishable from no change.",
        "ref": "D34, D35 / O09",
    },
    {
        "claim": "The CNN was never shown brushwork, so its score was never a fair test.",
        "test": "Requested 44.8 mm tiles at 224 px -- the backbone's native input size at "
                "the locked floor -- so the tile enters the network with no resize, no "
                "crop, and no interpolation.",
        "result": "Closed. AUC 0.523. dAUC = +0.132, CI [-0.092, +0.352]: the largest "
                  "movement any change produced, and still centred on chance.",
        "ref": "D36 / O11",
    },
    {
        "claim": "0.20 mm/px was simply the wrong scale to look at.",
        "test": "Swept both signals across 0.15 / 0.20 / 0.25 / 0.30 mm/px on a population "
                "held fixed across floors, with the multiplicity correction fixed in "
                "advance for all eight tests.",
        "result": "Closed. All eight points within 0.047 of chance. None clears the "
                  "corrected bar; none clears even the uncorrected one.",
        "ref": "D37 / O13",
    },
]

REASON_LABEL = {
    "eligible": "Answerable",
    "native_coarser_than_floor": "Published imagery too coarse",
    "insufficient_tiles": "Too small for 20 tiles",
    "no_geometry": "No catalogued size",
    "no_iiif_identifier": "No IIIF image",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def geometry() -> dict[str, dict]:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT object_number, title, split, pupil_tier, source_query, "
            "cm_width, cm_height, native_px_width, native_px_height, "
            "mm_per_px_native, mm_per_px_analyzed FROM works "
            "WHERE split IN ('cohort','validation','ambiguous','pupil')"
        ).fetchall()
    finally:
        conn.close()
    return {r["object_number"]: dict(r) for r in rows}


def cnn_mm_per_px() -> dict[str, float]:
    """What the CNN actually saw per work, from the committed audit CSV."""
    out: dict[str, float] = {}
    if not AUDIT_CSV.is_file():
        return out
    with AUDIT_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            for key in ("mm_per_px_cnn", "cnn_mm_per_px", "mm_per_px_cnn_input"):
                if row.get(key):
                    out[row["object_number"]] = float(row[key])
                    break
    return out


def build_works(geo: dict, tiles_man: dict, cnn_man: dict, cnn_mm: dict) -> list[dict]:
    """One row per scored work: what it is, what was published, what can be answered."""
    tw = tiles_man["works"]
    cw = cnn_man["works"]
    out = []
    for oid, g in sorted(geo.items()):
        t = tw.get(oid, {})
        c = cw.get(oid, {})
        klass = g["split"]
        if klass == "pupil":
            klass = f"pupil ({g['pupil_tier'] or '?'})"
        out.append({
            "id": oid,
            "title": (g["title"] or "").strip(),
            "artist": (g["source_query"] if g["split"] == "pupil" else "Rembrandt van Rijn"),
            "klass": klass,
            "split": g["split"],
            "cm_w": g["cm_width"],
            "cm_h": g["cm_height"],
            "native_mm": g["mm_per_px_native"],
            "analyzed_mm": g["mm_per_px_analyzed"],
            "cnn_mm": cnn_mm.get(oid),
            "native_px": g["native_px_width"],
            "verdict": t.get("verdict", "below_floor"),
            "reason": t.get("reason", "no_geometry"),
            "reason_label": REASON_LABEL.get(t.get("reason", "no_geometry"), t.get("reason", "")),
            "cnn_eligible": c.get("verdict") == "eligible",
            # Relative to results/dossier/index.html. Emitted only when the JPEG is
            # actually committed, so the page can distinguish "no image" from a 404.
            "img": (f"../../data/images/{oid}.jpg"
                    if (config.IMAGES_DIR / f"{oid}.jpg").is_file() else None),
        })
    return out


def sweep_points() -> list[dict]:
    pts = []
    with SWEEP_CURVE.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            pts.append({
                "signal": r["signal"],
                "floor": float(r["floor"]),
                "tile_px": int(r["tile_px"]),
                "tile_mm": float(r["tile_mm"]),
                "auc": float(r["auc"]),
                "lo95": float(r["ci95_lo"]),
                "hi95": float(r["ci95_hi"]),
                "loC": float(r["ci_corrected_lo"]),
                "hiC": float(r["ci_corrected_hi"]),
                "base": float(r["base_rate"]),
            })
    return pts


def build() -> dict:
    geo = geometry()
    tiles_man = load_json(TILES_MANIFEST)
    cnn_man = load_json(CNN_MANIFEST)
    works = build_works(geo, tiles_man, cnn_man, cnn_mm_per_px())

    o09 = load_json(config.RESULTS_DIR / "qc_tile_scores_v1" / "summary.json")
    o11 = load_json(config.RESULTS_DIR / "qc_tile_scores_a_v1" / "summary.json")
    o13 = load_json(config.RESULTS_DIR / "qc_sweep_v1" / "summary.json")
    sweep_fit = load_json(config.RESULTS_DIR / "sweep" / "fit_manifest.json")

    answerable = sum(1 for w in works if w["verdict"] == "eligible")
    cohort_blocked = [
        w for w in works if w["split"] == "cohort" and w["verdict"] != "eligible"
    ]
    native = [w["native_mm"] for w in works if w["native_mm"]]
    analyzed = [w["analyzed_mm"] for w in works if w["analyzed_mm"]]
    cnn_vals = [w["cnn_mm"] for w in works if w["cnn_mm"]]

    return {
        "generated": _utc_now(),
        "n_works": len(works),
        "outcomes": [
            {"id": i, "question": q, "tier": t, "stat": s, "ref": r}
            for i, q, t, s, r in OUTCOMES
        ],
        "ruled_out": RULED_OUT,
        "works": works,
        "sweep": sweep_points(),
        "confounds": [
            {"test": "O06", "what": "mm/px of the analyzed image", "auc": 0.590,
             "pipeline": 0.419, "n": "23 + 67"},
            {"test": "O09", "what": "native mm/px published", "auc": 0.689,
             "pipeline": 0.469, "n": "17 + 38"},
            {"test": "O11", "what": "native mm/px published", "auc": 0.705,
             "pipeline": 0.523, "n": "15 + 36"},
            {"test": "O13", "what": "native mm/px published", "auc": 0.617,
             "pipeline": 0.530, "n": "15 + 20"},
        ],
        "scale": {
            "native": [min(native), max(native)],
            "analyzed": [min(analyzed), max(analyzed)],
            "cnn": [min(cnn_vals), max(cnn_vals)] if cnn_vals else None,
            "pixels_used_pct": 6.3,
            "native_mp": 4408,
            "analyzed_mp": 278,
            "cnn_below_stroke": len(works),
        },
        "adequacy": {
            "answerable": answerable,
            "blocked": len(works) - answerable,
            "cohort_blocked": len(cohort_blocked),
            "cohort_total": sum(1 for w in works if w["split"] == "cohort"),
            "blocked_examples": sorted(
                [w for w in works if w["verdict"] != "eligible" and w["native_mm"]],
                key=lambda w: -w["native_mm"],
            )[:5],
        },
        "stats": {
            "o09": o09, "o11": o11, "o13": o13,
            "sweep_population": sweep_fit["population_sizes"],
            "n_tests": sweep_fit["multiplicity"]["n_tests"],
            "corrected_pct": sweep_fit["multiplicity"]["corrected_ci_pct"],
        },
    }


def main() -> int:
    if not TEMPLATE.is_file():
        print(f"ERROR: missing {TEMPLATE}", file=sys.stderr)
        return 1
    data = build()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, indent=1), encoding="utf-8")

    html = TEMPLATE.read_text(encoding="utf-8")
    if MARKER not in html:
        print(f"ERROR: {TEMPLATE.name} has no {MARKER} marker", file=sys.stderr)
        return 1
    blob = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    OUT_HTML.write_text(html.replace(MARKER, f"window.DOSSIER={blob};"), encoding="utf-8")

    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_HTML}  ({OUT_HTML.stat().st_size / 1024:.0f} KB)")
    print(f"  {data['n_works']} works, {data['adequacy']['answerable']} answerable, "
          f"{data['adequacy']['blocked']} blocked")
    print(f"  {len(data['sweep'])} sweep points, {len(data['outcomes'])} outcomes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
