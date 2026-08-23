"""
Phase 9 Wave A: the eight O03 features recomputed per physically-normalized tile.

Implements `results/phase9_tile_statistics_design.md` §3 (D35 / O08). Every tile
is 30 mm x 30 mm of canvas at 150 x 150 px, so a GLCM offset of 1 px is 0.20 mm
on every work in the corpus -- the property `features_v1` did not have.

The feature definitions are deliberately **unchanged**: this module calls
`features.extract_one()`, the same function `features.py` calls, with the same
frozen constants. The only difference between `features_v1` and this recipe is
what a pixel means. Changing the features and the pixels together would make the
comparison in §5 uninterpretable.

Reads : data/tiles/tiles_v1/manifest.json + the tile JPEGs it names
Writes: data/features/tile_features_v1.csv (+ manifest)
QC    : results/qc_tile_features_v1/{failures.csv,summary.json}

No aggregation, no z-score, no fit, no Signal A (design §2). One row per tile.

Usage (repo root, mamba env CohortScope):
  python tile_features.py
  python tile_features.py --force
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

import config
import features
import tiles

RECIPE_ID = "tile_features_v1"
TILES_RECIPE = tiles.RECIPE_ID
DESIGN_DOC = "results/phase9_tile_statistics_design.md"
DECISION = "D35"

FEATURE_COLUMNS = features.FEATURE_COLUMNS
# Design §4.1: the only column that can legitimately have no value on a tile.
# `hue_circ_std` needs at least one pixel with Lab chroma >= features.HUE_CHROMA_MIN.
UNDEFINABLE_COLUMNS = ("hue_circ_std",)

TILE_ROOT = tiles.TILE_ROOT
TILE_MANIFEST = tiles.MANIFEST_PATH
OUT_DIR = config.DATA_DIR / "features"
CSV_PATH = OUT_DIR / f"{RECIPE_ID}.csv"
MANIFEST_PATH = OUT_DIR / f"{RECIPE_ID}_manifest.json"
QC_DIR = config.RESULTS_DIR / f"qc_{RECIPE_ID}"
FAILURES_PATH = QC_DIR / "failures.csv"
SUMMARY_PATH = QC_DIR / "summary.json"
UNDEFINED_PATH = QC_DIR / "undefined_cells.csv"

ROW_FIELDS = (
    "object_number",
    "split",
    "pupil_tier",
    "tile_row",
    "tile_col",
    *FEATURE_COLUMNS,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_tile_manifest() -> dict:
    """Recipe-ID contract: the upstream manifest is the worklist, not the filesystem."""
    if not TILE_MANIFEST.is_file():
        raise FileNotFoundError(f"missing {TILE_MANIFEST}; run `python tiles.py` first")
    with TILE_MANIFEST.open(encoding="utf-8") as f:
        man = json.load(f)
    if man.get("recipe_id") != TILES_RECIPE:
        raise ValueError(f"expected recipe_id={TILES_RECIPE}, got {man.get('recipe_id')!r}")
    return man


def worklist(man: dict) -> list[tuple[str, dict]]:
    """Eligible works in manifest order, each with its pre-registered tile positions."""
    works = man["works"]
    out: list[tuple[str, dict]] = []
    for oid in man["object_numbers"]:
        entry = works[oid]
        if entry["verdict"] != "eligible":
            raise ValueError(f"{oid} is in object_numbers but verdict={entry['verdict']}")
        out.append((oid, entry))
    return out


def read_tile(path: Path) -> np.ndarray:
    """Tile JPEG -> HxWx3 uint8 RGB. Branch H discipline: no CNN tensor is read here."""
    with Image.open(path) as im:
        arr = np.asarray(im.convert("RGB"), dtype=np.uint8)
    expected = config.TILE_SIZE_PX
    if arr.shape[:2] != (expected, expected):
        raise ValueError(f"expected {expected}x{expected} tile, got {arr.shape[1]}x{arr.shape[0]}")
    return arr


def extract_work(oid: str, entry: dict) -> tuple[list[dict], list[dict], list[dict]]:
    rows: list[dict] = []
    failures: list[dict] = []
    undefined_cells: list[dict] = []
    for row_i, col_i in entry["positions"]:
        path = tiles.tile_path(oid, row_i, col_i)
        try:
            if not path.is_file():
                raise FileNotFoundError(f"tile missing: {path}")
            feats = features.extract_one(read_tile(path))
            # Design §4.1: a tile is never dropped for what it depicts. A feature
            # that is undefined on this tile (only `hue_circ_std` can be: an
            # entirely near-grey patch has no hue) is written as an empty cell and
            # excluded from that feature's aggregate, for this work only.
            undefined = [c for c in FEATURE_COLUMNS if not math.isfinite(feats[c])]
            unexpected = [c for c in undefined if c not in UNDEFINABLE_COLUMNS]
            if unexpected:
                raise ValueError(f"non-finite features: {unexpected}")
            rows.append(
                {
                    "object_number": oid,
                    "split": entry["split"],
                    "pupil_tier": entry.get("pupil_tier") or "",
                    "tile_row": row_i,
                    "tile_col": col_i,
                    **{
                        c: ("" if c in undefined else f"{feats[c]:.10g}")
                        for c in FEATURE_COLUMNS
                    },
                }
            )
            for c in undefined:
                undefined_cells.append(
                    {
                        "object_number": oid,
                        "split": entry["split"],
                        "tile_row": row_i,
                        "tile_col": col_i,
                        "column": c,
                        "reason": "undefined on this tile (design §4.1); tile retained",
                    }
                )
        except Exception as exc:  # noqa: BLE001 -- log per tile, never drop silently
            failures.append(
                {
                    "object_number": oid,
                    "split": entry["split"],
                    "tile_row": row_i,
                    "tile_col": col_i,
                    "error": str(exc),
                }
            )
    return rows, failures, undefined_cells


def write_csv(rows: list[dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(ROW_FIELDS))
        writer.writeheader()
        writer.writerows(rows)


def write_qc(
    failures: list[dict],
    undefined: list[dict],
    per_work: dict[str, int],
    man: dict,
) -> None:
    QC_DIR.mkdir(parents=True, exist_ok=True)
    with FAILURES_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["object_number", "split", "tile_row", "tile_col", "error"]
        )
        writer.writeheader()
        writer.writerows(failures)

    with UNDEFINED_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["object_number", "split", "tile_row", "tile_col", "column", "reason"],
        )
        writer.writeheader()
        writer.writerows(undefined)

    planned = {oid: e["tiles_written"] for oid, e in man["works"].items() if e["verdict"] == "eligible"}
    short = {oid: n for oid, n in per_work.items() if n < planned[oid]}
    summary = {
        "recipe_id": RECIPE_ID,
        "tiles_recipe": TILES_RECIPE,
        "created_at": _utc_now(),
        "n_works": len(per_work),
        "n_tiles_expected": sum(planned.values()),
        "n_tiles_featurized": sum(per_work.values()),
        "n_tile_failures": len(failures),
        "n_undefined_cells": len(undefined),
        "undefined_cells_by_column": {
            c: sum(1 for u in undefined if u["column"] == c) for c in UNDEFINABLE_COLUMNS
        },
        "works_with_undefined_cells": len({u["object_number"] for u in undefined}),
        "works_short_of_expected": short,
        "design": DESIGN_DOC,
        "decision": DECISION,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def write_manifest(rows: list[dict], per_work: dict[str, int], man: dict) -> None:
    manifest = {
        "recipe_id": RECIPE_ID,
        "tiles_recipe": TILES_RECIPE,
        "created_at": _utc_now(),
        "design": DESIGN_DOC,
        "decision": DECISION,
        "source": "tiles_v1 region JPEGs (Branch H equivalent: RGB, no CNN tensor)",
        "feature_columns": list(FEATURE_COLUMNS),
        "feature_source": "features.extract_one (unchanged from features_v1, design §3)",
        "mm_per_px": config.TILE_FLOOR_MM_PER_PX,
        "tile_size_px": config.TILE_SIZE_PX,
        "tile_size_mm": config.TILE_SIZE_MM,
        "n_rows": len(rows),
        "n_works": len(per_work),
        "object_numbers": sorted(per_work),
        "tiles_per_work": per_work,
        "splits_by_id": {
            oid: man["works"][oid]["split"] for oid in sorted(per_work)
        },
        "pupil_tier_by_id": {
            oid: (man["works"][oid].get("pupil_tier") or "") for oid in sorted(per_work)
        },
        "csv": CSV_PATH.relative_to(config.ROOT).as_posix(),
        "no_aggregation": True,
        "no_zscore": True,
        "undefinable_columns": list(UNDEFINABLE_COLUMNS),
        "undefined_cell_policy": "design §4.1: tile retained, cell empty, "
                                 "excluded from that feature's aggregate only",
        "no_signal_a": True,
        "numpy": np.__version__,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def run(*, force: bool) -> int:
    if CSV_PATH.is_file() and not force:
        print(f"Refusing to overwrite {CSV_PATH}; pass --force", file=sys.stderr)
        return 2

    man = load_tile_manifest()
    work_items = worklist(man)
    print(f"{RECIPE_ID}: {len(work_items)} eligible works at {config.TILE_FLOOR_MM_PER_PX} mm/px")

    rows: list[dict] = []
    failures: list[dict] = []
    undefined: list[dict] = []
    per_work: dict[str, int] = {}
    for i, (oid, entry) in enumerate(work_items, 1):
        w_rows, w_fail, w_undef = extract_work(oid, entry)
        rows.extend(w_rows)
        failures.extend(w_fail)
        undefined.extend(w_undef)
        per_work[oid] = len(w_rows)
        if i % 10 == 0 or i == len(work_items):
            print(f"  [{i}/{len(work_items)}] {len(rows)} tiles featurized")

    write_csv(rows)
    write_manifest(rows, per_work, man)
    write_qc(failures, undefined, per_work, man)

    print(f"Wrote {CSV_PATH} ({len(rows)} tile rows over {len(per_work)} works)")
    print(f"Wrote {MANIFEST_PATH}")
    print(f"Wrote {QC_DIR} (failures={len(failures)}, undefined cells={len(undefined)})")
    return 0 if not failures else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Per-tile O03 features (tile_features_v1 / D35)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing CSV")
    args = parser.parse_args()
    try:
        return run(force=args.force)
    except Exception as exc:  # noqa: BLE001 -- CLI surface
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
