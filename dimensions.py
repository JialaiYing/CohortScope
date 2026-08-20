"""
Backfill physical + native geometry onto rows acquired before Fix 1.

`acquire.py` now captures catalogued size (cm), native IIIF pixel size, and the
derived millimetres-per-pixel for every work it harvests. This module fills those
columns in for a database written before that existed, so an existing snapshot
does not have to be re-harvested from scratch.

It is a backfill, not a second source of truth: the `works` table is authoritative
and this writes into it. It touches no split, no score, and no feature.

Usage (repo root, mamba env CohortScope):
  python dimensions.py            # fill rows whose geometry is missing
  python dimensions.py --force    # re-resolve every scored row
  python dimensions.py --check    # report coverage; resolve nothing
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

import requests

import acquire
import config
import rijks_api

SCORED_SPLITS = ("cohort", "validation", "ambiguous", "pupil")

GEOMETRY_COLUMNS = (
    "cm_width",
    "cm_height",
    "native_px_width",
    "native_px_height",
    "analyzed_px_width",
    "analyzed_px_height",
    "mm_per_px_analyzed",
    "mm_per_px_native",
)


def open_db() -> sqlite3.Connection:
    if not config.DB_PATH.is_file():
        raise FileNotFoundError(f"{config.DB_PATH} missing; run acquire.py first")
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    for change in acquire.migrate_schema(conn):
        print(f"  migration: {change}")
    return conn


def scored_rows(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT object_number, object_uri, iiif_id, image_path, split, "
        + ", ".join(GEOMETRY_COLUMNS)
        + " FROM works WHERE split IN (?,?,?,?) ORDER BY object_number",
        SCORED_SPLITS,
    ).fetchall()
    return [dict(r) for r in rows]


def needs_backfill(row: dict) -> bool:
    return any(row.get(c) is None for c in GEOMETRY_COLUMNS)


def report_coverage(rows: list[dict]) -> int:
    missing = [r for r in rows if needs_backfill(r)]
    print(f"{len(rows)} scored works; {len(rows) - len(missing)} with complete geometry")
    if missing:
        print(f"{len(missing)} incomplete:")
        for r in missing[:20]:
            gaps = [c for c in GEOMETRY_COLUMNS if r.get(c) is None]
            print(f"  {r['object_number']:12s} missing {', '.join(gaps)}")
        if len(missing) > 20:
            print(f"  ... and {len(missing) - 20} more")
    return len(missing)


def backfill_one(conn: sqlite3.Connection, row: dict) -> bool:
    record = rijks_api.resolve(row["object_uri"])
    image_path = Path(row["image_path"]) if row["image_path"] else None
    if image_path is not None and not image_path.is_absolute():
        image_path = config.ROOT / image_path
    geo = acquire.compute_geometry(record, row["iiif_id"], image_path)
    conn.execute(
        "UPDATE works SET " + ", ".join(f"{c}=?" for c in GEOMETRY_COLUMNS)
        + " WHERE object_number=?",
        tuple(geo[c] for c in GEOMETRY_COLUMNS) + (row["object_number"],),
    )
    return geo["mm_per_px_analyzed"] is not None


def run(*, force: bool, check: bool) -> int:
    conn = open_db()
    try:
        rows = scored_rows(conn)
        if check:
            return 0 if report_coverage(rows) == 0 else 1

        todo = rows if force else [r for r in rows if needs_backfill(r)]
        print(f"{len(rows)} scored works; {len(todo)} to resolve")
        unresolved: list[str] = []
        for i, row in enumerate(todo, 1):
            oid = row["object_number"]
            try:
                ok = backfill_one(conn, row)
            except (requests.RequestException, OSError, KeyError, ValueError) as exc:
                unresolved.append(f"{oid}: {exc}")
                continue
            if not ok:
                unresolved.append(f"{oid}: no catalogued width; mm/px left NULL")
            if i % 20 == 0 or i == len(todo):
                print(f"  [{i}/{len(todo)}] resolved")
        conn.commit()

        rows = scored_rows(conn)
        complete = sum(1 for r in rows if not needs_backfill(r))
        print(f"Geometry complete for {complete}/{len(rows)} scored works")
        if unresolved:
            print(f"{len(unresolved)} unresolved:", file=sys.stderr)
            for line in unresolved:
                print(f"  {line}", file=sys.stderr)
    finally:
        conn.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill physical/native geometry (Fix 1)")
    parser.add_argument("--force", action="store_true", help="Re-resolve every scored row")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report geometry coverage and exit non-zero if incomplete; resolves nothing",
    )
    args = parser.parse_args()
    return run(force=args.force, check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
