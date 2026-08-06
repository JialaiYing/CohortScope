"""
Phase 3 Wave B: hand-built O03 features from Branch H only (D29).

Reads: data/preprocessed/preprocess_v1/rgb/{object_number}.png
Writes: data/features/features_v1.csv (+ dictionary, manifest)
QC: results/qc_features_v1/failures.csv

No z-scores, no cohort fits, no Branch C, no anomaly scores.

Usage (repo root, mamba env CohortScope):
  python features.py
  python features.py --force
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

import config

RECIPE_ID = "features_v1"
PREPROCESS_RECIPE = "preprocess_v1"
SCORED_SPLITS = ("cohort", "validation", "ambiguous")

FEATURE_COLUMNS = (
    "grad_mag_mean",
    "grad_mag_std",
    "grad_orient_entropy",
    "laplacian_var",
    "lbp_entropy",
    "glcm_contrast",
    "lab_chroma_mean",
    "hue_circ_std",
)

RGB_DIR = config.DATA_DIR / "preprocessed" / PREPROCESS_RECIPE / "rgb"
OUT_DIR = config.DATA_DIR / "features"
CSV_PATH = OUT_DIR / f"{RECIPE_ID}.csv"
DICT_PATH = OUT_DIR / f"{RECIPE_ID}_dictionary.md"
MANIFEST_PATH = OUT_DIR / "manifest.json"
QC_DIR = config.RESULTS_DIR / f"qc_{RECIPE_ID}"
FAILURES_PATH = QC_DIR / "failures.csv"

# Locked compute defaults (results/phase3_feature_shortlist.md §1)
LUM_WEIGHTS = (0.2989, 0.5870, 0.1140)
ORIENT_BINS = 8
LBP_P = 8
LBP_R = 1
GLCM_LEVELS = 32
GLCM_DISTANCE = 1
GLCM_ANGLES_DEG = (0.0, 45.0, 90.0, 135.0)
HUE_CHROMA_MIN = 5.0  # Lab chroma; near-gray ignored for hue only

FEATURE_MEANINGS = {
    "grad_mag_mean": "Average edge strength (Sobel) — overall surface busy-ness",
    "grad_mag_std": "Spread of edge strength — smooth passages vs local impasto/edge clusters",
    "grad_orient_entropy": "How evenly stroke/edge directions are spread — ordered vs chaotic",
    "laplacian_var": "High-frequency energy (Laplacian variance) — fine grain vs flat paint",
    "lbp_entropy": "Local Binary Pattern histogram entropy — micro-texture complexity",
    "glcm_contrast": "Gray-level co-occurrence contrast — local tonal jumps",
    "lab_chroma_mean": "Mean Lab chroma sqrt(a*^2+b*^2) — how colorful vs muted overall",
    "hue_circ_std": "Circular std of Lab hue (chroma-weighted; chroma<5 ignored) — palette coherence",
}


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
            SELECT object_number, split
            FROM works
            WHERE split IN ('cohort', 'validation', 'ambiguous')
            ORDER BY object_number
            """
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def to_luminance(rgb: np.ndarray) -> np.ndarray:
    """rgb float [0,1] HxWx3 → grayscale float."""
    w = np.asarray(LUM_WEIGHTS, dtype=np.float64)
    return (rgb * w).sum(axis=2)


def shannon_entropy(counts: np.ndarray) -> float:
    total = counts.sum()
    if total <= 0:
        return float("nan")
    p = counts.astype(np.float64) / total
    p = p[p > 0]
    return float(-(p * np.log2(p)).sum())


def sobel_features(gray: np.ndarray) -> tuple[float, float, float]:
    gx = ndimage.sobel(gray, axis=1, mode="reflect")
    gy = ndimage.sobel(gray, axis=0, mode="reflect")
    mag = np.hypot(gx, gy)
    # Unsigned orientation in [0, pi)
    orient = np.arctan2(gy, gx) % np.pi
    hist, _ = np.histogram(orient, bins=ORIENT_BINS, range=(0.0, np.pi))
    return float(mag.mean()), float(mag.std()), shannon_entropy(hist)


def laplacian_variance(gray: np.ndarray) -> float:
    # 3x3 Laplacian (scipy ndimage.laplace)
    resp = ndimage.laplace(gray, mode="reflect")
    return float(resp.var())


def _uniform_lbp_lookup() -> np.ndarray:
    """Map raw 8-bit LBP → uniform code in {0..P+1}; P+1 = non-uniform."""
    table = np.empty(256, dtype=np.uint8)
    for val in range(256):
        bits = [(val >> b) & 1 for b in range(LBP_P)]
        transitions = sum(bits[b] != bits[(b + 1) % LBP_P] for b in range(LBP_P))
        table[val] = sum(bits) if transitions <= 2 else (LBP_P + 1)
    return table


_UNIFORM_LBP_TABLE = _uniform_lbp_lookup()


def _lbp_uniform_codes(gray_u8: np.ndarray) -> np.ndarray:
    """Uniform LBP, P=8, R=1 on the 8-connected grid (classic discrete)."""
    g = gray_u8
    # Pad so every interior pixel has 8 neighbors; codes on full padded then crop
    p = np.pad(g, 1, mode="reflect")
    center = p[1:-1, 1:-1]
    # Clockwise from right: E, SE, S, SW, W, NW, N, NE
    neighbors = (
        p[1:-1, 2:],
        p[2:, 2:],
        p[2:, 1:-1],
        p[2:, :-2],
        p[1:-1, :-2],
        p[:-2, :-2],
        p[:-2, 1:-1],
        p[:-2, 2:],
    )
    codes = np.zeros(center.shape, dtype=np.uint8)
    for i, nb in enumerate(neighbors):
        codes |= ((nb >= center).astype(np.uint8) << i)
    return _UNIFORM_LBP_TABLE[codes]


def lbp_entropy(gray_u8: np.ndarray) -> float:
    codes = _lbp_uniform_codes(gray_u8)
    # Interior only (border undefined for r=1) — use full with reflect already baked in map_coordinates
    hist = np.bincount(codes.ravel(), minlength=LBP_P + 2)
    return shannon_entropy(hist)


def _quantize_gray(gray_u8: np.ndarray, levels: int) -> np.ndarray:
    # Map 0..255 → 0..levels-1
    q = (gray_u8.astype(np.float64) * (levels / 256.0)).astype(np.int32)
    return np.clip(q, 0, levels - 1)


def glcm_contrast_mean(gray_u8: np.ndarray) -> float:
    q = _quantize_gray(gray_u8, GLCM_LEVELS)
    h, w = q.shape
    contrasts: list[float] = []
    for deg in GLCM_ANGLES_DEG:
        rad = math.radians(deg)
        dy = int(round(GLCM_DISTANCE * math.sin(rad)))
        dx = int(round(GLCM_DISTANCE * math.cos(rad)))
        # Source and destination overlapping region
        if dy >= 0:
            y0_s, y1_s = 0, h - dy
            y0_d, y1_d = dy, h
        else:
            y0_s, y1_s = -dy, h
            y0_d, y1_d = 0, h + dy
        if dx >= 0:
            x0_s, x1_s = 0, w - dx
            x0_d, x1_d = dx, w
        else:
            x0_s, x1_s = -dx, w
            x0_d, x1_d = 0, w + dx
        src = q[y0_s:y1_s, x0_s:x1_s].ravel()
        dst = q[y0_d:y1_d, x0_d:x1_d].ravel()
        if src.size == 0:
            contrasts.append(float("nan"))
            continue
        glcm = np.zeros((GLCM_LEVELS, GLCM_LEVELS), dtype=np.float64)
        np.add.at(glcm, (src, dst), 1)
        # Symmetric
        glcm = glcm + glcm.T
        s = glcm.sum()
        if s <= 0:
            contrasts.append(float("nan"))
            continue
        glcm /= s
        ii, jj = np.indices(glcm.shape)
        contrasts.append(float(((ii - jj) ** 2 * glcm).sum()))
    arr = np.asarray(contrasts, dtype=np.float64)
    if np.any(~np.isfinite(arr)):
        return float("nan")
    return float(arr.mean())


def _srgb_to_linear(u: np.ndarray) -> np.ndarray:
    """u in [0,1] sRGB → linear RGB."""
    return np.where(u <= 0.04045, u / 12.92, ((u + 0.055) / 1.055) ** 2.4)


def rgb_to_lab(rgb01: np.ndarray) -> np.ndarray:
    """HxWx3 sRGB [0,1] → Lab (D65 / CIE)."""
    lin = _srgb_to_linear(rgb01)
    # sRGB D65 matrix
    m = np.array(
        [
            [0.4124564, 0.3575761, 0.1804375],
            [0.2126729, 0.7151522, 0.0721750],
            [0.0193339, 0.1191920, 0.9503041],
        ],
        dtype=np.float64,
    )
    xyz = lin @ m.T
    # D65 white
    white = np.array([0.95047, 1.0, 1.08883], dtype=np.float64)
    t = xyz / white
    delta = 6.0 / 29.0
    def f(c: np.ndarray) -> np.ndarray:
        return np.where(c > delta**3, np.cbrt(c), c / (3 * delta**2) + 4.0 / 29.0)

    fx, fy, fz = f(t[..., 0]), f(t[..., 1]), f(t[..., 2])
    L = 116.0 * fy - 16.0
    a = 500.0 * (fx - fy)
    b = 200.0 * (fy - fz)
    return np.stack([L, a, b], axis=-1)


def palette_features(rgb01: np.ndarray) -> tuple[float, float]:
    lab = rgb_to_lab(rgb01)
    a = lab[..., 1]
    b = lab[..., 2]
    chroma = np.hypot(a, b)
    chroma_mean = float(chroma.mean())

    mask = chroma >= HUE_CHROMA_MIN
    if not np.any(mask):
        return chroma_mean, float("nan")
    # Chroma-weighted circular stats on Lab hue
    w = chroma[mask]
    theta = np.arctan2(b[mask], a[mask])
    c = float((w * np.cos(theta)).sum() / w.sum())
    s = float((w * np.sin(theta)).sum() / w.sum())
    r = math.hypot(c, s)
    # Clamp for numerical stability
    r = min(max(r, 1e-12), 1.0)
    hue_circ_std = math.sqrt(-2.0 * math.log(r))
    return chroma_mean, float(hue_circ_std)


def extract_one(rgb_u8: np.ndarray) -> dict[str, float]:
    if rgb_u8.ndim != 3 or rgb_u8.shape[2] != 3:
        raise ValueError(f"expected HxWx3 RGB, got {rgb_u8.shape}")
    rgb01 = rgb_u8.astype(np.float64) / 255.0
    gray = to_luminance(rgb01)
    gray_u8 = np.clip(np.rint(gray * 255.0), 0, 255).astype(np.uint8)

    g_mean, g_std, g_ent = sobel_features(gray)
    lap_var = laplacian_variance(gray)
    lbp_ent = lbp_entropy(gray_u8)
    glcm_c = glcm_contrast_mean(gray_u8)
    chroma_m, hue_std = palette_features(rgb01)

    return {
        "grad_mag_mean": g_mean,
        "grad_mag_std": g_std,
        "grad_orient_entropy": g_ent,
        "laplacian_var": lap_var,
        "lbp_entropy": lbp_ent,
        "glcm_contrast": glcm_c,
        "lab_chroma_mean": chroma_m,
        "hue_circ_std": hue_std,
    }


def write_dictionary(path: Path) -> None:
    lines = [
        f"# Feature dictionary — `{RECIPE_ID}`",
        "",
        f"**Recipe:** `{RECIPE_ID}` · **Source:** Branch H `{PREPROCESS_RECIPE}/rgb/*.png` only  ",
        f"**Locked:** D29 / O03 · **No** z-scores, fits, or Branch C",
        "",
        "| Column | Meaning |",
        "|---|---|",
        "| `object_number` | Join key (same as SQLite `works`, preprocess caches) |",
    ]
    for col in FEATURE_COLUMNS:
        lines.append(f"| `{col}` | {FEATURE_MEANINGS[col]} |")
    lines.extend(
        [
            "",
            "## Compute defaults (frozen)",
            "",
            f"- Grayscale luminance weights `{LUM_WEIGHTS}`",
            f"- Sobel 3×3; orientation entropy on {ORIENT_BINS} bins over `[0, π)`",
            f"- Laplacian via `scipy.ndimage.laplace`",
            f"- Uniform LBP P={LBP_P}, R={LBP_R}; Shannon entropy of codes",
            f"- GLCM: {GLCM_LEVELS} gray levels, distance={GLCM_DISTANCE}, "
            f"mean contrast over angles {GLCM_ANGLES_DEG}",
            f"- Lab chroma mean; hue circular std with Lab chroma ≥ {HUE_CHROMA_MIN}",
            "- **Note:** `hue_circ_std` uses **Lab** hue (`atan2(b*, a*)`), not HSV — "
            "do not describe it as HSV in Phase 4 write-ups.",
            "",
            "## Geometry (D27)",
            "",
            "Branch H is identity on width=1500 IIIF JPEGs; tall works may have height > 1500. "
            "No resize/crop/pad in this extractor.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract O03 hand-built features (Branch H)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing CSV")
    args = parser.parse_args()

    if CSV_PATH.is_file() and not args.force:
        print(f"Refusing to overwrite {CSV_PATH} (pass --force)", file=sys.stderr)
        return 2

    works = load_scored_works(config.DB_PATH)
    if len(works) != 25:
        print(f"WARNING: expected N=25 scored works, got {len(works)}", file=sys.stderr)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    QC_DIR.mkdir(parents=True, exist_ok=True)

    rows_out: list[dict] = []
    failures: list[dict] = []

    for w in works:
        oid = w["object_number"]
        split = w["split"]
        png = RGB_DIR / f"{oid}.png"
        try:
            if not png.is_file():
                raise FileNotFoundError(f"Branch H PNG missing: {png}")
            with Image.open(png) as im:
                rgb = np.asarray(im.convert("RGB"), dtype=np.uint8)
            feats = extract_one(rgb)
            if not all(math.isfinite(feats[c]) for c in FEATURE_COLUMNS):
                bad = [c for c in FEATURE_COLUMNS if not math.isfinite(feats[c])]
                raise ValueError(f"non-finite features: {bad}")
            row = {"object_number": oid, **feats}
            rows_out.append(row)
            failures.append(
                {
                    "object_number": oid,
                    "split": split,
                    "stage": "extract",
                    "error": "",
                    "ok": "true",
                }
            )
            print(f"OK  {oid}  ({rgb.shape[1]}x{rgb.shape[0]})")
        except Exception as exc:  # noqa: BLE001 — log per-row, fail closed
            failures.append(
                {
                    "object_number": oid,
                    "split": split,
                    "stage": "extract",
                    "error": str(exc),
                    "ok": "false",
                }
            )
            print(f"FAIL {oid}: {exc}", file=sys.stderr)

    # Fail closed: do not write partial matrix as success
    ok_ids = {r["object_number"] for r in rows_out}
    expected = {w["object_number"] for w in works}
    if ok_ids != expected:
        missing = sorted(expected - ok_ids)
        print(f"Incomplete extract; missing {missing}. Writing failures only.", file=sys.stderr)
        with FAILURES_PATH.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f, fieldnames=["object_number", "split", "stage", "error", "ok"]
            )
            writer.writeheader()
            writer.writerows(failures)
        return 1

    fieldnames = ["object_number", *FEATURE_COLUMNS]
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    write_dictionary(DICT_PATH)

    with FAILURES_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["object_number", "split", "stage", "error", "ok"]
        )
        writer.writeheader()
        writer.writerows(failures)

    manifest = {
        "recipe_id": RECIPE_ID,
        "preprocess_recipe": PREPROCESS_RECIPE,
        "source": "branch_h_rgb_png",
        "n_rows": len(rows_out),
        "object_numbers": [r["object_number"] for r in rows_out],
        "feature_columns": list(FEATURE_COLUMNS),
        "splits_included": list(SCORED_SPLITS),
        "csv": str(CSV_PATH.relative_to(config.ROOT)).replace("\\", "/"),
        "dictionary": str(DICT_PATH.relative_to(config.ROOT)).replace("\\", "/"),
        "no_zscore": True,
        "no_branch_c": True,
        "design": "results/phase3_feature_shortlist.md",
        "matrix_contract": "results/phase3_matrix_contract.md",
        "geometry_note": "results/qc_preprocess_v1/geometry_note.md",
        "decision": "D29",
        "created_at": _utc_now(),
        "numpy": np.__version__,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    n_fail = sum(1 for r in failures if r["ok"] != "true")
    print(f"Wrote {CSV_PATH} ({len(rows_out)} rows)")
    print(f"Wrote {DICT_PATH}")
    print(f"Wrote {MANIFEST_PATH}")
    print(f"Wrote {FAILURES_PATH} (failures={n_fail})")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
