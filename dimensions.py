"""
Physical + native-pixel geometry cache for scored works (D32 / O06 §4.6).

Resolves each work's catalogued physical size (cm, from the `la-framed` payload)
and its native IIIF pixel size (`info.json`), and derives mm-per-pixel for both the
native image and the analyzed 1500px-wide derivative.

Used by `evaluate_pupils.py` for the pre-registered confound check. Writes nothing
that any scoring stage reads — it does not alter scores.

Usage (repo root, mamba env CohortScope):
  python dimensions.py           # fill gaps in the cache
  python dimensions.py --force   # re-resolve every work
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from PIL import Image

import config
import rijks_api

SCORED_SPLITS = ("cohort", "validation", "ambiguous", "pupil")
CACHE_PATH = config.META_DIR / "dimensions.json"
INFO_TMPL = "https://iiif.micr.io/{identifier}/info.json"

# Getty AAT / Rijksmuseum notation labels for the two dimensions we want.
_WANTED = ("height", "width")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_physical_cm(record: dict) -> dict[str, float]:
    """Pull catalogued height/width in cm from a resolved la-framed record."""
    out: dict[str, float] = {}
    for dim in record.get("dimension", []) or []:
        value = dim.get("value")
        if value is None:
            continue
        for classified in dim.get("classified_as", []) or []:
            for note in classified.get("notation", []) or []:
                label = note.get("@value")
                if note.get("@language") == "en" and label in _WANTED:
                    out.setdefault(label, float(value))
    return out


def native_pixels(iiif_id: str) -> tuple[int, int]:
    info = requests.get(
        INFO_TMPL.format(identifier=iiif_id), timeout=config.REQUEST_TIMEOUT_S
    )
    info.raise_for_status()
    data = info.json()
    return int(data["width"]), int(data["height"])


def load_cache() -> dict[str, dict]:
    if CACHE_PATH.is_file():
        with CACHE_PATH.open(encoding="utf-8") as f:
            return json.load(f).get("works", {})
    return {}


def scored_works() -> list[dict]:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT object_number, object_uri, iiif_id, image_path, split "
            "FROM works WHERE split IN (?,?,?,?) ORDER BY object_number",
            SCORED_SPLITS,
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def resolve_one(work: dict) -> dict | None:
    record = rijks_api.resolve(work["object_uri"])
    cm = extract_physical_cm(record)
    if "width" not in cm or "height" not in cm:
        return None
    native_w, native_h = native_pixels(work["iiif_id"])
    with Image.open(config.ROOT / work["image_path"]) as im:
        analyzed_w, analyzed_h = im.size
    return {
        "split": work["split"],
        "cm_width": cm["width"],
        "cm_height": cm["height"],
        "native_px_width": native_w,
        "native_px_height": native_h,
        "analyzed_px_width": analyzed_w,
        "analyzed_px_height": analyzed_h,
        # mm of canvas per pixel — the quantity texture features are implicitly
        # measured in. Both are reported: the analyzed derivative is what
        # features_v1 actually saw; native is the ceiling the museum publishes.
        "mm_per_px_analyzed": cm["width"] * 10.0 / analyzed_w,
        "mm_per_px_native": cm["width"] * 10.0 / native_w,
    }


def run(*, force: bool) -> int:
    config.META_DIR.mkdir(parents=True, exist_ok=True)
    cache = {} if force else load_cache()
    works = scored_works()
    todo = [w for w in works if w["object_number"] not in cache]
    print(f"{len(works)} scored works; {len(todo)} to resolve")

    failures: list[str] = []
    for i, w in enumerate(todo, 1):
        oid = w["object_number"]
        if not w["iiif_id"] or not w["image_path"]:
            failures.append(f"{oid}: no iiif_id/image_path")
            continue
        try:
            entry = resolve_one(w)
        except (requests.RequestException, OSError, KeyError, ValueError) as exc:
            failures.append(f"{oid}: {exc}")
            continue
        if entry is None:
            failures.append(f"{oid}: no catalogued cm dimensions")
            continue
        cache[oid] = entry
        print(f"  [{i}/{len(todo)}] {oid} {entry['cm_width']:.1f}cm "
              f"{entry['mm_per_px_analyzed']:.3f} mm/px analyzed / "
              f"{entry['mm_per_px_native']:.4f} native")

    payload = {
        "generated_at": _utc_now(),
        "source": "rijks la-framed dimension[] + IIIF info.json",
        "n_works": len(cache),
        "works": dict(sorted(cache.items())),
    }
    with CACHE_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    print(f"Wrote {CACHE_PATH} ({len(cache)} works)")
    if failures:
        print(f"{len(failures)} unresolved:", file=sys.stderr)
        for line in failures:
            print(f"  {line}", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Cache physical + native geometry (O06 §4.6)")
    parser.add_argument("--force", action="store_true", help="Re-resolve every work")
    args = parser.parse_args()
    return run(force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
