"""
Phase 8: physically-normalized tile acquisition (D34 / O07 / tiles_v1).

Replaces the fixed-1500px download with IIIF region requests sized in millimetres
of canvas. Every tile covers TILE_SIZE_MM of the painting and is served at
TILE_SIZE_PX pixels, so one pixel means the same physical distance on a 15 cm
panel and a 4 m canvas — the property `preprocess_v1` never had.

Works whose published resolution cannot reach the floor are recorded as
**below floor** and are not tiled. They are reported, never silently scored.

Implements results/phase8_tiling_design.md exactly. The floor, tile size, inset,
tile count, and selection rule are pre-registered; they are read from `config`
and must not be edited to move a downstream number.

Reads : data/cohortscope.sqlite (geometry from D33)
Writes: data/tiles/tiles_v1/{object_number}/{row}_{col}.jpg
        data/tiles/tiles_v1/manifest.json
        results/qc_tiles_v1/{coverage.csv,failures.csv}
        results/tiling_report.md

Usage (repo root, mamba env CohortScope):
  python tiles.py            # fetch missing tiles
  python tiles.py --plan     # eligibility + tile plan only; no network, no writes
  python tiles.py --force    # re-fetch every tile
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

import config
import rijks_api

RECIPE_ID = "tiles_v1"
SCORED_SPLITS = ("cohort", "validation", "ambiguous", "pupil")

TILE_ROOT = config.DATA_DIR / "tiles" / RECIPE_ID
MANIFEST_PATH = TILE_ROOT / "manifest.json"
QC_DIR = config.RESULTS_DIR / f"qc_{RECIPE_ID}"
REPORT_PATH = config.RESULTS_DIR / "tiling_report.md"

# Below-floor reason codes (design §3). Fail-closed: anything not provably
# eligible is excluded with a stated reason.
REASON_OK = "eligible"
REASON_NO_GEOMETRY = "no_geometry"
REASON_COARSER_THAN_FLOOR = "native_coarser_than_floor"
REASON_TOO_FEW_TILES = "insufficient_tiles"
REASON_NO_IIIF = "no_iiif_identifier"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------
# planning — pure geometry, no network
# --------------------------------------------------------------------------

def tile_positions(
    native_w: int, native_h: int, mm_per_px_native: float
) -> tuple[list[tuple[int, int, int]], int, int, int]:
    """Deterministic tile plan for one work (design §2).

    Returns (selected, side_px, rows, cols) where `selected` is a list of
    (row, col, side_px) — but the caller derives x/y from row/col so the grid
    stays reconstructible from the manifest alone.
    """
    side = int(round(config.TILE_SIZE_MM / mm_per_px_native))
    if side < 1:
        return [], side, 0, 0

    inset_x0 = int(native_w * config.TILE_EDGE_INSET)
    inset_y0 = int(native_h * config.TILE_EDGE_INSET)
    inset_w = native_w - 2 * inset_x0
    inset_h = native_h - 2 * inset_y0

    cols = inset_w // side
    rows = inset_h // side
    total = rows * cols
    if total < config.TILES_PER_WORK:
        return [], side, rows, cols

    n = config.TILES_PER_WORK
    # Evenly spaced indices over the row-major enumeration. Strictly increasing
    # for total >= n, so no position is selected twice.
    selected = []
    for i in range(n):
        idx = (i * total) // n
        selected.append((idx // cols, idx % cols, side))
    return selected, side, rows, cols


def tile_origin(row: int, col: int, side: int, native_w: int, native_h: int) -> tuple[int, int]:
    """Top-left native-pixel coordinate of a grid cell."""
    return (
        int(native_w * config.TILE_EDGE_INSET) + col * side,
        int(native_h * config.TILE_EDGE_INSET) + row * side,
    )


def assess(work: dict) -> dict:
    """Eligibility verdict + tile plan for one work. Pure; no network."""
    out = {
        "object_number": work["object_number"],
        "split": work["split"],
        "pupil_tier": work["pupil_tier"],
        "title": work["title"],
        "mm_per_px_native": work["mm_per_px_native"],
        "verdict": None,
        "reason": None,
        "tile_side_native_px": None,
        "grid_rows": None,
        "grid_cols": None,
        "tiles_available": None,
        "tiles_planned": 0,
        "positions": [],
    }

    if not work["iiif_id"]:
        out["verdict"], out["reason"] = "below_floor", REASON_NO_IIIF
        return out
    if work["mm_per_px_native"] is None or not work["native_px_width"]:
        out["verdict"], out["reason"] = "below_floor", REASON_NO_GEOMETRY
        return out
    if work["mm_per_px_native"] > config.TILE_FLOOR_MM_PER_PX:
        out["verdict"], out["reason"] = "below_floor", REASON_COARSER_THAN_FLOOR
        return out

    positions, side, rows, cols = tile_positions(
        work["native_px_width"], work["native_px_height"], work["mm_per_px_native"]
    )
    out.update(
        tile_side_native_px=side,
        grid_rows=rows,
        grid_cols=cols,
        tiles_available=rows * cols,
    )
    if not positions:
        out["verdict"], out["reason"] = "below_floor", REASON_TOO_FEW_TILES
        return out

    out["verdict"], out["reason"] = "eligible", REASON_OK
    out["tiles_planned"] = len(positions)
    out["positions"] = positions
    return out


def load_works() -> list[dict]:
    if not config.DB_PATH.is_file():
        raise FileNotFoundError(f"{config.DB_PATH} missing; run acquire.py first")
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT object_number, split, pupil_tier, title, iiif_id, "
            "native_px_width, native_px_height, mm_per_px_native "
            "FROM works WHERE split IN (?,?,?,?) ORDER BY object_number",
            SCORED_SPLITS,
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------
# fetching
# --------------------------------------------------------------------------

def tile_path(object_number: str, row: int, col: int) -> Path:
    return TILE_ROOT / object_number / f"{row:03d}_{col:03d}.jpg"


def fetch_tile(
    iiif_id: str,
    x: int,
    y: int,
    side: int,
    dest: Path,
    *,
    retries: int = 2,
) -> int:
    url = config.IIIF_REGION_TMPL.format(
        identifier=iiif_id,
        x=x, y=y, w=side, h=side,
        tw=config.TILE_SIZE_PX, th=config.TILE_SIZE_PX,
    )
    last: Exception | None = None
    for _ in range(retries + 1):
        try:
            r = rijks_api.SESSION.get(url, timeout=config.REQUEST_TIMEOUT_S)
            r.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(r.content)
            return len(r.content)
        except (requests.RequestException, OSError) as exc:
            last = exc
    assert last is not None
    raise last


def fetch_work(plan: dict, work: dict, *, force: bool) -> tuple[int, int, list[dict]]:
    """Fetch this work's planned tiles. Returns (n_ok, n_bytes, failures)."""
    ok = 0
    total_bytes = 0
    failures: list[dict] = []
    for row, col, side in plan["positions"]:
        dest = tile_path(plan["object_number"], row, col)
        if dest.is_file() and not force:
            ok += 1
            total_bytes += dest.stat().st_size
            continue
        x, y = tile_origin(
            row, col, side, work["native_px_width"], work["native_px_height"]
        )
        try:
            total_bytes += fetch_tile(work["iiif_id"], x, y, side, dest)
            ok += 1
        except (requests.RequestException, OSError) as exc:
            failures.append(
                {
                    "object_number": plan["object_number"],
                    "row": row,
                    "col": col,
                    "x": x,
                    "y": y,
                    "side": side,
                    "message": str(exc)[:200],
                }
            )
    return ok, total_bytes, failures


# --------------------------------------------------------------------------
# outputs
# --------------------------------------------------------------------------

def write_manifest(plans: list[dict], fetched: dict[str, int], total_bytes: int) -> None:
    eligible = [p for p in plans if p["verdict"] == "eligible"]
    payload = {
        "recipe_id": RECIPE_ID,
        "created_at": _utc_now(),
        "design": "results/phase8_tiling_design.md",
        "decision": "D34",
        "parameters": {
            "floor_mm_per_px": config.TILE_FLOOR_MM_PER_PX,
            "tile_size_mm": config.TILE_SIZE_MM,
            "tile_size_px": config.TILE_SIZE_PX,
            "edge_inset": config.TILE_EDGE_INSET,
            "tiles_per_work": config.TILES_PER_WORK,
            "selection": "evenly spaced indices over row-major grid enumeration; no RNG",
        },
        "counts": {
            "considered": len(plans),
            "eligible": len(eligible),
            "below_floor": len(plans) - len(eligible),
            "tiles_written": sum(fetched.values()),
            "bytes": total_bytes,
        },
        "object_numbers": [p["object_number"] for p in eligible],
        "splits_by_id": {p["object_number"]: p["split"] for p in eligible},
        "works": {
            p["object_number"]: {
                "split": p["split"],
                "pupil_tier": p["pupil_tier"],
                "verdict": p["verdict"],
                "reason": p["reason"],
                "mm_per_px_native": p["mm_per_px_native"],
                "tile_side_native_px": p["tile_side_native_px"],
                "grid_rows": p["grid_rows"],
                "grid_cols": p["grid_cols"],
                "tiles_available": p["tiles_available"],
                "tiles_planned": p["tiles_planned"],
                "tiles_written": fetched.get(p["object_number"], 0),
                "positions": [[r, c] for r, c, _ in p["positions"]],
            }
            for p in plans
        },
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


def write_qc(plans: list[dict], fetched: dict[str, int], failures: list[dict]) -> None:
    QC_DIR.mkdir(parents=True, exist_ok=True)
    with (QC_DIR / "coverage.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "object_number", "split", "pupil_tier", "verdict", "reason",
            "mm_per_px_native", "tile_side_native_px", "grid_rows", "grid_cols",
            "tiles_available", "tiles_planned", "tiles_written",
        ])
        for p in plans:
            w.writerow([
                p["object_number"], p["split"], p["pupil_tier"] or "",
                p["verdict"], p["reason"],
                f"{p['mm_per_px_native']:.6f}" if p["mm_per_px_native"] is not None else "",
                p["tile_side_native_px"] or "", p["grid_rows"] or "",
                p["grid_cols"] or "", p["tiles_available"] or "",
                p["tiles_planned"], fetched.get(p["object_number"], 0),
            ])
    with (QC_DIR / "failures.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f, fieldnames=["object_number", "row", "col", "x", "y", "side", "message"]
        )
        w.writeheader()
        for row in failures:
            w.writerow(row)


def write_report(plans: list[dict], fetched: dict[str, int], total_bytes: int) -> None:
    def count(pred) -> int:
        return sum(1 for p in plans if pred(p))

    elig = lambda p: p["verdict"] == "eligible"  # noqa: E731
    groups = [
        ("cohort", lambda p: p["split"] == "cohort"),
        ("pupil — Tier 1", lambda p: p["pupil_tier"] == "tier1"),
        ("pupil — Tier 2", lambda p: p["pupil_tier"] == "tier2"),
        ("validation", lambda p: p["split"] == "validation"),
        ("ambiguous", lambda p: p["split"] == "ambiguous"),
    ]
    reasons: dict[str, int] = {}
    for p in plans:
        if not elig(p):
            reasons[p["reason"]] = reasons.get(p["reason"], 0) + 1

    n_elig = count(elig)
    L = [
        "# Tiling report (`tiles_v1` / D34)",
        "",
        f"**Design:** [`results/phase8_tiling_design.md`](phase8_tiling_design.md) · "
        f"**Generated:** `{_utc_now()}`",
        "",
        "Every tile covers the same physical area of canvas, so one pixel means the "
        "same distance on every painting. No feature, embedding, or score is computed here.",
        "",
        "## Parameters (pre-registered; not tunable)",
        "",
        "| Parameter | Value |",
        "|---|---|",
        f"| resolution floor | **{config.TILE_FLOOR_MM_PER_PX} mm/px** (O07) |",
        f"| tile size | {config.TILE_SIZE_MM:.0f} mm × {config.TILE_SIZE_MM:.0f} mm "
        f"= {config.TILE_SIZE_PX} × {config.TILE_SIZE_PX} px |",
        f"| edge inset | {config.TILE_EDGE_INSET:.0%} of each edge |",
        f"| tiles per work | {config.TILES_PER_WORK}, non-overlapping |",
        "| selection | evenly spaced over the row-major grid; deterministic, no RNG |",
        "",
        "## Eligibility",
        "",
        "| Group | eligible | considered |",
        "|---|---:|---:|",
    ]
    for name, pred in groups:
        L.append(
            f"| {name} | {count(lambda p, q=pred: q(p) and elig(p))} "
            f"| {count(pred)} |"
        )
    L += [
        f"| **total** | **{n_elig}** | **{len(plans)}** |",
        "",
        f"{sum(fetched.values()):,} tiles written, {total_bytes / 1e6:.1f} MB.",
        "",
        "## Below floor",
        "",
        "Works the published imagery cannot support at this floor. They are reported "
        "as unanswerable rather than scored on inadequate pixels.",
        "",
        "| Reason | N |",
        "|---|---:|",
    ]
    labels = {
        REASON_COARSER_THAN_FLOOR: f"native resolution coarser than {config.TILE_FLOOR_MM_PER_PX} mm/px",
        REASON_TOO_FEW_TILES: f"fewer than {config.TILES_PER_WORK} tiles fit inside the inset",
        REASON_NO_GEOMETRY: "no catalogued size — run `python dimensions.py`",
        REASON_NO_IIIF: "no IIIF identifier",
    }
    for reason, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        L.append(f"| {labels.get(reason, reason)} | {n} |")

    dropped_cohort = [
        p for p in plans if p["split"] == "cohort" and not elig(p)
    ]
    L += [
        "",
        f"### Cohort works excluded ({len(dropped_cohort)} of "
        f"{count(lambda p: p['split'] == 'cohort')})",
        "",
        "These are firm Rembrandts that any later fit on this recipe cannot use.",
        "",
        "| object | native mm/px | title |",
        "|---|---:|---|",
    ]
    for p in sorted(dropped_cohort, key=lambda p: -(p["mm_per_px_native"] or 0)):
        mm = f"{p['mm_per_px_native']:.3f}" if p["mm_per_px_native"] is not None else "—"
        L.append(f"| `{p['object_number']}` | {mm} | {p['title'][:70]} |")

    L += [
        "",
        "## Verification",
        "",
        f"Every tile is requested as an IIIF region of "
        f"`tile_side_native_px` square, served at {config.TILE_SIZE_PX} px, so the "
        f"realized resolution is {config.TILE_SIZE_MM:.0f} mm ÷ {config.TILE_SIZE_PX} px "
        f"= **{config.TILE_FLOOR_MM_PER_PX:.3f} mm/px for every work**, independent of "
        "painting size. That is the property the fixed-1500 pipeline lacked.",
        "",
        "Per-work detail: `results/qc_tiles_v1/coverage.csv`. "
        "Fetch failures: `results/qc_tiles_v1/failures.csv`.",
        "",
    ]
    REPORT_PATH.write_text("\n".join(L), encoding="utf-8")


# --------------------------------------------------------------------------

def run(*, force: bool, plan_only: bool) -> int:
    works = load_works()
    by_id = {w["object_number"]: w for w in works}
    plans = [assess(w) for w in works]
    eligible = [p for p in plans if p["verdict"] == "eligible"]

    print(f"{len(works)} scored works; {len(eligible)} eligible at "
          f"{config.TILE_FLOOR_MM_PER_PX} mm/px; "
          f"{len(works) - len(eligible)} below floor")
    print(f"planned tiles: {sum(p['tiles_planned'] for p in plans):,} "
          f"({config.TILE_SIZE_PX}x{config.TILE_SIZE_PX} px, "
          f"{config.TILE_SIZE_MM:.0f}mm of canvas each)")

    if plan_only:
        for p in plans:
            if p["verdict"] != "eligible":
                print(f"  below floor: {p['object_number']:11s} {p['reason']}")
        return 0

    fetched: dict[str, int] = {}
    failures: list[dict] = []
    total_bytes = 0
    for i, p in enumerate(eligible, 1):
        ok, nbytes, fails = fetch_work(p, by_id[p["object_number"]], force=force)
        fetched[p["object_number"]] = ok
        failures.extend(fails)
        total_bytes += nbytes
        if i % 10 == 0 or i == len(eligible):
            print(f"  [{i}/{len(eligible)}] {sum(fetched.values()):,} tiles, "
                  f"{total_bytes / 1e6:.1f} MB")

    write_manifest(plans, fetched, total_bytes)
    write_qc(plans, fetched, failures)
    write_report(plans, fetched, total_bytes)
    print(f"Wrote {MANIFEST_PATH}")
    print(f"Wrote {QC_DIR} (failures={len(failures)})")
    print(f"Wrote {REPORT_PATH}")

    short = [oid for oid, n in fetched.items() if n < config.TILES_PER_WORK]
    if short:
        print(f"WARNING: {len(short)} works have fewer than "
              f"{config.TILES_PER_WORK} tiles: {short[:10]}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Physically-normalized tiling (D34)")
    parser.add_argument("--force", action="store_true", help="Re-fetch every tile")
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Report eligibility and the tile plan without touching the network",
    )
    args = parser.parse_args()
    return run(force=args.force, plan_only=args.plan)


if __name__ == "__main__":
    raise SystemExit(main())
