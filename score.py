"""
Phase 4 Wave B: decomposable cohort anomaly scores (D30 / scores_v1).

Fit normals on split=cohort only (LOO for cohort self-scores).
Signal A: cosine distance to cohort centroid → z_A.
Signal B: RMS of 8 cohort feature z-scores → z_B.
O02: combined = z_A + z_B.
O04: SK-A-3934 vs cohort p95/median (no AUC; ambiguous excluded).

Usage (from repo root, mamba env CohortScope):
  python score.py
  python score.py --force
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

import config

RECIPE_ID = "scores_v1"
EMBED_RECIPE = "embed_v1"
FEATURES_RECIPE = "features_v1"
SCORED_SPLITS = ("cohort", "validation", "ambiguous", "pupil")  # D32 adds pupil
FEATURE_COLS = (
    "grad_mag_mean",
    "grad_mag_std",
    "grad_orient_entropy",
    "laplacian_var",
    "lbp_entropy",
    "glcm_contrast",
    "lab_chroma_mean",
    "hue_circ_std",
)
EPS = 1e-12
VALIDATION_ID = "SK-A-3934"
AMBIGUOUS_ID = "SK-A-4096"
DRIVER_A = "embed_cosine_to_centroid"

EMBED_MATRIX = config.DATA_DIR / "embeddings" / EMBED_RECIPE / "matrix.pt"
FEATURES_CSV = config.DATA_DIR / "features" / f"{FEATURES_RECIPE}.csv"
SCORES_DIR = config.RESULTS_DIR / "scores"
SCORES_CSV = SCORES_DIR / f"{RECIPE_ID}.csv"
FIT_MANIFEST = SCORES_DIR / "fit_manifest.json"
VALIDATION_REPORT = config.RESULTS_DIR / "validation_report.md"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def repo_rel(path: Path) -> str:
    """Repo-relative POSIX path for manifests / reports."""
    return path.resolve().relative_to(config.ROOT.resolve()).as_posix()


def l2_normalize(x: np.ndarray, axis: int = -1) -> np.ndarray:
    norms = np.linalg.norm(x, axis=axis, keepdims=True)
    norms = np.maximum(norms, EPS)
    return x / norms


def load_embeddings() -> tuple[list[str], np.ndarray]:
    if not EMBED_MATRIX.is_file():
        raise FileNotFoundError(f"missing embeddings: {EMBED_MATRIX}")
    blob = torch.load(EMBED_MATRIX, map_location="cpu", weights_only=True)
    ids = list(blob["object_numbers"])
    x = blob["X"].detach().cpu().numpy().astype(np.float64)
    if x.ndim != 2 or x.shape[1] != 2048:
        raise ValueError(f"expected X [N,2048], got {x.shape}")
    if len(ids) != x.shape[0]:
        raise ValueError("object_numbers length != X rows")
    return ids, x


def load_features() -> dict[str, np.ndarray]:
    if not FEATURES_CSV.is_file():
        raise FileNotFoundError(f"missing features: {FEATURES_CSV}")
    by_id: dict[str, np.ndarray] = {}
    with FEATURES_CSV.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or "object_number" not in reader.fieldnames:
            raise ValueError("features CSV missing object_number")
        missing_cols = [c for c in FEATURE_COLS if c not in reader.fieldnames]
        if missing_cols:
            raise ValueError(f"features CSV missing columns: {missing_cols}")
        for row in reader:
            oid = row["object_number"]
            by_id[oid] = np.array([float(row[c]) for c in FEATURE_COLS], dtype=np.float64)
    return by_id


def load_works_meta() -> dict[str, dict[str, str]]:
    if not config.DB_PATH.is_file():
        raise FileNotFoundError(f"missing DB: {config.DB_PATH}")
    conn = sqlite3.connect(config.DB_PATH)
    try:
        rows = conn.execute(
            "SELECT object_number, split, title FROM works WHERE split IN (?,?,?,?)",
            SCORED_SPLITS,
        ).fetchall()
    finally:
        conn.close()
    meta = {
        oid: {"split": split, "title": title or ""}
        for oid, split, title in rows
    }
    return meta


def align_inputs() -> tuple[list[str], np.ndarray, np.ndarray, dict[str, dict[str, str]]]:
    embed_ids, x = load_embeddings()
    feats = load_features()
    meta = load_works_meta()

    embed_set = set(embed_ids)
    feat_set = set(feats)
    meta_set = set(meta)
    if embed_set != feat_set or embed_set != meta_set:
        raise ValueError(
            "ID mismatch across embeddings / features / DB scored splits: "
            f"embed={len(embed_set)} feat={len(feat_set)} meta={len(meta_set)} "
            f"only_embed={sorted(embed_set - feat_set - meta_set)[:5]} "
            f"only_feat={sorted(feat_set - embed_set)[:5]} "
            f"only_meta={sorted(meta_set - embed_set)[:5]}"
        )
    if len(embed_ids) < 25:
        raise ValueError(f"expected at least the original N=25 scored works, got {len(embed_ids)}")

    # Stable order: sorted object_number
    ids = sorted(embed_ids)
    id_to_row = {oid: i for i, oid in enumerate(embed_ids)}
    x_aligned = np.stack([x[id_to_row[oid]] for oid in ids], axis=0)
    f_aligned = np.stack([feats[oid] for oid in ids], axis=0)

    splits = [meta[oid]["split"] for oid in ids]
    n_cohort = sum(s == "cohort" for s in splits)
    n_val = sum(s == "validation" for s in splits)
    n_amb = sum(s == "ambiguous" for s in splits)
    n_pupil = sum(s == "pupil" for s in splits)
    # D30 splits are frozen; D32 only adds `pupil`, which never enters a fit.
    if (n_cohort, n_val, n_amb) != (23, 1, 1):
        raise ValueError(f"expected split counts 23/1/1, got {n_cohort}/{n_val}/{n_amb}")
    if n_cohort + n_val + n_amb + n_pupil != len(ids):
        raise ValueError("unexpected split value among scored rows")
    if VALIDATION_ID not in meta or meta[VALIDATION_ID]["split"] != "validation":
        raise ValueError(f"{VALIDATION_ID} must be split=validation")
    if AMBIGUOUS_ID not in meta or meta[AMBIGUOUS_ID]["split"] != "ambiguous":
        raise ValueError(f"{AMBIGUOUS_ID} must be split=ambiguous")

    return ids, x_aligned, f_aligned, meta


def mean_std(a: np.ndarray, axis: int = 0) -> tuple[np.ndarray, np.ndarray]:
    mu = a.mean(axis=axis)
    # ddof=1 sample std; for axis=0 over rows
    if a.shape[axis] < 2:
        sigma = np.zeros_like(mu)
    else:
        sigma = a.std(axis=axis, ddof=1)
    return mu, sigma


def cosine_distance_to_centroid(x_hat: np.ndarray, centroid: np.ndarray) -> float:
    mu = centroid.astype(np.float64)
    nrm = np.linalg.norm(mu)
    if nrm < EPS:
        return 0.0
    mu = mu / nrm
    return float(1.0 - np.dot(x_hat, mu))


def compute_d_a(
    ids: list[str],
    x: np.ndarray,
    meta: dict[str, dict[str, str]],
) -> np.ndarray:
    """Cosine distance to cohort centroid; LOO for cohort rows."""
    x_hat = l2_normalize(x, axis=1)
    cohort_idx = [i for i, oid in enumerate(ids) if meta[oid]["split"] == "cohort"]
    if len(cohort_idx) < 2:
        raise ValueError("need >=2 cohort rows for LOO centroid")

    d_a = np.zeros(len(ids), dtype=np.float64)
    full_centroid = x_hat[cohort_idx].mean(axis=0)

    for i, oid in enumerate(ids):
        if meta[oid]["split"] == "cohort":
            others = [j for j in cohort_idx if j != i]
            centroid = x_hat[others].mean(axis=0)
        else:
            centroid = full_centroid
        d_a[i] = cosine_distance_to_centroid(x_hat[i], centroid)
    return d_a


def compute_feature_z_and_d_b(
    ids: list[str],
    f: np.ndarray,
    meta: dict[str, dict[str, str]],
) -> tuple[np.ndarray, np.ndarray]:
    """
    Per-row feature z-matrix [N,8] and d_B RMS.
    Cohort rows: LOO mean/std. Val/ambiguous: full cohort mean/std.
    """
    cohort_idx = [i for i, oid in enumerate(ids) if meta[oid]["split"] == "cohort"]
    n = len(ids)
    z = np.zeros((n, len(FEATURE_COLS)), dtype=np.float64)
    d_b = np.zeros(n, dtype=np.float64)

    full_mu, full_sigma = mean_std(f[cohort_idx], axis=0)

    for i, oid in enumerate(ids):
        if meta[oid]["split"] == "cohort":
            others = [j for j in cohort_idx if j != i]
            mu, sigma = mean_std(f[others], axis=0)
        else:
            mu, sigma = full_mu, full_sigma

        for c in range(len(FEATURE_COLS)):
            if sigma[c] < EPS:
                z[i, c] = 0.0
            else:
                z[i, c] = (f[i, c] - mu[c]) / sigma[c]
        d_b[i] = float(np.sqrt(np.mean(z[i] ** 2)))

    return z, d_b


def z_from_cohort_raw(raw: np.ndarray, cohort_mask: np.ndarray) -> tuple[np.ndarray, float, float]:
    cohort_vals = raw[cohort_mask]
    mu, sigma = mean_std(cohort_vals, axis=0)
    mu_f = float(mu)
    sigma_f = float(sigma)
    if sigma_f < EPS:
        print("WARNING: cohort raw-score std ~ 0; z set to 0", file=sys.stderr)
        return np.zeros_like(raw), mu_f, sigma_f
    return (raw - mu_f) / sigma_f, mu_f, sigma_f


def percentile_linear(values: np.ndarray, q: float) -> float:
    """q in [0,100]; numpy default linear interpolation."""
    return float(np.percentile(values, q))


def o04_outcome(c_val: float, cohort_combined: np.ndarray) -> str:
    p95 = percentile_linear(cohort_combined, 95)
    med = float(np.median(cohort_combined))
    if c_val >= p95:
        return "pass"
    if c_val >= med:
        return "weak"
    return "fail"


def write_fit_manifest(
    *,
    n_cohort: int,
    n_scored: int,
    mu_d_a: float,
    sigma_d_a: float,
    mu_d_b: float,
    sigma_d_b: float,
) -> None:
    SCORES_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "recipe_id": RECIPE_ID,
        "created_at": _utc_now(),
        "n_cohort": n_cohort,
        "n_scored": n_scored,
        "embedding": {
            "source": repo_rel(EMBED_MATRIX),
            "metric": "cosine_distance_to_centroid",
            "loo": True,
            "l2_normalize_vectors": True,
            "l2_normalize_centroid": True,
            "mu_d_A": mu_d_a,
            "sigma_d_A": sigma_d_a,
        },
        "features": {
            "source": repo_rel(FEATURES_CSV),
            "columns": list(FEATURE_COLS),
            "aggregate": "rms_z",
            "loo": True,
            "eps": EPS,
            "mu_d_B": mu_d_b,
            "sigma_d_B": sigma_d_b,
        },
        "o02": "combined = z_A + z_B",
        "o04": {
            "validation_id": VALIDATION_ID,
            "pass": "combined >= cohort p95 of LOO combined",
            "weak": "cohort median <= combined < cohort p95",
            "fail": "combined < cohort median",
            "ambiguous_excluded": True,
            "auc": False,
        },
        "design": "results/phase4_scoring_design.md",
        "decision": "D30",
        "splits_source": repo_rel(config.DB_PATH),
    }
    with FIT_MANIFEST.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")


def write_scores_csv(rows: list[dict]) -> None:
    SCORES_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "object_number",
        "split",
        "title",
        "d_A",
        "z_A",
        "d_B",
        "z_B",
        "combined",
        "rank_combined",
        "dominant_signal",
        "driver_A",
        "driver_B_1",
        "driver_B_2",
    ] + [f"z_{c}" for c in FEATURE_COLS]
    with SCORES_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_validation_report(
    rows_by_id: dict[str, dict],
    cohort_combined: np.ndarray,
    outcome: str,
) -> None:
    n_scored = len(rows_by_id)
    n_pupil = sum(1 for r in rows_by_id.values() if r["split"] == "pupil")
    val = rows_by_id[VALIDATION_ID]
    amb = rows_by_id[AMBIGUOUS_ID]
    med = float(np.median(cohort_combined))
    p90 = percentile_linear(cohort_combined, 90)
    p95 = percentile_linear(cohort_combined, 95)
    p99 = percentile_linear(cohort_combined, 99)
    c_val = float(val["combined"])

    clears = {
        "median": c_val >= med,
        "p90": c_val >= p90,
        "p95": c_val >= p95,
        "p99": c_val >= p99,
    }

    lines = [
        "# Validation report (T043 / scores_v1)",
        "",
        f"**Recipe:** `{RECIPE_ID}` · **Decision:** D30 · **Generated:** `{_utc_now()}`",
        "",
        "## Counts",
        "",
        "| Split | N | Role |",
        "|---|---:|---|",
        "| cohort | 23 | fit normals (LOO self-scores) |",
        "| validation | 1 | O04 / T043 only |",
        "| ambiguous | 1 | exploratory; not counted |",
        f"| pupil | {n_pupil} | D32 surrogate negative class; **not** part of O04 "
        "(see `results/pupil_validation_report.md`) |",
        "",
        "## O04 outcome (SK-A-3934)",
        "",
        f"**Result: `{outcome}`**",
        "",
        "| Quantity | Value |",
        "|---|---|",
        f"| object | `{VALIDATION_ID}` |",
        f"| title | {val['title']} |",
        f"| combined | {c_val:.6f} |",
        f"| z_A | {float(val['z_A']):.6f} |",
        f"| z_B | {float(val['z_B']):.6f} |",
        f"| dominant_signal | {val['dominant_signal']} |",
        f"| driver_A | {val['driver_A']} |",
        f"| driver_B_1 | {val['driver_B_1']} |",
        f"| driver_B_2 | {val['driver_B_2']} |",
        f"| rank_combined (of {n_scored}) | {val['rank_combined']} |",
        f"| cohort median combined | {med:.6f} |",
        f"| cohort p90 | {p90:.6f} |",
        f"| cohort p95 (O04 bar) | {p95:.6f} |",
        f"| cohort p99 | {p99:.6f} |",
        f"| clears median | {clears['median']} |",
        f"| clears p90 | {clears['p90']} |",
        f"| clears p95 | {clears['p95']} |",
        f"| clears p99 | {clears['p99']} |",
        "",
        "### Rule (pre-registered; not retuned)",
        "",
        "- **pass:** `combined` ≥ cohort p95 of LOO `combined`",
        "- **weak:** cohort median ≤ `combined` < p95",
        "- **fail:** `combined` < cohort median",
        "",
        "## Ambiguous (non-counting)",
        "",
        f"| Quantity | `{AMBIGUOUS_ID}` |",
        "|---|---|",
        f"| title | {amb['title']} |",
        f"| combined | {float(amb['combined']):.6f} |",
        f"| z_A | {float(amb['z_A']):.6f} |",
        f"| z_B | {float(amb['z_B']):.6f} |",
        f"| dominant_signal | {amb['dominant_signal']} |",
        f"| driver_A | {amb['driver_A']} |",
        f"| driver_B_1 | {amb['driver_B_1']} |",
        f"| driver_B_2 | {amb['driver_B_2']} |",
        f"| rank_combined (of {n_scored}) | {amb['rank_combined']} |",
        "",
        "Per D21 / O04: ambiguous outcomes do **not** confirm or refute the method.",
        "",
        "## Limits",
        "",
        "Validation N=1: a pass is a single-case tail hit, not a population rate; "
        "fail/weak is inconclusive for “method never works.” IIIF ~1500 px (D12/D27) "
        "is weaker than forensic brushstroke scans. Geometry: Phase 1 uses width=1500, "
        "so tall works may have long edge >1500. No AUC. Rules were not changed after "
        "seeing validation scores.",
        "",
        "## Artifacts",
        "",
        f"- `{repo_rel(SCORES_CSV)}`",
        f"- `{repo_rel(FIT_MANIFEST)}`",
        f"- Design: `results/phase4_scoring_design.md`",
        "",
    ]
    VALIDATION_REPORT.write_text("\n".join(lines), encoding="utf-8")


def run(*, force: bool) -> int:
    if SCORES_CSV.is_file() and not force:
        print(f"Refusing to overwrite {SCORES_CSV}; pass --force", file=sys.stderr)
        return 2

    ids, x, f, meta = align_inputs()
    cohort_mask = np.array([meta[oid]["split"] == "cohort" for oid in ids])

    # --- Fit/score path: compute all scores before reading O04 ---
    d_a = compute_d_a(ids, x, meta)
    z_feat, d_b = compute_feature_z_and_d_b(ids, f, meta)

    z_a, mu_d_a, sigma_d_a = z_from_cohort_raw(d_a, cohort_mask)
    z_b, mu_d_b, sigma_d_b = z_from_cohort_raw(d_b, cohort_mask)
    combined = z_a + z_b

    # Rank among all scored (1 = most anomalous): combined desc, then z_A, then z_B
    order = np.lexsort((-z_b, -z_a, -combined))
    rank = np.empty(len(ids), dtype=np.int32)
    rank[order] = np.arange(1, len(ids) + 1)

    rows: list[dict] = []
    rows_by_id: dict[str, dict] = {}
    for i, oid in enumerate(ids):
        abs_z = np.abs(z_feat[i])
        top = np.argsort(-abs_z)
        driver1 = FEATURE_COLS[int(top[0])]
        driver2 = FEATURE_COLS[int(top[1])]
        dom = "A" if z_a[i] >= z_b[i] else "B"
        row = {
            "object_number": oid,
            "split": meta[oid]["split"],
            "title": meta[oid]["title"],
            "d_A": f"{d_a[i]:.8f}",
            "z_A": f"{z_a[i]:.8f}",
            "d_B": f"{d_b[i]:.8f}",
            "z_B": f"{z_b[i]:.8f}",
            "combined": f"{combined[i]:.8f}",
            "rank_combined": str(int(rank[i])),
            "dominant_signal": dom,
            "driver_A": DRIVER_A,
            "driver_B_1": driver1,
            "driver_B_2": driver2,
        }
        for c_i, c_name in enumerate(FEATURE_COLS):
            row[f"z_{c_name}"] = f"{z_feat[i, c_i]:.8f}"
        rows_by_id[oid] = {
            **row,
            "combined": combined[i],
            "z_A": z_a[i],
            "z_B": z_b[i],
            "rank_combined": int(rank[i]),
        }
        rows.append(row)

    rows.sort(key=lambda r: int(r["rank_combined"]))

    write_fit_manifest(
        n_cohort=int(cohort_mask.sum()),
        n_scored=len(ids),
        mu_d_a=mu_d_a,
        sigma_d_a=sigma_d_a,
        mu_d_b=mu_d_b,
        sigma_d_b=sigma_d_b,
    )
    write_scores_csv(rows)

    # --- T043: evaluate validation only after artifacts are fixed ---
    cohort_combined = combined[cohort_mask]
    c_val = float(combined[ids.index(VALIDATION_ID)])
    outcome = o04_outcome(c_val, cohort_combined)
    write_validation_report(rows_by_id, cohort_combined, outcome)

    print(f"Wrote {SCORES_CSV}")
    print(f"Wrote {FIT_MANIFEST}")
    print(f"Wrote {VALIDATION_REPORT}")
    print(f"O04 outcome (SK-A-3934): {outcome}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Cohortscope Phase 4 scoring (scores_v1)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing scores_v1")
    args = parser.parse_args()
    try:
        return run(force=args.force)
    except Exception as exc:  # noqa: BLE001 — CLI surface
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
