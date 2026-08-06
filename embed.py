"""
Phase 3 Wave B: ResNet50 embedding extract (D13 / D29 / embed_v1).

Reads Branch C preprocess tensors only (`preprocess_v1/cnn/*.pt`).
No finetune, no scoring, no DINOv2. Features use Branch H — not this module.

Usage (from repo root, mamba env CohortScope):
  python embed.py           # write embed_v1 cache + QC
  python embed.py --force   # overwrite existing embed_v1 outputs
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import torch
import torchvision
from torch import nn
from torchvision.models import ResNet50_Weights, resnet50

import config

RECIPE_ID = "embed_v1"
PREPROCESS_RECIPE = "preprocess_v1"
EMBED_DIM = 2048
BATCH_SIZE = 1
SCORED_SPLITS = ("cohort", "validation", "ambiguous")

PREPROCESS_ROOT = config.DATA_DIR / "preprocessed" / PREPROCESS_RECIPE
CNN_DIR = PREPROCESS_ROOT / "cnn"
PREPROCESS_MANIFEST = PREPROCESS_ROOT / "manifest.json"

EMBED_ROOT = config.DATA_DIR / "embeddings" / RECIPE_ID
VECTORS_DIR = EMBED_ROOT / "vectors"
MATRIX_PATH = EMBED_ROOT / "matrix.pt"
MANIFEST_PATH = EMBED_ROOT / "manifest.json"
QC_DIR = config.RESULTS_DIR / f"qc_{RECIPE_ID}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_preprocess_worklist() -> tuple[list[str], dict[str, str]]:
    if not PREPROCESS_MANIFEST.is_file():
        raise FileNotFoundError(f"Preprocess manifest missing: {PREPROCESS_MANIFEST}")
    with PREPROCESS_MANIFEST.open(encoding="utf-8") as f:
        meta = json.load(f)
    if meta.get("recipe_id") != PREPROCESS_RECIPE:
        raise ValueError(
            f"unexpected preprocess recipe_id={meta.get('recipe_id')!r}; "
            f"expected {PREPROCESS_RECIPE!r}"
        )
    object_numbers = list(meta["object_numbers"])
    splits_by_id = dict(meta.get("splits_by_id", {}))
    if sorted(object_numbers) != object_numbers:
        object_numbers = sorted(object_numbers)
    if len(object_numbers) != 25:
        raise ValueError(f"expected N=25 scored IDs, got {len(object_numbers)}")
    missing_split = [oid for oid in object_numbers if oid not in splits_by_id]
    if missing_split:
        raise ValueError(f"splits_by_id missing IDs: {missing_split[:5]}")
    return object_numbers, splits_by_id


def build_model(device: torch.device) -> nn.Module:
    if config.BACKBONE != "resnet50":
        raise ValueError(f"unsupported BACKBONE={config.BACKBONE!r}; D13 locks resnet50")
    if config.BACKBONE_WEIGHTS != "IMAGENET1K_V2":
        raise ValueError(
            f"unsupported BACKBONE_WEIGHTS={config.BACKBONE_WEIGHTS!r}; "
            "D13 locks IMAGENET1K_V2"
        )
    weights = ResNet50_Weights.IMAGENET1K_V2
    model = resnet50(weights=weights)
    model.fc = nn.Identity()
    model.eval()
    for p in model.parameters():
        p.requires_grad_(False)
    return model.to(device)


def load_branch_c(object_number: str) -> torch.Tensor:
    path = CNN_DIR / f"{object_number}.pt"
    if not path.is_file():
        raise FileNotFoundError(f"Branch C missing: {path}")
    tensor = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(tensor, torch.Tensor):
        raise TypeError(f"{path}: expected Tensor, got {type(tensor)}")
    if tuple(tensor.shape) != (3, 224, 224):
        raise ValueError(f"{path}: bad shape {tuple(tensor.shape)}; expected (3, 224, 224)")
    if tensor.dtype != torch.float32:
        tensor = tensor.float()
    return tensor


@torch.inference_mode()
def embed_one(model: nn.Module, tensor_chw: torch.Tensor, device: torch.device) -> torch.Tensor:
    batch = tensor_chw.unsqueeze(0).to(device, non_blocking=False)
    if batch.shape[0] != BATCH_SIZE:
        raise RuntimeError(f"batch_size must be {BATCH_SIZE}, got {batch.shape[0]}")
    out = model(batch)
    vec = out.squeeze(0).detach().float().cpu().reshape(-1)
    if tuple(vec.shape) != (EMBED_DIM,):
        raise ValueError(f"bad embedding shape {tuple(vec.shape)}; expected ({EMBED_DIM},)")
    if not torch.isfinite(vec).all():
        raise ValueError("non-finite embedding values")
    return vec


def write_failures(rows: list[dict]) -> Path:
    QC_DIR.mkdir(parents=True, exist_ok=True)
    path = QC_DIR / "failures.csv"
    fields = ("object_number", "ok", "stage", "message", "l2_norm")
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fields})
    return path


def write_manifest(
    object_numbers: list[str],
    splits_by_id: dict[str, str],
    *,
    device: str,
    l2_stats: dict[str, float],
) -> None:
    payload = {
        "recipe_id": RECIPE_ID,
        "backbone": config.BACKBONE,
        "backbone_weights": config.BACKBONE_WEIGHTS,
        "dim": EMBED_DIM,
        "pool": "adaptive_avgpool",
        "batch_size": BATCH_SIZE,
        "preprocess_recipe": PREPROCESS_RECIPE,
        "input": "branch_c_pt",
        "splits_included": list(SCORED_SPLITS),
        "object_numbers": object_numbers,
        "splits_by_id": {oid: splits_by_id[oid] for oid in object_numbers},
        "n": len(object_numbers),
        "device": device,
        "l2_norm": l2_stats,
        "versions": {
            "torch": torch.__version__,
            "torchvision": torchvision.__version__,
        },
        "design": "results/phase3_embedding_design.md",
        "matrix_contract": "results/phase3_matrix_contract.md",
        "geometry_note": "results/qc_preprocess_v1/geometry_note.md",
        "decision": "D29",
        "created_at": _utc_now(),
    }
    with MANIFEST_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="ResNet50 embed_v1 extractor (D29)")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing embed_v1 vectors/matrix/manifest",
    )
    args = parser.parse_args()

    object_numbers, splits_by_id = load_preprocess_worklist()
    EMBED_ROOT.mkdir(parents=True, exist_ok=True)
    VECTORS_DIR.mkdir(parents=True, exist_ok=True)

    if not args.force and MATRIX_PATH.is_file() and MANIFEST_PATH.is_file():
        existing = sorted(p.stem for p in VECTORS_DIR.glob("*.pt"))
        if existing == object_numbers:
            print(f"{RECIPE_ID} already complete (N={len(existing)}); pass --force to redo")
            return 0

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"device={device} batch_size={BATCH_SIZE} backbone={config.BACKBONE}")

    model = build_model(device)
    failure_rows: list[dict] = []
    vectors: dict[str, torch.Tensor] = {}
    norms: list[float] = []

    for oid in object_numbers:
        stage = "load"
        try:
            tensor = load_branch_c(oid)
            stage = "forward"
            vec = embed_one(model, tensor, device)
            stage = "write"
            out_path = VECTORS_DIR / f"{oid}.pt"
            if out_path.is_file() and not args.force:
                # Still recompute into matrix for consistency when partial
                pass
            torch.save(vec, out_path)
            vectors[oid] = vec
            nrm = float(torch.linalg.vector_norm(vec).item())
            norms.append(nrm)
            failure_rows.append(
                {
                    "object_number": oid,
                    "ok": "true",
                    "stage": "",
                    "message": "",
                    "l2_norm": f"{nrm:.6f}",
                }
            )
            print(f"  ok {oid} ({splits_by_id[oid]}) dim={EMBED_DIM} l2={nrm:.4f}")
        except Exception as exc:  # noqa: BLE001 — per-ID QC log
            failure_rows.append(
                {
                    "object_number": oid,
                    "ok": "false",
                    "stage": stage,
                    "message": str(exc),
                    "l2_norm": "",
                }
            )
            print(f"  FAIL {oid} [{stage}]: {exc}", file=sys.stderr)

    write_failures(failure_rows)
    ok_ids = [oid for oid in object_numbers if oid in vectors]
    if ok_ids != object_numbers:
        print(
            f"incomplete: ok={len(ok_ids)} expected={len(object_numbers)}",
            file=sys.stderr,
        )
        return 1

    X = torch.stack([vectors[oid] for oid in object_numbers], dim=0)
    if tuple(X.shape) != (len(object_numbers), EMBED_DIM):
        raise RuntimeError(f"bad matrix shape {tuple(X.shape)}")
    torch.save({"object_numbers": object_numbers, "X": X}, MATRIX_PATH)

    norms_t = torch.tensor(norms, dtype=torch.float32)
    l2_stats = {
        "min": float(norms_t.min().item()),
        "median": float(norms_t.median().item()),
        "max": float(norms_t.max().item()),
    }
    write_manifest(
        object_numbers,
        splits_by_id,
        device=str(device),
        l2_stats=l2_stats,
    )

    print(
        f"wrote {MATRIX_PATH} shape={tuple(X.shape)}; "
        f"vectors={len(ok_ids)}; l2 min/med/max="
        f"{l2_stats['min']:.4f}/{l2_stats['median']:.4f}/{l2_stats['max']:.4f}"
    )
    print(f"QC: {QC_DIR / 'failures.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
