"""
Phase 10 Wave C: work-level Signal A on commensurable pixels (D36 / O11).

Implements `results/phase10_tile_embedding_design.md` §4-§8 exactly. Nothing here
is tunable: the aggregation rule, the fit rule, the bootstrap seed, the k values,
the confound list, and the O11 decision table are transcribed from that document,
which was committed before any 224 px tile was fetched.

There is no `combined` on this recipe (design §4): Signal A and Signal B now live
on different populations (61 vs 64 works) with different tile sizes, so summing
their z-scores would sum measurements of different corpora.

Reads : data/embeddings/tile_embed_v1/matrix.pt, data/embeddings/embed_v1/matrix.pt,
        results/tile_scores/tile_scores_v1.csv, data/cohortscope.sqlite
Writes: results/tile_scores/tile_scores_a_v1.csv
        results/tile_scores/fit_manifest_a.json
        results/tile_embedding_report.md
QC    : results/qc_tile_scores_a_v1/{dropped.csv,summary.json}

O04, O06, and O09 are not recomputed and not amended.

Usage (repo root, mamba env CohortScope):
  python tile_score_a.py
  python tile_score_a.py --force
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from datetime import datetime, timezone

import numpy as np
import torch

import config
import tile_embed
from evaluate_pupils import auc, precision_at_k, spearman
from tile_score import (
    bootstrap_ci,
    bootstrap_delta_ci,
    directionless,
    iqr,
    load_meta,
    mean_std,
)

# --- Pre-registered constants (design §5-§8). Do not retune. ---
RECIPE_ID = "tile_scores_a_v1"
N_BOOTSTRAP = 10_000
BOOTSTRAP_SEED = 20260823           # design §6.2
PRECISION_AT_K = (5, 10, 20)        # design §6.4
PASS_AUC = 0.70                     # design §8, transcribed from O06 / O09
MIN_TILES = 10                      # design §4
EPS = 1e-12

DESIGN_DOC = "results/phase10_tile_embedding_design.md"
DECISION = "D36"

TILE_MATRIX = tile_embed.MATRIX_PATH
FIXED_MATRIX = config.DATA_DIR / "embeddings" / "embed_v1" / "matrix.pt"
SIGNAL_B_CSV = config.RESULTS_DIR / "tile_scores" / "tile_scores_v1.csv"
OUT_DIR = config.RESULTS_DIR / "tile_scores"
SCORES_CSV = OUT_DIR / f"{RECIPE_ID}.csv"
FIT_MANIFEST = OUT_DIR / "fit_manifest_a.json"
REPORT_PATH = config.RESULTS_DIR / "tile_embedding_report.md"
QC_DIR = config.RESULTS_DIR / f"qc_{RECIPE_ID}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def l2(x: np.ndarray) -> np.ndarray:
    return x / np.maximum(np.linalg.norm(x, axis=-1, keepdims=True), EPS)


# --------------------------------------------------------------------------
# load
# --------------------------------------------------------------------------

def load_tile_vectors() -> tuple[list[str], np.ndarray]:
    if not TILE_MATRIX.is_file():
        raise FileNotFoundError(f"missing {TILE_MATRIX}; run `python tile_embed.py`")
    blob = torch.load(TILE_MATRIX, map_location="cpu", weights_only=True)
    if blob.get("recipe_id") != tile_embed.RECIPE_ID:
        raise ValueError(f"unexpected recipe_id {blob.get('recipe_id')!r}")
    return list(blob["object_numbers"]), blob["X"].numpy().astype(np.float64)


def load_fixed_vectors() -> dict[str, np.ndarray]:
    """`embed_v1` work-level vectors, for the paired baseline arm (design §5)."""
    if not FIXED_MATRIX.is_file():
        raise FileNotFoundError(f"missing {FIXED_MATRIX}; run `python embed.py`")
    blob = torch.load(FIXED_MATRIX, map_location="cpu", weights_only=True)
    x = blob["X"].numpy().astype(np.float64)
    return {oid: x[i] for i, oid in enumerate(blob["object_numbers"])}


def load_signal_b() -> dict[str, float]:
    """`z_B_tile` from D35, for the cross-signal independence check (design §6.8)."""
    if not SIGNAL_B_CSV.is_file():
        return {}
    with SIGNAL_B_CSV.open(encoding="utf-8", newline="") as f:
        return {r["object_number"]: float(r["z_B_tile"]) for r in csv.DictReader(f)}


# --------------------------------------------------------------------------
# Signal A on tiles (design §4)
# --------------------------------------------------------------------------

def tile_distances(
    tile_oids: list[str], tv: np.ndarray, ids: list[str], is_cohort: np.ndarray
) -> tuple[dict[str, np.ndarray], dict[str, float]]:
    """
    Per-tile cosine distance to the cohort tile centroid, leave-one-out for cohort
    works: a work's own tiles never enter the centroid it is scored against.

    Also returns the mean-embedding variant (§4): average a work's tile vectors
    first, then take one distance. Reported beside the median rule, never in
    place of it.
    """
    hat = l2(tv)
    by_work: dict[str, list[int]] = {}
    for i, oid in enumerate(tile_oids):
        by_work.setdefault(oid, []).append(i)

    cohort = {oid for oid, c in zip(ids, is_cohort) if c}
    cohort_rows = [i for i, oid in enumerate(tile_oids) if oid in cohort]
    if len(cohort_rows) < 2:
        raise ValueError("need >= 2 cohort tiles for a LOO centroid")
    total = hat[cohort_rows].sum(axis=0)
    n_total = len(cohort_rows)

    per_tile: dict[str, np.ndarray] = {}
    mean_variant: dict[str, float] = {}
    for oid, idx in by_work.items():
        if oid in cohort:
            centroid = (total - hat[idx].sum(axis=0)) / (n_total - len(idx))
        else:
            centroid = total / n_total
        c_hat = centroid / max(float(np.linalg.norm(centroid)), EPS)
        per_tile[oid] = 1.0 - hat[idx] @ c_hat
        mean_vec = l2(hat[idx].mean(axis=0))
        mean_variant[oid] = float(1.0 - mean_vec @ c_hat)
    return per_tile, mean_variant


def fit_z_1d(v: np.ndarray, is_cohort: np.ndarray) -> np.ndarray:
    """Cohort-only normals, LOO for cohort rows (structurally as D30 / D35)."""
    ci = np.flatnonzero(is_cohort)
    if ci.size < 2:
        raise ValueError("need >= 2 cohort rows for a LOO fit")

    def stats(sample: np.ndarray) -> tuple[float, float]:
        mu, sd = mean_std(sample.reshape(-1, 1))
        return float(mu[0]), float(sd[0])

    mu_f, sd_f = stats(v[ci])
    z = np.zeros_like(v)
    for i in range(v.size):
        mu, sd = stats(v[ci[ci != i]]) if is_cohort[i] else (mu_f, sd_f)
        z[i] = 0.0 if sd < EPS else (v[i] - mu) / sd
    return z


def fixed_arm_distance(ids: list[str], fixed: dict[str, np.ndarray], is_cohort: np.ndarray) -> np.ndarray:
    """`embed_v1` cosine-to-centroid re-fit from scratch on these works (design §5)."""
    hat = l2(np.array([fixed[o] for o in ids]))
    ci = np.flatnonzero(is_cohort)
    full = hat[ci].mean(axis=0)
    d = np.zeros(len(ids))
    for i in range(len(ids)):
        c = hat[ci[ci != i]].mean(axis=0) if is_cohort[i] else full
        c = c / max(float(np.linalg.norm(c)), EPS)
        d[i] = 1.0 - float(hat[i] @ c)
    return d


def o11_tier(auc_value: float, ci_low: float) -> str:
    """Design §8, verbatim (thresholds transcribed unchanged from O06 / O09)."""
    if ci_low <= 0.50:
        return "fail"
    if auc_value >= PASS_AUC:
        return "pass"
    return "weak"


# --------------------------------------------------------------------------
# run
# --------------------------------------------------------------------------

def build(force: bool) -> int:
    if SCORES_CSV.is_file() and not force:
        print(f"Refusing to overwrite {SCORES_CSV}; pass --force", file=sys.stderr)
        return 2

    tile_oids, tv = load_tile_vectors()
    meta = load_meta()
    counts: dict[str, int] = {}
    for o in tile_oids:
        counts[o] = counts.get(o, 0) + 1

    dropped = [
        {"object_number": o, "reason": f"only {n} tiles (< {MIN_TILES}, design §4)"}
        for o, n in sorted(counts.items())
        if n < MIN_TILES
    ]
    keep = {o for o, n in counts.items() if n >= MIN_TILES}
    ids = sorted(keep)
    splits = np.array([meta[o]["split"] for o in ids])
    tiers = np.array([meta[o]["pupil_tier"] or "" for o in ids])
    is_cohort = splits == "cohort"
    is_tier1 = (splits == "pupil") & (tiers == "tier1")
    is_tier2 = (splits == "pupil") & (tiers == "tier2")

    mask = [i for i, o in enumerate(tile_oids) if o in keep]
    per_tile, mean_variant = tile_distances(
        [tile_oids[i] for i in mask], tv[mask], ids, is_cohort
    )

    d_a = np.array([float(np.median(per_tile[o])) for o in ids])
    d_iqr = np.array([iqr(per_tile[o]) for o in ids])
    z_a = fit_z_1d(d_a, is_cohort)
    z_a_mean = fit_z_1d(np.array([mean_variant[o] for o in ids]), is_cohort)

    fixed = load_fixed_vectors()
    z_a_fixed = fit_z_1d(fixed_arm_distance(ids, fixed, is_cohort), is_cohort)

    order = np.argsort(-z_a, kind="mergesort")
    rank = np.empty(len(ids), dtype=int)
    rank[order] = np.arange(1, len(ids) + 1)

    z_b = load_signal_b()
    results = evaluate(ids, meta, counts, is_cohort, is_tier1, is_tier2,
                       z_a, z_a_mean, z_a_fixed, d_a, d_iqr, z_b)

    write_scores_csv(ids, meta, counts, d_a, d_iqr, z_a, z_a_mean, z_a_fixed, rank, z_b)
    write_fit_manifest(ids, is_cohort, counts, dropped)
    write_qc(dropped, results, ids)
    write_report(results, dropped)

    print(f"Wrote {SCORES_CSV}")
    print(f"Wrote {FIT_MANIFEST}")
    print(f"Wrote {REPORT_PATH}")
    print(f"Wrote {QC_DIR}")
    print(
        f"O11 outcome: {results['tier']}"
        + (" (CONFOUNDED)" if results["confounded"] else "")
        + f"  AUC={results['auc']:.3f} CI=[{results['ci'][0]:.3f}, {results['ci'][1]:.3f}]"
        f"  dAUC={results['delta_auc']:+.3f}"
    )
    return 0


def evaluate(ids, meta, counts, is_cohort, is_tier1, is_tier2,
             z_a, z_a_mean, z_a_fixed, d_a, d_iqr, z_b) -> dict:
    neg, pos = z_a[is_cohort], z_a[is_tier1]
    a = auc(neg, pos)
    ci = bootstrap_ci(neg, pos, seed=BOOTSTRAP_SEED)
    tier = o11_tier(a, ci[0])

    neg_f, pos_f = z_a_fixed[is_cohort], z_a_fixed[is_tier1]
    a_fixed = auc(neg_f, pos_f)
    delta = a - a_fixed
    delta_ci = bootstrap_delta_ci(neg, pos, neg_f, pos_f, seed=BOOTSTRAP_SEED)

    pooled = np.flatnonzero(is_cohort | is_tier1)
    pooled = pooled[np.argsort(-z_a[pooled], kind="mergesort")]
    labels = [1 if is_tier1[i] else 0 for i in pooled]
    base_rate = sum(labels) / len(labels)
    prec = {k: precision_at_k(labels, k) for k in PRECISION_AT_K}

    by_artist: dict[str, dict] = {}
    for i, oid in enumerate(ids):
        if is_tier1[i]:
            d = by_artist.setdefault(meta[oid]["creator"] or "?", {"z": [], "iqr": []})
            d["z"].append(z_a[i])
            d["iqr"].append(d_iqr[i])

    shared = [i for i, o in enumerate(ids) if o in z_b]
    cross = {
        "n": len(shared),
        "rho": (
            spearman(z_a[shared], np.array([z_b[ids[i]] for i in shared]))
            if len(shared) > 2 else float("nan")
        ),
    }

    confounds = {}
    quantities = {
        "9a mm_per_px_native": [meta[o]["mm_per_px_native"] for o in ids],
        "9b native_px_width": [meta[o]["native_px_width"] for o in ids],
        "9c area_cm2": [meta[o]["area_cm2"] for o in ids],
        "9d tiles_written": [counts[o] for o in ids],
    }
    for name, raw in quantities.items():
        v = np.array([np.nan if x is None else float(x) for x in raw])
        ok = np.isfinite(v)
        n_ok, p_ok = ok & is_cohort, ok & is_tier1
        both = ok & (is_cohort | is_tier1)
        constant = bool(both.sum()) and float(np.ptp(v[both])) == 0.0
        c_auc = (
            float("nan") if constant or not (n_ok.sum() and p_ok.sum())
            else auc(v[n_ok], v[p_ok])
        )
        confounds[name] = {
            "auc": c_auc,
            "auc_directionless": directionless(c_auc),
            "spearman_rho": float("nan") if constant or both.sum() <= 2
                            else spearman(v[both], z_a[both]),
            "constant": constant,
            "n_cohort": int(n_ok.sum()),
            "n_tier1": int(p_ok.sum()),
        }
    breaches = [n for n, d in confounds.items() if np.isfinite(d["auc"]) and d["auc"] >= a]
    breaches_dl = [
        n for n, d in confounds.items()
        if np.isfinite(d["auc_directionless"]) and d["auc_directionless"] >= directionless(a)
    ]

    return {
        "auc": a, "ci": ci, "tier": tier,
        "auc_fixed": a_fixed, "delta_auc": delta, "delta_ci": delta_ci,
        "auc_mean_variant": auc(z_a_mean[is_cohort], z_a_mean[is_tier1]),
        "base_rate": base_rate, "precision_at_k": prec,
        "by_artist": by_artist,
        "tier2": {
            "n": int(is_tier2.sum()),
            "auc": auc(neg, z_a[is_tier2]) if is_tier2.sum() else float("nan"),
        },
        "cross_signal": cross,
        "confounds": confounds, "breaches": breaches,
        "breaches_directionless": breaches_dl, "confounded": bool(breaches),
        "n_cohort": int(is_cohort.sum()), "n_tier1": int(is_tier1.sum()),
        "n_scored": len(ids),
    }


# --------------------------------------------------------------------------
# outputs
# --------------------------------------------------------------------------

def write_scores_csv(ids, meta, counts, d_a, d_iqr, z_a, z_a_mean, z_a_fixed, rank, z_b) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fields = [
        "object_number", "split", "pupil_tier", "creator", "title", "n_tiles",
        "d_A_tile_median", "d_A_tile_iqr", "z_A_tile", "z_A_tile_mean_variant",
        "z_A_fixed_refit", "rank_z_A_tile", "z_B_tile",
    ]
    with SCORES_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for i, oid in enumerate(ids):
            m = meta[oid]
            w.writerow({
                "object_number": oid,
                "split": m["split"],
                "pupil_tier": m["pupil_tier"] or "",
                "creator": m["creator"] or "",
                "title": m["title"] or "",
                "n_tiles": counts[oid],
                "d_A_tile_median": f"{d_a[i]:.8f}",
                "d_A_tile_iqr": f"{d_iqr[i]:.8f}",
                "z_A_tile": f"{z_a[i]:.8f}",
                "z_A_tile_mean_variant": f"{z_a_mean[i]:.8f}",
                "z_A_fixed_refit": f"{z_a_fixed[i]:.8f}",
                "rank_z_A_tile": int(rank[i]),
                "z_B_tile": f"{z_b[oid]:.8f}" if oid in z_b else "",
            })


def write_fit_manifest(ids, is_cohort, counts, dropped) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FIT_MANIFEST.write_text(json.dumps({
        "recipe_id": RECIPE_ID,
        "tile_embed_recipe": tile_embed.RECIPE_ID,
        "created_at": _utc_now(),
        "design": DESIGN_DOC,
        "decision": DECISION,
        "n_scored": len(ids),
        "n_cohort": int(is_cohort.sum()),
        "n_tiles": sum(counts[o] for o in ids),
        "fit_on": "split == 'cohort' only, leave-one-out for cohort rows",
        "centroid": "L2-normalized mean of every cohort tile vector; a work's own "
                    "tiles are excluded from the centroid it is scored against",
        "aggregation": "median over the work's tile cosine distances (design §4)",
        "mean_variant": "reported beside the median rule, never in place of it",
        "min_tiles": MIN_TILES,
        "mm_per_px": config.TILE_FLOOR_MM_PER_PX,
        "tile_size_px": config.CNN_TILE_SIZE_PX,
        "tile_size_mm": config.CNN_TILE_SIZE_MM,
        "resize": None,
        "crop": None,
        "combined": None,
        "signal_b": "not combined -- different population (design §4)",
        "bootstrap": {"n": N_BOOTSTRAP, "seed": BOOTSTRAP_SEED, "unit": "works"},
        "fixed_pixel_arm": {
            "source": FIXED_MATRIX.relative_to(config.ROOT).as_posix(),
            "note": "embed_v1 re-fit from scratch on the same eligible works (design §5)",
        },
        "dropped_works": dropped,
    }, indent=2) + "\n", encoding="utf-8")


def write_qc(dropped, r, ids) -> None:
    QC_DIR.mkdir(parents=True, exist_ok=True)
    with (QC_DIR / "dropped.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["object_number", "reason"])
        w.writeheader()
        w.writerows(dropped)
    (QC_DIR / "summary.json").write_text(json.dumps({
        "recipe_id": RECIPE_ID,
        "created_at": _utc_now(),
        "n_scored": len(ids),
        "n_dropped": len(dropped),
        "o11_tier": r["tier"],
        "confounded": r["confounded"],
        "auc": r["auc"],
        "auc_ci": list(r["ci"]),
        "auc_fixed_refit": r["auc_fixed"],
        "delta_auc": r["delta_auc"],
        "delta_auc_ci": list(r["delta_ci"]),
        "auc_mean_variant": r["auc_mean_variant"],
        "base_rate": r["base_rate"],
        "cross_signal_rho": r["cross_signal"]["rho"],
        "design": DESIGN_DOC,
        "decision": DECISION,
    }, indent=2) + "\n", encoding="utf-8")


def write_report(r, dropped) -> None:
    a, lo, hi = r["auc"], r["ci"][0], r["ci"][1]
    d, dlo, dhi = r["delta_auc"], r["delta_ci"][0], r["delta_ci"][1]
    n = r["n_cohort"] + r["n_tier1"]

    L = [
        "# Tile embedding report — O11 (D36 / `tile_scores_a_v1`)",
        "",
        f"**Recipe:** `{RECIPE_ID}` · **Decision:** {DECISION} · **Generated:** `{_utc_now()}`  ",
        f"**Pre-registration:** `{DESIGN_DOC}` — thresholds, seed, k values, and the "
        "confound list were fixed before any 224 px tile was fetched.",
        "",
        "Signal A only, and for the first time on pixels the CNN can actually resolve "
        "paint in. Each tile is 44.8 mm of canvas served at 224 × 224 px — the "
        "backbone's native input size at the locked 0.20 mm/px floor — so **nothing is "
        "resized, cropped, or interpolated** on the way in. `embed_v1` by contrast fed "
        "the network 0.586–16.058 mm/px after its 256-resize and 224-crop, which is why "
        "`z_A`'s 0.427 in O06 was never a fair test.",
        "",
        "There is no `combined` here (design §4): Signal A and Signal B now live on "
        "different populations, so summing their z-scores would sum different corpora.",
        "",
        "## Headline",
        "",
        f"**O11 outcome: `{r['tier']}`**",
        "",
        f"**Confound clause (§7): {'fires' if r['confounded'] else 'does not fire'}** — see below.",
        "",
        "| Quantity | Value |",
        "|---|---|",
        f"| AUC (`z_A_tile`, cohort vs Tier-1) | **{a:.3f}** |",
        f"| bootstrap 95% CI ({N_BOOTSTRAP:,} resamples, seed {BOOTSTRAP_SEED}) | [{lo:.3f}, {hi:.3f}] |",
        f"| N | {r['n_cohort']} cohort vs {r['n_tier1']} Tier-1 pupils = {n} |",
        "| chance | 0.500 |",
        f"| mean-embedding variant (§4, reported not substituted) | {r['auc_mean_variant']:.3f} |",
        "",
        "### The paired comparison (design §5) — did showing the CNN brushwork help?",
        "",
        f"Both arms are the same backbone, the same layer, the same {n} works, and the "
        "same fit rule. The only difference is what a pixel means.",
        "",
        "| Arm | what the CNN saw | AUC |",
        "|---|---|---|",
        f"| `tile_scores_a_v1` (`z_A_tile`) | 0.20 mm/px, no resize | **{a:.3f}** |",
        f"| `embed_v1` re-fit on the same works | 0.586–16.058 mm/px after resize + crop | {r['auc_fixed']:.3f} |",
        f"| **ΔAUC** | | **{d:+.3f}**, 95% CI [{dlo:+.3f}, {dhi:+.3f}] |",
        "",
        "The re-fitted figure is a **new** number on this population. It does not amend "
        "O06, where `z_A` scored 0.427 on 23 cohort vs 67 pupils.",
        "",
        "## precision@k (design §6.4)",
        "",
        f"Pooled ranking of all {n} works by `z_A_tile` descending. "
        f"**Base rate = {r['base_rate']:.3f}.** Below it means worse than a random shortlist.",
        "",
        "| k | precision@k | vs base rate |",
        "|---:|---:|---|",
    ]
    for k in PRECISION_AT_K:
        p = r["precision_at_k"][k]
        L.append(f"| {k} | {p:.3f} | {p - r['base_rate']:+.3f} |")

    cs = r["cross_signal"]
    L += [
        "",
        "## Cross-signal independence (design §6.8)",
        "",
        f"Spearman ρ between `z_A_tile` and `z_B_tile` over the {cs['n']} works both "
        f"recipes score: **{cs['rho']:+.3f}**. "
        + (
            "Weak rank correlation, so the two signals are close to independent evidence "
            "— which also means neither is rescued by the other."
            if abs(cs["rho"]) < 0.4 else
            "Strong rank correlation: the two signals are **not** independent evidence, "
            "whatever either one scores on its own."
        ),
        "",
        "## Confound checks (design §7)",
        "",
        "Analyzed mm/px is constant at 0.200 by construction. These are the residual "
        "acquisition confounds, named in the pre-registration before being computed. "
        "**9a fired in O09 at AUC 0.689.**",
        "",
        "| # | Quantity | AUC alone | direction-free | Spearman ρ vs `z_A_tile` | N |",
        "|---|---|---:|---:|---:|---|",
    ]
    for name, dd in r["confounds"].items():
        num, _, label = name.partition(" ")
        if dd["constant"]:
            L.append(f"| {num} | `{label}` | *constant* | — | — | {dd['n_cohort']}+{dd['n_tier1']} |")
        else:
            L.append(
                f"| {num} | `{label}` | {dd['auc']:.3f} | {dd['auc_directionless']:.3f} | "
                f"{dd['spearman_rho']:+.3f} | {dd['n_cohort']}+{dd['n_tier1']} |"
            )
    const = [n2.partition(" ")[2] for n2, dd in r["confounds"].items() if dd["constant"]]
    if const:
        L += ["", f"`{'`, `'.join(const)}` is the same value for every work in the "
              "population, so it cannot separate the classes and no AUC or ρ is defined."]

    L += [
        "",
        f"**Fail-closed rule (§7), applied literally:** a quantity whose AUC ≥ {a:.3f} "
        "makes the result *confounded* regardless of tier.",
        "",
        (f"- Breaching quantities: **{', '.join(r['breaches'])}**."
         if r["breaches"] else
         "- No quantity reaches the `z_A_tile` AUC. The result is not confounded by 9a–9d."),
    ]
    if r["breaches_directionless"]:
        L.append(
            "- Reported, not substituted for the literal rule: on the direction-free "
            f"measure `max(AUC, 1−AUC)`, these also match or beat `z_A_tile`: "
            f"**{', '.join(r['breaches_directionless'])}**."
        )
    if r["breaches"]:
        near = [n2 for n2 in r["breaches"] if abs(r["confounds"][n2]["auc"] - 0.50) < 0.05]
        real = [n2 for n2 in r["breaches"] if n2 not in near]
        L += ["", "**How much weight this carries.** The breach list is not uniform:"]
        if near:
            L.append(
                f"- `{'`, `'.join(x.partition(' ')[2] for x in near)}` sits within 0.05 of "
                f"chance and clears a {a:.3f} bar by arithmetic, not by doing real work. "
                "§8 scopes the clause's *effect* to overriding an otherwise-positive tier."
            )
        if real:
            worst = max(real, key=lambda n2: r["confounds"][n2]["auc"])
            cw = r["confounds"][worst]
            L.append(
                f"- `{worst.partition(' ')[2]}` is not near chance: **AUC {cw['auc']:.3f}** "
                f"against the pipeline's {a:.3f}, with Spearman ρ {cw['spearman_rho']:+.3f} "
                "against the score itself. That one is a real confound, and it is the same "
                "column that fired in O09."
            )

    L += [
        "",
        "## Per-artist breakdown (design §6.6)",
        "",
        "| Tier-1 creator | N | median `z_A_tile` | median tile-distance IQR |",
        "|---|---:|---:|---:|",
    ]
    for artist, d2 in sorted(r["by_artist"].items(), key=lambda kv: -float(np.median(kv[1]["z"]))):
        L.append(f"| {artist} | {len(d2['z'])} | {float(np.median(d2['z'])):.3f} | "
                 f"{float(np.median(d2['iqr'])):.4f} |")

    t2 = r["tier2"]
    L += [
        "",
        "## Tier-2 sensitivity (never pooled)",
        "",
        f"Cohort ({r['n_cohort']}) vs the {t2['n']} eligible Tier-2 works: "
        f"**AUC {t2['auc']:.3f}**. Reported with its reduced N per design §6.7.",
        "",
        "## Works dropped from the primary analysis",
        "",
    ]
    if dropped:
        L += ["| object | reason |", "|---|---|"]
        L += [f"| `{x['object_number']}` | {x['reason']} |" for x in dropped]
    else:
        L.append(f"None. Every eligible work retained {MIN_TILES}+ tiles (design §4).")

    L += ["", "### The reading (design §8, stated in advance)", ""]
    if r["tier"] == "fail":
        L += [
            f"**Showing the CNN actual brushwork did not rescue Signal A.** ΔAUC is "
            f"{d:+.3f}, 95% CI [{dlo:+.3f}, {dhi:+.3f}] — an interval that "
            f"{'contains' if dlo <= 0 <= dhi else 'excludes'} zero. The bootstrap CI on "
            f"the primary AUC is [{lo:.3f}, {hi:.3f}], which includes chance.",
            "",
            "`results/resolution_audit.md` showed the ResNet50 had never seen better "
            "than 0.586 mm/px on any work in the corpus — 0 of 108 reached 0.30 — so "
            "`z_A`'s 0.427 in O06 was never a fair test of the embedding. It has now had "
            "one. At 0.20 mm/px, with no resize and no crop, on the backbone's native "
            "input size, it still does not separate firm Rembrandts from their pupils.",
            "",
            "**Both halves of the method have now been tested on commensurable pixels "
            "and both have failed.** O09 returned `fail` for the eight handcrafted "
            f"features at this same scale; O11 returns `{r['tier']}` for the embedding. "
            f"Signal B moved +0.042 and Signal A moved {d:+.3f} — this is the larger of "
            "the two, and it is the one place where normalization visibly did something: "
            f"the fixed-pixel arm was at {r['auc_fixed']:.3f}, clearly *below* chance, and "
            f"commensurable pixels brought it back to {a:.3f}. But a 95% CI of "
            f"[{dlo:+.3f}, {dhi:+.3f}] contains zero, and an arm that lands on chance is "
            "not a method. The scale confound was real, D34 removed it, and what was left "
            "underneath is noise in both signals.",
            "",
            "That is the honest end of this method as specified. It is not a prompt to try "
            "a third variant of it.",
            "",
        ]
    else:
        L += [
            f"AUC {a:.3f}, CI [{lo:.3f}, {hi:.3f}], ΔAUC {d:+.3f} [{dlo:+.3f}, {dhi:+.3f}]. "
            "Read the confound table above before reading this as a method result — "
            "in O09 a metadata column out-scored the entire pipeline.",
            "",
        ]

    L += [
        "## What this does and does not settle",
        "",
        "- **O04 (`weak`), O06 (`fail`), and O09 (`fail`) are unchanged** and not amended. "
        "All four outcomes stand side by side.",
        "- **`scores_v1` remains the published fixed-pixel baseline.**",
        "- **ImageNet features are not brushwork features** (design §9.3). ResNet50 was "
        "trained to name objects. Showing it paint at 0.20 mm/px removes a known defect; "
        "it does not make the representation appropriate. This is evidence about *this* "
        "backbone at *this* scale, and it is **not** a licence to reopen the deferred "
        "DINOv2 / finetuning work.",
        "- **A 44.8 mm tile is outside the training distribution** of a network trained "
        "on whole objects (§9.4).",
        "- **The cohort is 16 and size-biased from both ends** — D34 removed the six "
        "largest works, this recipe additionally removes the smallest.",
        "- **The floor was not swept** (§9.7).",
        "",
        "## Artifacts",
        "",
        f"- `{SCORES_CSV.relative_to(config.ROOT).as_posix()}`",
        f"- `{FIT_MANIFEST.relative_to(config.ROOT).as_posix()}`",
        f"- `{TILE_MATRIX.relative_to(config.ROOT).as_posix()}` — one vector per tile",
        f"- `{QC_DIR.relative_to(config.ROOT).as_posix()}/`",
        f"- Pre-registration: `{DESIGN_DOC}`",
        "",
    ]
    REPORT_PATH.write_text("\n".join(L), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Work-level tile Signal A + O11 (D36)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing outputs")
    args = parser.parse_args()
    try:
        return build(args.force)
    except Exception as exc:  # noqa: BLE001 -- CLI surface
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
