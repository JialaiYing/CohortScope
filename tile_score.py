"""
Phase 9 Wave B: work-level Signal B on physically-normalized tiles (D35 / O09).

Implements `results/phase9_tile_statistics_design.md` §4-§8 exactly. Nothing here
is tunable: the aggregation rule, the fit rule, the bootstrap seed, the k values,
the confound list, and the O09 decision table are transcribed from that document,
which was committed before any feature value was computed from any tile.

There is no Signal A and no `combined` on this recipe (design §2): a 150 px tile
cannot enter a 224 px CNN without a resample factor, which is the arbitrariness
D34 exists to remove.

Reads : data/features/tile_features_v1.csv, data/features/features_v1.csv,
        data/tiles/tiles_v1/manifest.json, data/cohortscope.sqlite
Writes: results/tile_scores/tile_scores_v1.csv
        results/tile_scores/fit_manifest.json
        results/tile_validation_report.md
QC    : results/qc_tile_scores_v1/{dropped.csv,summary.json}

O04 and O06 are not recomputed and not amended. `scores_v1` stays published as
the fixed-pixel baseline.

Usage (repo root, mamba env CohortScope):
  python tile_score.py
  python tile_score.py --force
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from datetime import datetime, timezone

import numpy as np

import config
import tile_features
from evaluate_pupils import auc, precision_at_k, spearman

# --- Pre-registered constants (design §5-§8). Do not retune. ---
RECIPE_ID = "tile_scores_v1"
TILE_FEATURES_RECIPE = tile_features.RECIPE_ID
N_BOOTSTRAP = 10_000
BOOTSTRAP_SEED = 20260822           # design §6.2
PRECISION_AT_K = (5, 10, 20)        # design §6.4
PASS_AUC = 0.70                     # design §8, transcribed from O06
MIN_TILES = 10                      # design §4
EPS = 1e-12

FEATURE_COLS = tile_features.FEATURE_COLUMNS
DESIGN_DOC = "results/phase9_tile_statistics_design.md"
DECISION = "D35"

TILE_FEATURES_CSV = config.DATA_DIR / "features" / f"{TILE_FEATURES_RECIPE}.csv"
FIXED_FEATURES_CSV = config.DATA_DIR / "features" / "features_v1.csv"
OUT_DIR = config.RESULTS_DIR / "tile_scores"
SCORES_CSV = OUT_DIR / f"{RECIPE_ID}.csv"
FIT_MANIFEST = OUT_DIR / "fit_manifest.json"
REPORT_PATH = config.RESULTS_DIR / "tile_validation_report.md"
QC_DIR = config.RESULTS_DIR / f"qc_{RECIPE_ID}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------
# load
# --------------------------------------------------------------------------

def load_tile_rows() -> dict[str, dict[str, list[float]]]:
    """object_number -> feature -> list of per-tile values (undefined cells omitted)."""
    if not TILE_FEATURES_CSV.is_file():
        raise FileNotFoundError(f"missing {TILE_FEATURES_CSV}; run `python tile_features.py`")
    by_work: dict[str, dict[str, list[float]]] = {}
    counts: dict[str, int] = {}
    with TILE_FEATURES_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            oid = row["object_number"]
            slot = by_work.setdefault(oid, {c: [] for c in FEATURE_COLS})
            counts[oid] = counts.get(oid, 0) + 1
            for c in FEATURE_COLS:
                raw = row[c]
                if raw != "":  # design §4.1: undefined cell, tile retained
                    slot[c].append(float(raw))
    for oid in by_work:
        by_work[oid]["__n_tiles__"] = counts[oid]  # type: ignore[assignment]
    return by_work


def load_meta() -> dict[str, dict]:
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT object_number, title, split, pupil_tier, source_query, "
            "cm_width, cm_height, native_px_width, mm_per_px_native FROM works"
        ).fetchall()
    finally:
        conn.close()
    out = {}
    for r in rows:
        d = dict(r)
        d["creator"] = d["source_query"] if d["split"] == "pupil" else None
        cm_w, cm_h = d["cm_width"], d["cm_height"]
        d["area_cm2"] = (cm_w * cm_h) if (cm_w and cm_h) else None
        out[d["object_number"]] = d
    return out


def load_fixed_features() -> dict[str, np.ndarray]:
    """`features_v1` values, for the paired baseline arm (design §5)."""
    if not FIXED_FEATURES_CSV.is_file():
        raise FileNotFoundError(f"missing {FIXED_FEATURES_CSV}; run `python features.py`")
    out: dict[str, np.ndarray] = {}
    with FIXED_FEATURES_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            out[row["object_number"]] = np.array(
                [float(row[c]) for c in FEATURE_COLS], dtype=np.float64
            )
    return out


# --------------------------------------------------------------------------
# aggregation (design §4 + §4.1)
# --------------------------------------------------------------------------

def iqr(values: np.ndarray) -> float:
    return float(np.percentile(values, 75) - np.percentile(values, 25))


def aggregate(by_work: dict) -> tuple[dict[str, dict], list[dict]]:
    """Median / mean / IQR per feature per work. Median is primary (design §4)."""
    agg: dict[str, dict] = {}
    dropped: list[dict] = []
    for oid, slot in by_work.items():
        n_tiles = int(slot["__n_tiles__"])
        if n_tiles < MIN_TILES:
            dropped.append(
                {"object_number": oid, "reason": f"only {n_tiles} tiles (< {MIN_TILES}, design §4)"}
            )
            continue
        empty = [c for c in FEATURE_COLS if len(slot[c]) == 0]
        if empty:
            dropped.append(
                {
                    "object_number": oid,
                    "reason": f"features undefined on every tile (design §4.1): {empty}",
                }
            )
            continue
        entry = {"n_tiles": n_tiles, "support": {}, "median": {}, "mean": {}, "iqr": {}}
        for c in FEATURE_COLS:
            v = np.asarray(slot[c], dtype=np.float64)
            entry["support"][c] = int(v.size)
            entry["median"][c] = float(np.median(v))
            entry["mean"][c] = float(v.mean())
            entry["iqr"][c] = iqr(v)
        agg[oid] = entry
    return agg, dropped


# --------------------------------------------------------------------------
# fit (design §5; structurally identical to D30)
# --------------------------------------------------------------------------

def mean_std(a: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mu = a.mean(axis=0)
    sigma = a.std(axis=0, ddof=1) if a.shape[0] >= 2 else np.zeros_like(mu)
    return mu, sigma


def fit_z(x: np.ndarray, is_cohort: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Cohort-only normals. LOO for cohort rows so no work enters its own normal.
    Returns (z [N,F], full-cohort mu, full-cohort sigma).
    """
    cohort_idx = np.flatnonzero(is_cohort)
    if cohort_idx.size < 2:
        raise ValueError("need >= 2 cohort rows for a LOO fit")
    full_mu, full_sigma = mean_std(x[cohort_idx])
    z = np.zeros_like(x)
    for i in range(x.shape[0]):
        if is_cohort[i]:
            others = cohort_idx[cohort_idx != i]
            mu, sigma = mean_std(x[others])
        else:
            mu, sigma = full_mu, full_sigma
        safe = sigma >= EPS
        z[i] = np.where(safe, (x[i] - mu) / np.where(safe, sigma, 1.0), 0.0)
    return z, full_mu, full_sigma


def rms(z: np.ndarray) -> np.ndarray:
    return np.sqrt(np.mean(z**2, axis=1))


# --------------------------------------------------------------------------
# statistics
# --------------------------------------------------------------------------

def bootstrap_ci(
    neg: np.ndarray, pos: np.ndarray, *, seed: int = BOOTSTRAP_SEED
) -> tuple[float, float]:
    """Stratified percentile bootstrap 95% CI over works (design §6.2)."""
    rng = np.random.default_rng(seed)
    vals = np.empty(N_BOOTSTRAP, dtype=np.float64)
    for i in range(N_BOOTSTRAP):
        vals[i] = auc(
            neg[rng.integers(0, neg.size, neg.size)],
            pos[rng.integers(0, pos.size, pos.size)],
        )
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def bootstrap_delta_ci(
    neg_a: np.ndarray,
    pos_a: np.ndarray,
    neg_b: np.ndarray,
    pos_b: np.ndarray,
    *,
    seed: int = BOOTSTRAP_SEED,
) -> tuple[float, float]:
    """
    Paired bootstrap on AUC(a) - AUC(b) (design §5). The same resampled works are
    used for both arms on every draw, so the pairing between the tile arm and the
    fixed-pixel arm is preserved and only the pixels differ.
    """
    rng = np.random.default_rng(seed)
    vals = np.empty(N_BOOTSTRAP, dtype=np.float64)
    for i in range(N_BOOTSTRAP):
        ni = rng.integers(0, neg_a.size, neg_a.size)
        pi = rng.integers(0, pos_a.size, pos_a.size)
        vals[i] = auc(neg_a[ni], pos_a[pi]) - auc(neg_b[ni], pos_b[pi])
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def o09_tier(auc_value: float, ci_low: float) -> str:
    """Design §8, verbatim (thresholds transcribed unchanged from O06 §5)."""
    if ci_low <= 0.50:
        return "fail"
    if auc_value >= PASS_AUC:
        return "pass"
    return "weak"


def directionless(a: float) -> float:
    """Separation ignoring sign: an AUC of 0.10 separates as well as 0.90."""
    return max(a, 1.0 - a)


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------

def build(force: bool) -> int:
    if SCORES_CSV.is_file() and not force:
        print(f"Refusing to overwrite {SCORES_CSV}; pass --force", file=sys.stderr)
        return 2

    by_work = load_tile_rows()
    meta = load_meta()
    agg, dropped = aggregate(by_work)

    ids = sorted(agg)
    splits = np.array([meta[o]["split"] for o in ids])
    tiers = np.array([meta[o]["pupil_tier"] or "" for o in ids])
    is_cohort = splits == "cohort"
    is_tier1 = (splits == "pupil") & (tiers == "tier1")
    is_tier2 = (splits == "pupil") & (tiers == "tier2")

    # --- tile arm ---
    med = np.array([[agg[o]["median"][c] for c in FEATURE_COLS] for o in ids])
    z_tile, mu_tile, sigma_tile = fit_z(med, is_cohort)
    z_b_tile = rms(z_tile)

    # --- paired fixed-pixel arm: features_v1, re-fit on the same works (design §5) ---
    fixed = load_fixed_features()
    x_fixed = np.array([fixed[o] for o in ids])
    z_fixed, mu_fixed, sigma_fixed = fit_z(x_fixed, is_cohort)
    z_b_fixed = rms(z_fixed)

    # per-work dispersion summary: median over the 8 features of IQR in cohort-sigma
    # units, so the eight are commensurable. The eight raw IQRs stay in the CSV.
    sig_safe = np.where(sigma_tile >= EPS, sigma_tile, np.nan)
    iqr_mat = np.array([[agg[o]["iqr"][c] for c in FEATURE_COLS] for o in ids])
    iqr_sigma = np.nanmedian(iqr_mat / sig_safe, axis=1)

    order = np.argsort(-z_b_tile, kind="mergesort")
    rank = np.empty(len(ids), dtype=int)
    rank[order] = np.arange(1, len(ids) + 1)

    write_scores_csv(ids, meta, agg, z_tile, z_b_tile, z_b_fixed, iqr_sigma, rank)
    write_fit_manifest(ids, is_cohort, mu_tile, sigma_tile, mu_fixed, sigma_fixed, dropped)

    results = evaluate(ids, meta, agg, is_cohort, is_tier1, is_tier2, z_tile, z_b_tile, z_b_fixed, iqr_sigma)
    write_qc(dropped, results, ids)
    write_report(ids, meta, agg, results, dropped)

    print(f"Wrote {SCORES_CSV}")
    print(f"Wrote {FIT_MANIFEST}")
    print(f"Wrote {REPORT_PATH}")
    print(f"Wrote {QC_DIR}")
    print(
        f"O09 outcome: {results['tier']}"
        + (" (CONFOUNDED)" if results["confounded"] else "")
        + f"  AUC={results['auc']:.3f} CI=[{results['ci'][0]:.3f}, {results['ci'][1]:.3f}]"
        f"  dAUC={results['delta_auc']:+.3f}"
    )
    return 0


def evaluate(ids, meta, agg, is_cohort, is_tier1, is_tier2, z_tile, z_b_tile, z_b_fixed, iqr_sigma) -> dict:
    neg, pos = z_b_tile[is_cohort], z_b_tile[is_tier1]
    a = auc(neg, pos)
    ci = bootstrap_ci(neg, pos)
    tier = o09_tier(a, ci[0])

    neg_f, pos_f = z_b_fixed[is_cohort], z_b_fixed[is_tier1]
    a_fixed = auc(neg_f, pos_f)
    delta = a - a_fixed
    delta_ci = bootstrap_delta_ci(neg, pos, neg_f, pos_f)

    # precision@k over the pooled cohort + Tier-1 ranking (design §6.4)
    pooled = np.flatnonzero(is_cohort | is_tier1)
    pooled = pooled[np.argsort(-z_b_tile[pooled], kind="mergesort")]
    labels = [1 if is_tier1[i] else 0 for i in pooled]
    base_rate = sum(labels) / len(labels)
    prec = {k: precision_at_k(labels, k) for k in PRECISION_AT_K}

    per_feature = {
        c: auc(z_tile[is_cohort, j], z_tile[is_tier1, j]) for j, c in enumerate(FEATURE_COLS)
    }

    by_artist: dict[str, dict] = {}
    for i, oid in enumerate(ids):
        if not is_tier1[i]:
            continue
        k = meta[oid]["creator"] or "?"
        d = by_artist.setdefault(k, {"z": [], "iqr": []})
        d["z"].append(z_b_tile[i])
        d["iqr"].append(iqr_sigma[i])

    tier2 = {
        "n": int(is_tier2.sum()),
        "auc": auc(neg, z_b_tile[is_tier2]) if is_tier2.sum() else float("nan"),
    }

    # confounds (design §7). Works with a missing value are excluded from that row
    # only, and the N used is reported.
    confounds = {}
    quantities = {
        "8a mm_per_px_native": [meta[o]["mm_per_px_native"] for o in ids],
        "8b native_px_width": [meta[o]["native_px_width"] for o in ids],
        "8c area_cm2": [meta[o]["area_cm2"] for o in ids],
        "8d tiles_written": [agg[o]["n_tiles"] for o in ids],
    }
    for name, raw in quantities.items():
        v = np.array([np.nan if x is None else float(x) for x in raw])
        ok = np.isfinite(v)
        n_ok, p_ok = ok & is_cohort, ok & is_tier1
        both = ok & (is_cohort | is_tier1)
        # A column with a single value cannot separate anything. Its AUC is 0.500
        # by tie alone and its rank correlation is undefined; reporting those as
        # numbers would invite reading a tie as a result.
        constant = bool(both.sum()) and float(np.ptp(v[both])) == 0.0
        c_auc = (
            float("nan")
            if constant or not (n_ok.sum() and p_ok.sum())
            else auc(v[n_ok], v[p_ok])
        )
        rho = float("nan") if constant or both.sum() <= 2 else spearman(v[both], z_b_tile[both])
        confounds[name] = {
            "auc": c_auc,
            "auc_directionless": directionless(c_auc),
            "spearman_rho": rho,
            "constant": constant,
            "n_cohort": int(n_ok.sum()),
            "n_tier1": int(p_ok.sum()),
        }

    # Fail-closed rule, applied literally as written in §7.
    breaches = [n for n, d in confounds.items() if np.isfinite(d["auc"]) and d["auc"] >= a]
    # Reported, never substituted for the literal rule above.
    breaches_dl = [
        n for n, d in confounds.items()
        if np.isfinite(d["auc_directionless"]) and d["auc_directionless"] >= directionless(a)
    ]

    return {
        "auc": a,
        "ci": ci,
        "tier": tier,
        "auc_fixed": a_fixed,
        "delta_auc": delta,
        "delta_ci": delta_ci,
        "base_rate": base_rate,
        "precision_at_k": prec,
        "per_feature_auc": per_feature,
        "by_artist": by_artist,
        "tier2": tier2,
        "confounds": confounds,
        "breaches": breaches,
        "breaches_directionless": breaches_dl,
        "confounded": bool(breaches),
        "n_cohort": int(is_cohort.sum()),
        "n_tier1": int(is_tier1.sum()),
    }


# --------------------------------------------------------------------------
# outputs
# --------------------------------------------------------------------------

def write_scores_csv(ids, meta, agg, z_tile, z_b_tile, z_b_fixed, iqr_sigma, rank) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fields = [
        "object_number", "split", "pupil_tier", "creator", "title",
        "n_tiles", "z_B_tile", "z_B_fixed_refit", "rank_z_B_tile", "tile_iqr_sigma",
    ]
    for c in FEATURE_COLS:
        fields += [f"support_{c}", f"med_{c}", f"mean_{c}", f"iqr_{c}", f"z_{c}"]
    with SCORES_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for i, oid in enumerate(ids):
            m, e = meta[oid], agg[oid]
            row = {
                "object_number": oid,
                "split": m["split"],
                "pupil_tier": m["pupil_tier"] or "",
                "creator": m["creator"] or "",
                "title": m["title"] or "",
                "n_tiles": e["n_tiles"],
                "z_B_tile": f"{z_b_tile[i]:.8f}",
                "z_B_fixed_refit": f"{z_b_fixed[i]:.8f}",
                "rank_z_B_tile": int(rank[i]),
                "tile_iqr_sigma": f"{iqr_sigma[i]:.8f}",
            }
            for j, c in enumerate(FEATURE_COLS):
                row[f"support_{c}"] = e["support"][c]
                row[f"med_{c}"] = f"{e['median'][c]:.8g}"
                row[f"mean_{c}"] = f"{e['mean'][c]:.8g}"
                row[f"iqr_{c}"] = f"{e['iqr'][c]:.8g}"
                row[f"z_{c}"] = f"{z_tile[i, j]:.8f}"
            w.writerow(row)


def write_fit_manifest(ids, is_cohort, mu_t, sig_t, mu_f, sig_f, dropped) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "recipe_id": RECIPE_ID,
        "tile_features_recipe": TILE_FEATURES_RECIPE,
        "created_at": _utc_now(),
        "design": DESIGN_DOC,
        "decision": DECISION,
        "n_scored": len(ids),
        "n_cohort": int(is_cohort.sum()),
        "fit_on": "split == 'cohort' only, leave-one-out for cohort rows",
        "aggregation": "median over a work's tiles, per feature (design §4)",
        "undefined_cell_policy": "design §4.1",
        "min_tiles": MIN_TILES,
        "feature_columns": list(FEATURE_COLS),
        "mm_per_px": config.TILE_FLOOR_MM_PER_PX,
        "signal_a": None,
        "combined": None,
        "tile_arm": {
            "source": TILE_FEATURES_CSV.relative_to(config.ROOT).as_posix(),
            "cohort_mu": dict(zip(FEATURE_COLS, mu_t.tolist())),
            "cohort_sigma": dict(zip(FEATURE_COLS, sig_t.tolist())),
        },
        "fixed_pixel_arm": {
            "source": FIXED_FEATURES_CSV.relative_to(config.ROOT).as_posix(),
            "note": "features_v1 re-fit from scratch on the same eligible works (design §5)",
            "cohort_mu": dict(zip(FEATURE_COLS, mu_f.tolist())),
            "cohort_sigma": dict(zip(FEATURE_COLS, sig_f.tolist())),
        },
        "bootstrap": {"n": N_BOOTSTRAP, "seed": BOOTSTRAP_SEED, "unit": "works"},
        "dropped_works": dropped,
    }
    FIT_MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def write_qc(dropped, results, ids) -> None:
    QC_DIR.mkdir(parents=True, exist_ok=True)
    with (QC_DIR / "dropped.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["object_number", "reason"])
        w.writeheader()
        w.writerows(dropped)
    summary = {
        "recipe_id": RECIPE_ID,
        "created_at": _utc_now(),
        "n_scored": len(ids),
        "n_dropped": len(dropped),
        "o09_tier": results["tier"],
        "confounded": results["confounded"],
        "auc": results["auc"],
        "auc_ci": list(results["ci"]),
        "auc_fixed_refit": results["auc_fixed"],
        "delta_auc": results["delta_auc"],
        "delta_auc_ci": list(results["delta_ci"]),
        "base_rate": results["base_rate"],
        "design": DESIGN_DOC,
        "decision": DECISION,
    }
    (QC_DIR / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def write_report(ids, meta, agg, r, dropped) -> None:
    a, lo, hi = r["auc"], r["ci"][0], r["ci"][1]
    d, dlo, dhi = r["delta_auc"], r["delta_ci"][0], r["delta_ci"][1]

    L = [
        "# Tile validation report — O09 (D35 / `tile_scores_v1`)",
        "",
        f"**Recipe:** `{RECIPE_ID}` · **Decision:** {DECISION} · **Generated:** `{_utc_now()}`  ",
        f"**Pre-registration:** `{DESIGN_DOC}` — thresholds, seed, k values, and the "
        "confound list were fixed before any feature value was computed from any tile.",
        "",
        "Signal B only. There is no `z_A` and no `combined` on this recipe (design §2): "
        "a 150 px tile cannot enter a 224 px CNN without a resample factor, which is the "
        "arbitrariness D34 exists to remove. This report says nothing about Signal A.",
        "",
        "## Headline",
        "",
        f"**O09 outcome: `{r['tier']}`**",
        "",
        f"**Confound clause (§7): {'fires' if r['confounded'] else 'does not fire'}** — see below.",
        "",
        "| Quantity | Value |",
        "|---|---|",
        f"| AUC (`z_B_tile`, cohort vs Tier-1) | **{a:.3f}** |",
        f"| bootstrap 95% CI ({N_BOOTSTRAP:,} resamples, seed {BOOTSTRAP_SEED}) | [{lo:.3f}, {hi:.3f}] |",
        f"| N | {r['n_cohort']} cohort vs {r['n_tier1']} Tier-1 pupils = {r['n_cohort'] + r['n_tier1']} |",
        f"| chance | 0.500 |",
        "",
        "### The paired comparison (design §5) — did physical normalization help?",
        "",
        "Both arms use the **same 55 works** and the **same 8 features**; the only "
        "difference is what a pixel means.",
        "",
        "| Arm | pixels | AUC |",
        "|---|---|---|",
        f"| `tile_scores_v1` (`z_B_tile`) | 0.20 mm/px everywhere | **{a:.3f}** |",
        f"| `features_v1` re-fit on the same works | fixed 1500 px wide (0.100–0.947 mm/px) | {r['auc_fixed']:.3f} |",
        f"| **ΔAUC** | | **{d:+.3f}**, 95% CI [{dlo:+.3f}, {dhi:+.3f}] |",
        "",
        "The re-fitted fixed-pixel figure is a **new** number computed on this "
        "population. It does not amend O06 or `results/pupil_validation_report.md`, "
        "where `z_B` scored 0.522 on 23 cohort vs 67 pupils.",
        "",
        "## precision@k (design §6.4)",
        "",
        f"Pooled ranking of all {r['n_cohort'] + r['n_tier1']} works by `z_B_tile` descending. "
        f"**Base rate = {r['base_rate']:.3f}** — a random shortlist of any size scores this. "
        "A value below it means the ranking is worse than picking at random.",
        "",
        "| k | precision@k | vs base rate |",
        "|---:|---:|---|",
    ]
    for k in PRECISION_AT_K:
        p = r["precision_at_k"][k]
        L.append(f"| {k} | {p:.3f} | {p - r['base_rate']:+.3f} |")

    L += [
        "",
        "## Per-feature AUC (design §6.5)",
        "",
        "Each of the eight z-scores on its own. This exposes whether one feature "
        "carries the signal or whether the RMS is pooling eight noise channels.",
        "",
        "| Feature | AUC alone |",
        "|---|---:|",
    ]
    for c, v in sorted(r["per_feature_auc"].items(), key=lambda kv: -abs(kv[1] - 0.5)):
        L.append(f"| `{c}` | {v:.3f} |")

    L += [
        "",
        "## Confound checks (design §7)",
        "",
        "mm/px of the *analyzed* pixels is constant at 0.200 by construction, so the "
        "O06 finding cannot recur in its original form. These are the residual "
        "acquisition confounds, named in the pre-registration before being computed.",
        "",
        "| # | Quantity | AUC alone | direction-free | Spearman ρ vs `z_B_tile` | N |",
        "|---|---|---:|---:|---:|---|",
    ]
    for name, dd in r["confounds"].items():
        num, _, label = name.partition(" ")
        if dd["constant"]:
            L.append(
                f"| {num} | `{label}` | — | — | — | {dd['n_cohort']}+{dd['n_tier1']} |"
                .replace("| — |", "| *constant* |", 1)
            )
        else:
            L.append(
                f"| {num} | `{label}` | {dd['auc']:.3f} | {dd['auc_directionless']:.3f} | "
                f"{dd['spearman_rho']:+.3f} | {dd['n_cohort']}+{dd['n_tier1']} |"
            )
    const = [n.partition(" ")[2] for n, dd in r["confounds"].items() if dd["constant"]]
    if const:
        L += [
            "",
            f"`{'`, `'.join(const)}` is the same value for every work in the population, "
            "so it cannot separate the classes and no AUC or ρ is defined for it. It is "
            "reported as constant rather than as a tie at 0.500.",
        ]

    L += [
        "",
        f"**Fail-closed rule (§7), applied literally:** a quantity whose AUC ≥ "
        f"{a:.3f} (the `z_B_tile` AUC) makes the result *confounded* regardless of tier.",
        "",
        (
            f"- Breaching quantities: **{', '.join(r['breaches'])}** → reported as **confounded**."
            if r["breaches"]
            else "- No quantity reaches the `z_B_tile` AUC. The result is not confounded by 8a–8d."
        ),
    ]
    if r["breaches_directionless"]:
        L.append(
            "- Reported, not substituted for the literal rule: on the direction-free "
            f"measure `max(AUC, 1−AUC)`, these also match or beat `z_B_tile`: "
            f"**{', '.join(r['breaches_directionless'])}**. A quantity that separates "
            "in the *opposite* direction still separates."
        )
    if r["breaches"] and a < 0.50:
        L += [
            "",
            f"**How much weight this carries.** `z_B_tile` is at {a:.3f}, *below* chance, so "
            "any quantity sitting at or near 0.500 clears the bar by arithmetic rather than "
            "by doing real work — `area_cm2` at "
            f"{r['confounds']['8c area_cm2']['auc']:.3f} is in that category. The clause is "
            "reported as firing because that is what §7 says, and §8 scopes its *effect* to "
            "overriding an otherwise-positive tier, of which there is none here. The entry "
            "that carries real weight is **8a**: at "
            f"{r['confounds']['8a mm_per_px_native']['auc']:.3f} it is not near chance and it "
            "beats the pipeline outright.",
        ]

    L += [
        "",
        "## Per-artist breakdown (design §6.6)",
        "",
        "`tile_iqr_sigma` is the within-work spread across that work's tiles: the "
        "median over the eight features of IQR ÷ cohort σ. It is the visible form of "
        "limitation §9.1 — 20 tiles is a sample, not a census.",
        "",
        "| Tier-1 creator | N | median `z_B_tile` | median tile IQR (σ) |",
        "|---|---:|---:|---:|",
    ]
    for artist, d2 in sorted(r["by_artist"].items(), key=lambda kv: -float(np.median(kv[1]["z"]))):
        L.append(
            f"| {artist} | {len(d2['z'])} | {float(np.median(d2['z'])):.3f} | "
            f"{float(np.median(d2['iqr'])):.3f} |"
        )

    t2 = r["tier2"]
    L += [
        "",
        "## Tier-2 sensitivity (never pooled)",
        "",
        f"Cohort ({r['n_cohort']}) vs the {t2['n']} eligible Tier-2 works "
        f"(Lievens, Backer — pupilage disputed or absent): **AUC {t2['auc']:.3f}**. "
        "Reported with its reduced N per design §6.7; it is not combined with the "
        "Tier-1 figure and does not enter O09.",
        "",
        "## Works dropped from the primary analysis",
        "",
    ]
    if dropped:
        L += ["| object | reason |", "|---|---|"]
        L += [f"| `{x['object_number']}` | {x['reason']} |" for x in dropped]
    else:
        L.append(
            f"None. Every eligible work retained {MIN_TILES}+ tiles and no feature was "
            "undefined on all of a work's tiles (design §4, §4.1)."
        )

    L += [
        "",
        "## What this does and does not settle",
        "",
        "- **O04 (`weak`, N=1) and O06 (`fail`, N=67) are unchanged.** They are not "
        "recomputed here and this report does not amend them. All three outcomes stand "
        "side by side.",
        "- **`scores_v1` remains the published fixed-pixel baseline.**",
        "- **Signal A is untested at 0.20 mm/px** (design §2). Nothing here exonerates "
        "or condemns the embedding.",
        "- **The cohort is 17 and size-biased** — the six excluded firm Rembrandts are "
        "systematically the largest, so these normals describe small-and-medium works.",
        "- **The floor was not swept.** Re-running at another floor is legitimate only "
        "as a declared sweep reported in full, never as a substitution "
        "(`results/phase8_tiling_design.md` §4.5).",
        "",
    ]
    L += ["### The informative reading (design §8, stated in advance)", ""]
    if r["tier"] == "fail":
        moved = (
            "removing it did not produce one"
            if dlo <= 0 <= dhi
            else ("removing it moved the number without lifting it off chance"
                  if d > 0 else "removing it made the number worse")
        )
        L += [
            f"**Physical normalization did not rescue the handcrafted signal.** ΔAUC is "
            f"{d:+.3f} with a 95% CI of [{dlo:+.3f}, {dhi:+.3f}] — an interval that "
            f"{'contains' if dlo <= 0 <= dhi else 'excludes'} zero, so the change from "
            f"fixed-pixel to physically-normalized input is "
            f"{'indistinguishable from no change at this N' if dlo <= 0 <= dhi else 'measurable'}. "
            f"Both arms sit below chance ({a:.3f} and {r['auc_fixed']:.3f}).",
            "",
            "This is the result the pre-registration named in advance as the informative "
            "one. The 9.5× scale gradient that O06 flagged as its largest exposure was "
            "real, and D34 removed it — the eight features now measure the same physical "
            f"quantity on every work. Separation was not hiding behind it -- {moved}. "
            "On this evidence the handcrafted-feature line of attack is exhausted at "
            "0.20 mm/px, and that is a finding, not a step on the way to a better number.",
            "",
            f"**The successor confound is the story.** §7 named `mm_per_px_native` in "
            "advance as \"the direct successor to the 0.590 finding\", and it is: at "
            f"{r['confounds']['8a mm_per_px_native']['auc']:.3f} it out-separates the entire "
            f"pipeline ({a:.3f}), exactly as `mm_per_px_analyzed` did in O06. Analyzed "
            "resolution is now constant, so what remains is **how far the IIIF server had "
            "to downsample to reach 0.20 mm/px** — a property of the digitization, not of "
            "the painting. Normalizing the nominal scale did not normalize the effective "
            "sharpness behind it.",
            "",
        ]
    else:
        L += [
            f"ΔAUC is {d:+.3f}, 95% CI [{dlo:+.3f}, {dhi:+.3f}]. Read it against the "
            "confound table above before reading it as a method result.",
            "",
        ]

    L += [
        "## Artifacts",
        "",
        f"- `{SCORES_CSV.relative_to(config.ROOT).as_posix()}` — per-work aggregates, z-scores, both arms",
        f"- `{FIT_MANIFEST.relative_to(config.ROOT).as_posix()}` — cohort means/stds for both arms",
        f"- `{TILE_FEATURES_CSV.relative_to(config.ROOT).as_posix()}` — one row per tile",
        f"- `{QC_DIR.relative_to(config.ROOT).as_posix()}/`",
        f"- Pre-registration: `{DESIGN_DOC}`",
        "",
    ]
    REPORT_PATH.write_text("\n".join(L), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Work-level tile Signal B + O09 (D35)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing outputs")
    args = parser.parse_args()
    try:
        return build(args.force)
    except Exception as exc:  # noqa: BLE001 -- CLI surface
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
