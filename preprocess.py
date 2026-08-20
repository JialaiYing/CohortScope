"""
Phase 2 Wave B: deterministic preprocess cache (D26 / preprocess_v1).

Consumer contract:
  - Features (hand-built) reads Branch H PNGs only (`rgb/`).
  - Branch C tensors (`cnn/`) are embeddings-only (ResNet50 input); do not
    feed them to interpretable feature extractors.

Usage (from repo root, mamba env CohortScope):
  python preprocess.py           # write rgb/ + cnn/ caches + QC
  python preprocess.py --force   # overwrite existing preprocess_v1 outputs
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import torch
import torchvision
from PIL import Image, ImageOps
from torchvision import transforms

import config

RECIPE_ID = "preprocess_v1"
SCORED_SPLITS = ("cohort", "validation", "ambiguous", "pupil")  # D32 adds pupil

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
CNN_RESIZE_SHORT = 256
CNN_CROP = 224

CACHE_ROOT = config.DATA_DIR / "preprocessed" / RECIPE_ID
RGB_DIR = CACHE_ROOT / "rgb"
CNN_DIR = CACHE_ROOT / "cnn"
QC_DIR = config.RESULTS_DIR / f"qc_{RECIPE_ID}"

CNN_TRANSFORM = transforms.Compose(
    [
        transforms.Resize(CNN_RESIZE_SHORT),
        transforms.CenterCrop(CNN_CROP),
        transforms.ToTensor(),
        transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ]
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_scored_works(db_path: Path) -> list[dict]:
    if not db_path.is_file():
        raise FileNotFoundError(f"SQLite missing: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT object_number, split, image_path
            FROM works
            WHERE split IN ('cohort', 'validation', 'ambiguous', 'pupil')
            ORDER BY object_number
            """
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def decode_rgb(image_path: Path) -> Image.Image:
    """Shared decode: load → EXIF transpose → RGB (design §1.1)."""
    with Image.open(image_path) as im:
        im = ImageOps.exif_transpose(im)
        return im.convert("RGB")


def tensor_to_uint8_rgb(t: torch.Tensor) -> Image.Image:
    """Denormalize ImageNet tensor for QC visualization only."""
    mean = torch.tensor(IMAGENET_MEAN, dtype=t.dtype).view(3, 1, 1)
    std = torch.tensor(IMAGENET_STD, dtype=t.dtype).view(3, 1, 1)
    x = (t * std + mean).clamp(0.0, 1.0)
    arr = (x * 255.0).byte().permute(1, 2, 0).cpu().numpy()
    return Image.fromarray(arr, mode="RGB")


def process_one(
    object_number: str,
    image_path: Path,
    *,
    force: bool,
) -> tuple[Image.Image, torch.Tensor]:
    rgb_out = RGB_DIR / f"{object_number}.png"
    cnn_out = CNN_DIR / f"{object_number}.pt"
    if not force and rgb_out.is_file() and cnn_out.is_file():
        rgb = Image.open(rgb_out).convert("RGB")
        tensor = torch.load(cnn_out, map_location="cpu", weights_only=True)
        return rgb, tensor

    rgb = decode_rgb(image_path)
    tensor = CNN_TRANSFORM(rgb)

    RGB_DIR.mkdir(parents=True, exist_ok=True)
    CNN_DIR.mkdir(parents=True, exist_ok=True)
    rgb.save(rgb_out, format="PNG")
    torch.save(tensor, cnn_out)
    return rgb, tensor


def pick_qc_ids(works: list[dict], rgb_sizes: dict[str, tuple[int, int]]) -> list[str]:
    """Fixed recipe: aspect quantiles among cohort + val + ambiguous (not score-based)."""
    cohort = [w for w in works if w["split"] == "cohort"]
    cohort_sorted = sorted(
        cohort,
        key=lambda w: rgb_sizes[w["object_number"]][0]
        / max(rgb_sizes[w["object_number"]][1], 1),
    )
    n = len(cohort_sorted)
    idxs = sorted({0, n // 3, (2 * n) // 3, n - 1})
    ids = [cohort_sorted[i]["object_number"] for i in idxs]
    for w in works:
        if w["split"] in ("validation", "ambiguous"):
            ids.append(w["object_number"])
    # de-dupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for oid in ids:
        if oid not in seen:
            seen.add(oid)
            out.append(oid)
    return out


def write_qc_grid(
    qc_ids: list[str],
    sources: dict[str, Path],
    rgb_images: dict[str, Image.Image],
    cnn_tensors: dict[str, torch.Tensor],
    splits: dict[str, str],
) -> Path:
    """3-row strip per id: before | Branch H | Branch C denorm (viz only)."""
    thumb_h = 180
    gap = 8
    label_h = 28
    panels: list[Image.Image] = []
    row_meta: list[str] = []

    for oid in qc_ids:
        before = Image.open(sources[oid]).convert("RGB")
        after_h = rgb_images[oid]
        after_c = tensor_to_uint8_rgb(cnn_tensors[oid])

        def _thumb(im: Image.Image) -> Image.Image:
            w, h = im.size
            scale = thumb_h / h
            return im.resize((max(1, int(w * scale)), thumb_h), Image.Resampling.BILINEAR)

        panels.append(_thumb(before))
        panels.append(_thumb(after_h))
        panels.append(_thumb(after_c))
        row_meta.append(f"{oid} ({splits[oid]})")

    # layout: each work is one row of 3 panels
    n_rows = len(qc_ids)
    cell_ws = []
    for r in range(n_rows):
        trio = panels[r * 3 : (r + 1) * 3]
        cell_ws.append(sum(p.size[0] for p in trio) + 2 * gap)
    canvas_w = max(cell_ws) + 2 * gap
    canvas_h = n_rows * (thumb_h + label_h + gap) + gap

    canvas = Image.new("RGB", (canvas_w, canvas_h), (245, 245, 245))
    # draw via paste; labels as tiny PIL default font text via a simple bar
    from PIL import ImageDraw, ImageFont

    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.load_default()
    except OSError:
        font = None

    y = gap
    for r, oid in enumerate(qc_ids):
        draw.rectangle([0, y, canvas_w, y + label_h], fill=(230, 230, 230))
        label = (
            f"{row_meta[r]}  |  L→R: raw IIIF | Branch H PNG | Branch C denorm (viz only)"
        )
        draw.text((gap, y + 6), label, fill=(20, 20, 20), font=font)
        y += label_h
        x = gap
        for p in panels[r * 3 : (r + 1) * 3]:
            canvas.paste(p, (x, y))
            x += p.size[0] + gap
        y += thumb_h + gap

    QC_DIR.mkdir(parents=True, exist_ok=True)
    out = QC_DIR / "before_after_grid.png"
    canvas.save(out)
    return out


def write_failures(rows: list[dict]) -> Path:
    QC_DIR.mkdir(parents=True, exist_ok=True)
    path = QC_DIR / "failures.csv"
    fields = ("object_number", "split", "stage", "error", "ok")
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow(row)
    return path


def write_manifest(object_numbers: list[str], splits_by_id: dict[str, str]) -> Path:
    CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    payload = {
        "recipe_id": RECIPE_ID,
        "created_at": _utc_now(),
        "source_edge": config.IIIF_MAX_EDGE,
        "backbone": config.BACKBONE,
        "backbone_weights": config.BACKBONE_WEIGHTS,
        "cnn": {
            "resize_short": CNN_RESIZE_SHORT,
            "crop": CNN_CROP,
            "mean": list(IMAGENET_MEAN),
            "std": list(IMAGENET_STD),
            "weights": config.BACKBONE_WEIGHTS,
        },
        "splits_included": list(SCORED_SPLITS),
        "object_numbers": object_numbers,
        "splits_by_id": splits_by_id,
        "n": len(object_numbers),
        "versions": {
            "torch": torch.__version__,
            "torchvision": torchvision.__version__,
            "pillow": Image.__version__,
        },
        "design": "results/phase2_preprocess_design.md",
        "decision": "D26",
    }
    path = CACHE_ROOT / "manifest.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cohortscope Phase 2 preprocess_v1")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing rgb/cnn cache files",
    )
    args = parser.parse_args(argv)

    works = load_scored_works(config.DB_PATH)
    if not works:
        print("No scored works found in SQLite.", file=sys.stderr)
        return 1

    failure_rows: list[dict] = []
    rgb_images: dict[str, Image.Image] = {}
    cnn_tensors: dict[str, torch.Tensor] = {}
    rgb_sizes: dict[str, tuple[int, int]] = {}
    sources: dict[str, Path] = {}
    splits: dict[str, str] = {}
    ok_ids: list[str] = []

    print(f"Preprocess {RECIPE_ID}: {len(works)} scored works → {CACHE_ROOT}")

    for w in works:
        oid = w["object_number"]
        split = w["split"]
        splits[oid] = split
        rel = w["image_path"]
        if not rel:
            failure_rows.append(
                {
                    "object_number": oid,
                    "split": split,
                    "stage": "load",
                    "error": "image_path is null",
                    "ok": "false",
                }
            )
            continue
        src = config.ROOT / rel
        sources[oid] = src
        try:
            if not src.is_file():
                raise FileNotFoundError(f"missing image: {src}")
            rgb, tensor = process_one(oid, src, force=args.force)
            if tuple(tensor.shape) != (3, CNN_CROP, CNN_CROP):
                raise ValueError(f"bad cnn shape {tuple(tensor.shape)}")
            rgb_images[oid] = rgb
            cnn_tensors[oid] = tensor
            rgb_sizes[oid] = rgb.size
            ok_ids.append(oid)
            failure_rows.append(
                {
                    "object_number": oid,
                    "split": split,
                    "stage": "write",
                    "error": "",
                    "ok": "true",
                }
            )
            print(f"  ok {oid} ({split}) rgb={rgb.size} cnn={tuple(tensor.shape)}")
        except Exception as exc:  # noqa: BLE001 — log every failure for QC
            stage = "load"
            msg = str(exc)
            if "cnn" in msg.lower() or "shape" in msg.lower():
                stage = "cnn"
            elif "png" in msg.lower() or "write" in msg.lower():
                stage = "write"
            failure_rows.append(
                {
                    "object_number": oid,
                    "split": split,
                    "stage": stage,
                    "error": msg,
                    "ok": "false",
                }
            )
            print(f"  FAIL {oid}: {exc}", file=sys.stderr)

    fail_path = write_failures(failure_rows)
    n_fail = sum(1 for r in failure_rows if r["ok"] == "false")

    if len(ok_ids) != len(works) or n_fail:
        print(
            f"Incomplete: ok={len(ok_ids)} expected={len(works)} failures={n_fail}",
            file=sys.stderr,
        )
        print(f"Failures log: {fail_path}")
        return 1

    # Sanity: file counts
    rgb_files = sorted(p.stem for p in RGB_DIR.glob("*.png"))
    cnn_files = sorted(p.stem for p in CNN_DIR.glob("*.pt"))
    if rgb_files != ok_ids or cnn_files != ok_ids:
        print("Cache file set mismatch vs ok_ids", file=sys.stderr)
        print(f"  rgb={len(rgb_files)} cnn={len(cnn_files)} ok={len(ok_ids)}")
        return 1

    manifest = write_manifest(ok_ids, splits)
    qc_ids = pick_qc_ids(works, rgb_sizes)
    grid = write_qc_grid(qc_ids, sources, rgb_images, cnn_tensors, splits)

    print(f"Manifest: {manifest}")
    print(f"QC grid:  {grid} (ids={qc_ids})")
    print(f"Failures: {fail_path} (n_fail={n_fail})")
    print(f"Done: {len(ok_ids)} works cached under {CACHE_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
