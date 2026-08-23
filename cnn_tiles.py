"""
Phase 10 Wave A: 224 px tile acquisition for Signal A (D36 / O10 / cnn_tiles_v1).

The same physically-normalized tiling as D34, with one derived constant changed:
each tile covers 44.8 mm x 44.8 mm of canvas and is served at 224 x 224 px.

  224 px (ResNet50 input size, config.BACKBONE)  x  0.20 mm/px (O07)  =  44.8 mm

So the region arrives at both the locked resolution floor and the backbone's
native input size, and **nothing is resized, cropped, or interpolated** on the way
into the CNN. That is the whole point: D35 §2 excluded Signal A from `tiles_v1`
because a 150 px tile would have needed a per-work resample factor, which is the
arbitrariness D34 exists to remove.

Floor, edge inset, tiles per work, and the deterministic selection rule are
unchanged and shared with `tiles.py` — there is one implementation of the
selection rule, not two, so the recipes cannot drift apart.

This module computes no embedding and no score. It only fetches.

Reads : data/cohortscope.sqlite (geometry from D33)
Writes: data/tiles/cnn_tiles_v1/{object_number}/{row}_{col}.jpg
        data/tiles/cnn_tiles_v1/manifest.json
        results/qc_cnn_tiles_v1/{coverage.csv,failures.csv}
        results/cnn_tiling_report.md

Usage (repo root, mamba env CohortScope):
  python cnn_tiles.py            # fetch missing tiles
  python cnn_tiles.py --plan     # eligibility + tile plan only; no network
  python cnn_tiles.py --force    # re-fetch every tile
"""

from __future__ import annotations

import argparse

import tiles

RECIPE = tiles.CNN_TILES_V1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="224 px physically-normalized tiling for Signal A (D36)"
    )
    parser.add_argument("--force", action="store_true", help="Re-fetch every tile")
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Report eligibility and the tile plan without touching the network",
    )
    args = parser.parse_args()
    return tiles.run(force=args.force, plan_only=args.plan, rec=RECIPE)


if __name__ == "__main__":
    raise SystemExit(main())
