"""
Phase 10 Wave B: ResNet50 embeddings of 224 px tiles (D36 / tile_embed_v1).

Implements `results/phase10_tile_embedding_design.md` §2, which was committed
before any 224 px tile was fetched.

The backbone, the weights, and the layer are **identical** to `embed_v1` — this
module reuses `embed.build_model()` rather than constructing its own, so the two
cannot drift. The only difference between `embed_v1` and this recipe is the
geometry of what goes in:

  embed_v1        JPEG -> resize short edge to 256 -> centre-crop 224 -> normalize
  tile_embed_v1   IIIF region already 224 px at 0.20 mm/px -> normalize

There is **no resize and no crop here**. A 44.8 mm tile at 0.20 mm/px is exactly
224 px, so the tile *is* the CNN input. That is the property D35 §2 said Signal A
could not have on `tiles_v1`, and the reason this recipe exists.

Reads : data/tiles/cnn_tiles_v1/manifest.json + the tile JPEGs it names
Writes: data/embeddings/tile_embed_v1/matrix.pt (+ manifest.json)
QC    : results/qc_tile_embed_v1/{failures.csv,summary.json}

One 2048-d vector per tile. No aggregation, no centroid, no distance, no score —
those are §4/§5 and live in `tile_score_a.py`.

Usage (repo root, mamba env CohortScope):
  python tile_embed.py
  python tile_embed.py --force
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from PIL import Image

import config
import embed
import preprocess
import tiles

RECIPE_ID = "tile_embed_v1"
TILES_RECIPE = tiles.CNN_TILES_V1
DESIGN_DOC = "results/phase10_tile_embedding_design.md"
DECISION = "D36"
EMBED_DIM = embed.EMBED_DIM

OUT_DIR = config.DATA_DIR / "embeddings" / RECIPE_ID
MATRIX_PATH = OUT_DIR / "matrix.pt"
MANIFEST_PATH = OUT_DIR / "manifest.json"
QC_DIR = config.RESULTS_DIR / f"qc_{RECIPE_ID}"
FAILURES_PATH = QC_DIR / "failures.csv"
SUMMARY_PATH = QC_DIR / "summary.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_tile_manifest() -> dict:
    """Recipe-ID contract: the upstream manifest is the worklist."""
    path = TILES_RECIPE.manifest_path
    if not path.is_file():
        raise FileNotFoundError(f"missing {path}; run `python cnn_tiles.py` first")
    with path.open(encoding="utf-8") as f:
        man = json.load(f)
    if man.get("recipe_id") != TILES_RECIPE.recipe_id:
        raise ValueError(
            f"expected recipe_id={TILES_RECIPE.recipe_id}, got {man.get('recipe_id')!r}"
        )
    px = man["parameters"]["tile_size_px"]
    if px != config.CNN_TILE_SIZE_PX:
        raise ValueError(
            f"tile manifest says {px} px but the backbone wants "
            f"{config.CNN_TILE_SIZE_PX}; this recipe exists precisely so no resize "
            "is needed, so a mismatch is fatal rather than something to resize away"
        )
    return man


def load_tile(path: Path) -> torch.Tensor:
    """
    Tile JPEG -> normalized CHW float tensor, CNN-ready.

    Deliberately *not* `preprocess.build_cnn_transform()`: that pipeline resizes
    the short edge to 256 and centre-crops to 224, which would change what a
    pixel means per work. Here the tile is already the exact input size, so the
    only step applied is the ImageNet normalization the pretrained weights
    require — a colour transform, not a geometric one.
    """
    with Image.open(path) as im:
        arr = np.asarray(im.convert("RGB"), dtype=np.uint8)
    want = config.CNN_TILE_SIZE_PX
    if arr.shape[:2] != (want, want):
        raise ValueError(f"expected {want}x{want} tile, got {arr.shape[1]}x{arr.shape[0]}")
    t = torch.from_numpy(arr.copy()).permute(2, 0, 1).float().div_(255.0)
    mean = torch.tensor(preprocess.IMAGENET_MEAN, dtype=t.dtype).view(3, 1, 1)
    std = torch.tensor(preprocess.IMAGENET_STD, dtype=t.dtype).view(3, 1, 1)
    return (t - mean) / std


def worklist(man: dict) -> list[tuple[str, int, int]]:
    out: list[tuple[str, int, int]] = []
    for oid in man["object_numbers"]:
        entry = man["works"][oid]
        if entry["verdict"] != "eligible":
            raise ValueError(f"{oid} in object_numbers but verdict={entry['verdict']}")
        for row, col in entry["positions"]:
            out.append((oid, row, col))
    return out


def run(*, force: bool) -> int:
    if MATRIX_PATH.is_file() and not force:
        print(f"Refusing to overwrite {MATRIX_PATH}; pass --force", file=sys.stderr)
        return 2

    man = load_tile_manifest()
    items = worklist(man)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"{RECIPE_ID}: {len(items):,} tiles over {len(man['object_numbers'])} works")
    print(f"device={device} backbone={config.BACKBONE}/{config.BACKBONE_WEIGHTS}")
    print("no resize, no crop: the 224 px tile is the CNN input")

    model = embed.build_model(device)  # identical to embed_v1, not a copy

    vecs: list[torch.Tensor] = []
    keys: list[tuple[str, int, int]] = []
    failures: list[dict] = []
    for i, (oid, row, col) in enumerate(items, 1):
        path = tiles.tile_path(oid, row, col, TILES_RECIPE)
        try:
            vec = embed.embed_one(model, load_tile(path), device)
            vecs.append(vec)
            keys.append((oid, row, col))
        except Exception as exc:  # noqa: BLE001 -- log per tile, never drop silently
            failures.append(
                {"object_number": oid, "row": row, "col": col, "error": str(exc)[:200]}
            )
        if i % 200 == 0 or i == len(items):
            print(f"  [{i}/{len(items)}] {len(vecs):,} embedded")

    if not vecs:
        print("ERROR: no tile embedded", file=sys.stderr)
        return 1

    x = torch.stack(vecs, dim=0)
    if tuple(x.shape[1:]) != (EMBED_DIM,):
        raise ValueError(f"bad matrix shape {tuple(x.shape)}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "recipe_id": RECIPE_ID,
            "X": x,
            "object_numbers": [k[0] for k in keys],
            "tile_rows": [k[1] for k in keys],
            "tile_cols": [k[2] for k in keys],
        },
        MATRIX_PATH,
    )

    per_work: dict[str, int] = {}
    for oid, _, _ in keys:
        per_work[oid] = per_work.get(oid, 0) + 1

    manifest = {
        "recipe_id": RECIPE_ID,
        "tiles_recipe": TILES_RECIPE.recipe_id,
        "created_at": _utc_now(),
        "design": DESIGN_DOC,
        "decision": DECISION,
        "backbone": config.BACKBONE,
        "backbone_weights": config.BACKBONE_WEIGHTS,
        "layer": "penultimate global-average pool (fc = Identity)",
        "model_source": "embed.build_model -- shared with embed_v1, not a copy",
        "embed_dim": EMBED_DIM,
        "input_geometry": {
            "tile_size_px": config.CNN_TILE_SIZE_PX,
            "tile_size_mm": config.CNN_TILE_SIZE_MM,
            "mm_per_px": config.TILE_FLOOR_MM_PER_PX,
            "resize": None,
            "crop": None,
            "note": "224 px at 0.20 mm/px = 44.8 mm; the tile is the CNN input",
        },
        "normalization": {
            "imagenet_mean": list(preprocess.IMAGENET_MEAN),
            "imagenet_std": list(preprocess.IMAGENET_STD),
        },
        "n_tiles": len(keys),
        "n_works": len(per_work),
        "tiles_per_work": per_work,
        "object_numbers": sorted(per_work),
        "splits_by_id": {o: man["works"][o]["split"] for o in sorted(per_work)},
        "pupil_tier_by_id": {
            o: (man["works"][o].get("pupil_tier") or "") for o in sorted(per_work)
        },
        "matrix": MATRIX_PATH.relative_to(config.ROOT).as_posix(),
        "no_aggregation": True,
        "no_distance": True,
        "no_score": True,
        "device": str(device),
        "torch": torch.__version__,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    QC_DIR.mkdir(parents=True, exist_ok=True)
    with FAILURES_PATH.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["object_number", "row", "col", "error"])
        w.writeheader()
        w.writerows(failures)
    SUMMARY_PATH.write_text(
        json.dumps(
            {
                "recipe_id": RECIPE_ID,
                "created_at": _utc_now(),
                "n_tiles_expected": len(items),
                "n_tiles_embedded": len(keys),
                "n_failures": len(failures),
                "n_works": len(per_work),
                "works_short_of_20": {o: n for o, n in per_work.items() if n < 20},
                "design": DESIGN_DOC,
                "decision": DECISION,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Wrote {MATRIX_PATH}  [{tuple(x.shape)}]")
    print(f"Wrote {MANIFEST_PATH}")
    print(f"Wrote {QC_DIR} (failures={len(failures)})")
    return 0 if not failures else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Embed 224 px tiles (tile_embed_v1 / D36)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing matrix")
    args = parser.parse_args()
    try:
        return run(force=args.force)
    except Exception as exc:  # noqa: BLE001 -- CLI surface
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
