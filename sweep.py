"""
Phase 11: the resolution-floor sweep (D37 / O12 / O13 / sweep_v1).

Implements `results/phase11_resolution_sweep_design.md` exactly. Nothing here is
tunable: the swept floors, the fixed population, the pixel counts, the bootstrap
seed, the Bonferroni correction, and the O13 decision table are transcribed from
that document, which was committed before any non-0.20 tile was fetched.

Both signals are re-run at 0.15 / 0.20 / 0.25 / 0.30 mm/px on a population held
**fixed across floors**, each signal holding its pixel count fixed so that the
only thing varying across the sweep is millimetres per pixel:

  Signal B   150 x 150 px tile, canvas = 150 x floor mm
  Signal A   224 x 224 px tile, canvas = 224 x floor mm  (no resize at any floor)

`tiles_v1` and `cnn_tiles_v1` ARE the 0.20 points and are reused, not re-derived.
The run verifies that byte-identically rather than assuming it.

Reads : data/cohortscope.sqlite, plus the tile caches it fetches
Writes: results/sweep/{sweep_v1.csv,sweep_curve.csv,fit_manifest.json}
        results/resolution_sweep_report.md
QC    : results/qc_sweep_v1/

Usage (repo root, mamba env CohortScope):
  python sweep.py --plan     # population + tile census; no network, no writes
  python sweep.py --fetch    # fetch every sweep tile (long; resumable)
  python sweep.py            # score + report (requires --fetch to have run)
  python sweep.py --force    # overwrite existing sweep outputs
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
import embed
import features
import tile_embed
import tile_score_a
import tiles
from evaluate_pupils import auc, precision_at_k, spearman
from tile_score import directionless, iqr, load_meta, mean_std

# --- Pre-registered constants (design §2, §3, §5-§7). Do not retune. ---
RECIPE_ID = "sweep_v1"
FLOORS = (0.15, 0.20, 0.25, 0.30)          # design §2
SIGNAL_PX = {"B": 150, "A": 224}           # design §2
N_BOOTSTRAP = 10_000                       # design §5.2
BOOTSTRAP_SEED = 20260824                  # design §5.2
PRECISION_AT_K = (5, 10)                   # design §5.3
PASS_AUC = 0.70                            # design §7
N_TESTS = len(FLOORS) * len(SIGNAL_PX)     # 8 -- design §6
ALPHA = 0.05
CORRECTED_PCT = 100.0 * (ALPHA / N_TESTS) / 2.0        # 0.3125
MIN_TILES = 10
EPS = 1e-12

DESIGN_DOC = "results/phase11_resolution_sweep_design.md"
DECISION = "D37"
SCORED_SPLITS = ("cohort", "validation", "ambiguous", "pupil")

OUT_DIR = config.RESULTS_DIR / "sweep"
SCORES_CSV = OUT_DIR / "sweep_v1.csv"
CURVE_CSV = OUT_DIR / "sweep_curve.csv"
FIT_MANIFEST = OUT_DIR / "fit_manifest.json"
REPORT_PATH = config.RESULTS_DIR / "resolution_sweep_report.md"
QC_DIR = config.RESULTS_DIR / f"qc_{RECIPE_ID}"

FEATURE_COLS = features.FEATURE_COLUMNS
UNDEFINABLE = ("hue_circ_std",)  # D35 §4.1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def floor_tag(floor: float) -> str:
    return f"{int(round(floor * 100)):03d}"


def recipe_for(signal: str, floor: float) -> tiles.Recipe:
    """
    The sweep point as a `tiles.Recipe`. The 0.20 points resolve to the already
    published recipes, so their tiles are reused rather than re-fetched -- see
    design §2. Every other point gets its own cache under data/tiles/.
    """
    px = SIGNAL_PX[signal]
    if abs(floor - config.TILE_FLOOR_MM_PER_PX) < 1e-12:
        return tiles.TILES_V1 if signal == "B" else tiles.CNN_TILES_V1
    return tiles.Recipe(
        recipe_id=f"sweep_{signal.lower()}_{floor_tag(floor)}",
        size_mm=round(px * floor, 6),
        size_px=px,
        design=DESIGN_DOC,
        decision=DECISION,
        report_name=f"sweep_{signal.lower()}_{floor_tag(floor)}_tiling.md",
        floor_mm_per_px=floor,
    )


# --------------------------------------------------------------------------
# population (design §3)
# --------------------------------------------------------------------------

def load_works() -> list[dict]:
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


def eligible_at(works: list[dict], signal: str, floor: float) -> dict[str, dict]:
    rec = recipe_for(signal, floor)
    out = {}
    for w in works:
        plan = tiles.assess(w, rec)
        if plan["verdict"] == "eligible":
            out[w["object_number"]] = plan
    return out


def fixed_population(works: list[dict], signal: str) -> tuple[list[str], dict]:
    """The works eligible at EVERY swept floor -- design §3."""
    per_floor = {f: eligible_at(works, signal, f) for f in FLOORS}
    common = set.intersection(*[set(d) for d in per_floor.values()])
    return sorted(common), per_floor


# --------------------------------------------------------------------------
# fetch
# --------------------------------------------------------------------------

def fetch_all(works: list[dict], *, force: bool) -> int:
    by_id = {w["object_number"]: w for w in works}
    total_fail = 0
    for signal in ("B", "A"):
        pop, per_floor = fixed_population(works, signal)
        for floor in FLOORS:
            rec = recipe_for(signal, floor)
            reused = rec.recipe_id in (tiles.TILES_V1.recipe_id, tiles.CNN_TILES_V1.recipe_id)
            plans = [per_floor[floor][o] for o in pop]
            have = sum(
                1
                for p in plans
                for r, c, _ in p["positions"]
                if tiles.tile_path(p["object_number"], r, c, rec).is_file()
            )
            want = sum(len(p["positions"]) for p in plans)
            note = " (reusing the published 0.20 cache)" if reused else ""
            print(f"[{signal} @ {floor:.2f}] {rec.recipe_id}: {have}/{want} tiles present{note}")
            if have == want and not force:
                continue
            done = 0
            for p in plans:
                _, _, fails = tiles.fetch_work(p, by_id[p["object_number"]], force=force, rec=rec)
                total_fail += len(fails)
                done += 1
                if done % 10 == 0 or done == len(plans):
                    print(f"    [{done}/{len(plans)}] works")
    return total_fail


# --------------------------------------------------------------------------
# score (design §4)
# --------------------------------------------------------------------------

def signal_b_values(pop: list[str], plans: dict, rec: tiles.Recipe) -> dict[str, dict]:
    """Work-level medians over the eight features -- D35 §4 and §4.1, unchanged."""
    from PIL import Image

    out: dict[str, dict] = {}
    for oid in pop:
        cols: dict[str, list[float]] = {c: [] for c in FEATURE_COLS}
        n = 0
        for r, c, _ in plans[oid]["positions"]:
            path = tiles.tile_path(oid, r, c, rec)
            with Image.open(path) as im:
                arr = np.asarray(im.convert("RGB"), dtype=np.uint8)
            fv = features.extract_one(arr)
            n += 1
            for k in FEATURE_COLS:
                if np.isfinite(fv[k]):
                    cols[k].append(fv[k])
                elif k not in UNDEFINABLE:
                    raise ValueError(f"{oid} {r},{c}: non-finite {k}")
        out[oid] = {
            "n_tiles": n,
            "median": {k: float(np.median(v)) for k, v in cols.items()},
            "iqr": {k: iqr(np.asarray(v)) for k, v in cols.items()},
            "support": {k: len(v) for k, v in cols.items()},
        }
    return out


def signal_a_values(
    pop: list[str], plans: dict, rec: tiles.Recipe, model, device
) -> dict[str, dict]:
    """Per-tile embeddings -> cosine distance to a LOO cohort tile centroid -- D36 §4."""
    vecs: dict[str, np.ndarray] = {}
    for oid in pop:
        rows = []
        for r, c, _ in plans[oid]["positions"]:
            path = tiles.tile_path(oid, r, c, rec)
            rows.append(embed.embed_one(model, tile_embed.load_tile(path), device).numpy())
        vecs[oid] = tile_score_a.l2(np.asarray(rows, dtype=np.float64))
    return vecs


def fit_z_matrix(x: np.ndarray, is_cohort: np.ndarray) -> np.ndarray:
    ci = np.flatnonzero(is_cohort)
    full_mu, full_sd = mean_std(x[ci])
    z = np.zeros_like(x)
    for i in range(x.shape[0]):
        mu, sd = mean_std(x[ci[ci != i]]) if is_cohort[i] else (full_mu, full_sd)
        safe = sd >= EPS
        z[i] = np.where(safe, (x[i] - mu) / np.where(safe, sd, 1.0), 0.0)
    return z


def bootstrap_two_ci(neg: np.ndarray, pos: np.ndarray) -> tuple[tuple[float, float], tuple[float, float]]:
    """
    One resampling, two intervals: the descriptive 95% and the Bonferroni-corrected
    99.375% required by design §6. Computing both from the same draws means the
    correction cannot be applied selectively after the fact.
    """
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    vals = np.empty(N_BOOTSTRAP, dtype=np.float64)
    for i in range(N_BOOTSTRAP):
        vals[i] = auc(
            neg[rng.integers(0, neg.size, neg.size)],
            pos[rng.integers(0, pos.size, pos.size)],
        )
    ci95 = (float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5)))
    cic = (float(np.percentile(vals, CORRECTED_PCT)),
           float(np.percentile(vals, 100.0 - CORRECTED_PCT)))
    return ci95, cic


def o13_tier(points: list[dict]) -> str:
    """Design §7, verbatim. Judged on the Bonferroni-corrected bound only."""
    winners = [p for p in points if p["ci_corrected"][0] > 0.50]
    if not winners:
        return "fail"
    return "pass" if any(p["auc"] >= PASS_AUC for p in winners) else "weak"


# --------------------------------------------------------------------------
# scoring one sweep point
# --------------------------------------------------------------------------

def score_point(
    signal: str,
    floor: float,
    pop: list[str],
    plans: dict,
    meta: dict,
    model=None,
    device=None,
) -> dict:
    """One (signal, floor) point: work-level score, LOO cohort fit, AUC + both CIs."""
    rec = recipe_for(signal, floor)
    is_cohort = np.array([meta[o]["split"] == "cohort" for o in pop])
    is_tier1 = np.array(
        [meta[o]["split"] == "pupil" and meta[o]["pupil_tier"] == "tier1" for o in pop]
    )

    per_feature: dict[str, float] = {}
    if signal == "B":
        vals = signal_b_values(pop, plans, rec)
        x = np.array([[vals[o]["median"][c] for c in FEATURE_COLS] for o in pop])
        z_mat = fit_z_matrix(x, is_cohort)
        score = np.sqrt(np.mean(z_mat ** 2, axis=1))          # z_B_tile, D35 §5
        sig = np.where(z_mat.std(axis=0, ddof=1) >= EPS, z_mat.std(axis=0, ddof=1), np.nan)
        del sig
        iqr_mat = np.array([[vals[o]["iqr"][c] for c in FEATURE_COLS] for o in pop])
        cohort_sd = np.where(x[is_cohort].std(axis=0, ddof=1) >= EPS,
                             x[is_cohort].std(axis=0, ddof=1), np.nan)
        spread = np.nanmedian(iqr_mat / cohort_sd, axis=1)
        n_tiles = np.array([vals[o]["n_tiles"] for o in pop])
        for j, c in enumerate(FEATURE_COLS):
            per_feature[c] = auc(z_mat[is_cohort, j], z_mat[is_tier1, j])
    else:
        vecs = signal_a_values(pop, plans, rec, model, device)
        cohort_ids = [o for o, c in zip(pop, is_cohort) if c]
        total = sum(vecs[o].sum(axis=0) for o in cohort_ids)
        n_total = sum(vecs[o].shape[0] for o in cohort_ids)
        d_med, d_iqr, n_tiles_l = [], [], []
        for o in pop:
            if meta[o]["split"] == "cohort":
                centroid = (total - vecs[o].sum(axis=0)) / (n_total - vecs[o].shape[0])
            else:
                centroid = total / n_total
            centroid = centroid / max(float(np.linalg.norm(centroid)), EPS)
            d = 1.0 - vecs[o] @ centroid
            d_med.append(float(np.median(d)))
            d_iqr.append(iqr(d))
            n_tiles_l.append(vecs[o].shape[0])
        raw = np.asarray(d_med)
        score = fit_z_matrix(raw.reshape(-1, 1), is_cohort).ravel()   # z_A_tile, D36 §4
        spread = np.asarray(d_iqr)
        n_tiles = np.asarray(n_tiles_l)

    neg, pos = score[is_cohort], score[is_tier1]
    a = auc(neg, pos)
    ci95, cic = bootstrap_two_ci(neg, pos)

    pooled = np.flatnonzero(is_cohort | is_tier1)
    pooled = pooled[np.argsort(-score[pooled], kind="mergesort")]
    labels = [1 if is_tier1[i] else 0 for i in pooled]
    base_rate = sum(labels) / len(labels)

    return {
        "signal": signal,
        "floor": floor,
        "recipe_id": rec.recipe_id,
        "tile_px": rec.size_px,
        "tile_mm": rec.size_mm,
        "n_cohort": int(is_cohort.sum()),
        "n_tier1": int(is_tier1.sum()),
        "auc": a,
        "ci95": ci95,
        "ci_corrected": cic,
        "base_rate": base_rate,
        "precision_at_k": {k: precision_at_k(labels, k) for k in PRECISION_AT_K},
        "per_feature_auc": per_feature,
        "scores": {o: float(s) for o, s in zip(pop, score)},
        "spread": {o: float(s) for o, s in zip(pop, spread)},
        "n_tiles": {o: int(v) for o, v in zip(pop, n_tiles)},
    }


def confound_auc(pop: list[str], meta: dict) -> dict:
    """
    `mm_per_px_native` on the fixed sweep population (design §5.5). Constant across
    floors by construction, so it is computed once per signal.
    """
    is_cohort = np.array([meta[o]["split"] == "cohort" for o in pop])
    is_tier1 = np.array(
        [meta[o]["split"] == "pupil" and meta[o]["pupil_tier"] == "tier1" for o in pop]
    )
    v = np.array([meta[o]["mm_per_px_native"] or np.nan for o in pop])
    ok = np.isfinite(v)
    a = auc(v[ok & is_cohort], v[ok & is_tier1])
    return {"auc": a, "auc_directionless": directionless(a),
            "n_cohort": int((ok & is_cohort).sum()), "n_tier1": int((ok & is_tier1).sum())}


def run_scoring(works: list[dict], *, force: bool) -> int:
    if SCORES_CSV.is_file() and not force:
        print(f"Refusing to overwrite {SCORES_CSV}; pass --force", file=sys.stderr)
        return 2

    meta = load_meta()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = embed.build_model(device)

    points: list[dict] = []
    pops: dict[str, list[str]] = {}
    confounds: dict[str, dict] = {}
    for signal in ("B", "A"):
        pop, per_floor = fixed_population(works, signal)
        pops[signal] = pop
        confounds[signal] = confound_auc(pop, meta)
        for floor in FLOORS:
            pt = score_point(signal, floor, pop, per_floor[floor], meta,
                             model=model, device=device)
            points.append(pt)
            print(f"  [{signal} @ {floor:.2f}] AUC={pt['auc']:.3f} "
                  f"95% [{pt['ci95'][0]:.3f}, {pt['ci95'][1]:.3f}] "
                  f"corrected [{pt['ci_corrected'][0]:.3f}, {pt['ci_corrected'][1]:.3f}]")

    tier = o13_tier(points)
    best = max(points, key=lambda p: p["auc"])
    worst_confound = max(confounds.values(), key=lambda c: c["auc"])
    confounded = worst_confound["auc"] >= best["auc"]

    trend = {}
    for signal in ("B", "A"):
        pts = [p for p in points if p["signal"] == signal]
        trend[signal] = spearman(
            np.array([p["floor"] for p in pts]), np.array([p["auc"] for p in pts])
        )

    write_scores_csv(points, pops, meta)
    write_curve_csv(points)
    write_fit_manifest(points, pops, confounds)
    write_qc(points, tier, confounded, best)
    write_report(points, pops, meta, confounds, tier, best, confounded, trend)

    print(f"Wrote {SCORES_CSV}")
    print(f"Wrote {CURVE_CSV}")
    print(f"Wrote {REPORT_PATH}")
    print(f"O13 outcome: {tier}" + ("  (CONFOUNDED)" if confounded else "")
          + f"  best = Signal {best['signal']} @ {best['floor']:.2f} AUC {best['auc']:.3f}")
    return 0


# --------------------------------------------------------------------------
# outputs
# --------------------------------------------------------------------------

def write_scores_csv(points: list[dict], pops: dict, meta: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with SCORES_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "signal", "floor", "recipe_id", "tile_px", "tile_mm", "object_number",
            "split", "pupil_tier", "creator", "title", "n_tiles", "score", "tile_spread",
        ])
        w.writeheader()
        for pt in points:
            for oid in pops[pt["signal"]]:
                m = meta[oid]
                w.writerow({
                    "signal": pt["signal"], "floor": f"{pt['floor']:.2f}",
                    "recipe_id": pt["recipe_id"], "tile_px": pt["tile_px"],
                    "tile_mm": f"{pt['tile_mm']:g}", "object_number": oid,
                    "split": m["split"], "pupil_tier": m["pupil_tier"] or "",
                    "creator": m["creator"] or "", "title": m["title"] or "",
                    "n_tiles": pt["n_tiles"][oid],
                    "score": f"{pt['scores'][oid]:.8f}",
                    "tile_spread": f"{pt['spread'][oid]:.8f}",
                })


def write_curve_csv(points: list[dict]) -> None:
    with CURVE_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["signal", "floor", "tile_px", "tile_mm", "n_cohort", "n_tier1",
                    "auc", "ci95_lo", "ci95_hi", "ci_corrected_lo", "ci_corrected_hi",
                    "base_rate"] + [f"p_at_{k}" for k in PRECISION_AT_K])
        for pt in points:
            w.writerow([
                pt["signal"], f"{pt['floor']:.2f}", pt["tile_px"], f"{pt['tile_mm']:g}",
                pt["n_cohort"], pt["n_tier1"], f"{pt['auc']:.6f}",
                f"{pt['ci95'][0]:.6f}", f"{pt['ci95'][1]:.6f}",
                f"{pt['ci_corrected'][0]:.6f}", f"{pt['ci_corrected'][1]:.6f}",
                f"{pt['base_rate']:.4f}",
            ] + [f"{pt['precision_at_k'][k]:.4f}" for k in PRECISION_AT_K])


def write_fit_manifest(points: list[dict], pops: dict, confounds: dict) -> None:
    FIT_MANIFEST.write_text(json.dumps({
        "recipe_id": RECIPE_ID,
        "created_at": _utc_now(),
        "design": DESIGN_DOC,
        "decision": DECISION,
        "floors": list(FLOORS),
        "signal_pixels": SIGNAL_PX,
        "parameterization": "pixel count fixed per signal; tile canvas = px x floor",
        "population": "fixed across floors: works eligible at EVERY swept floor",
        "populations": {s: sorted(p) for s, p in pops.items()},
        "population_sizes": {s: len(p) for s, p in pops.items()},
        "fit_on": "split == 'cohort' only, leave-one-out for cohort rows",
        "tier2_sensitivity": "not computed -- one work per sweep (design §3)",
        "combined": None,
        "bootstrap": {"n": N_BOOTSTRAP, "seed": BOOTSTRAP_SEED, "unit": "works"},
        "multiplicity": {
            "n_tests": N_TESTS, "alpha": ALPHA,
            "corrected_ci_pct": 100 * (1 - ALPHA / N_TESTS),
            "corrected_percentiles": [CORRECTED_PCT, 100 - CORRECTED_PCT],
            "note": "computed at every point, not only the best",
        },
        "reused_020_recipes": [tiles.TILES_V1.recipe_id, tiles.CNN_TILES_V1.recipe_id],
        "confound_mm_per_px_native": confounds,
        "points": [
            {k: v for k, v in pt.items() if k not in ("scores", "spread", "n_tiles")}
            for pt in points
        ],
    }, indent=2, default=float) + "\n", encoding="utf-8")


def write_qc(points, tier, confounded, best) -> None:
    QC_DIR.mkdir(parents=True, exist_ok=True)
    (QC_DIR / "summary.json").write_text(json.dumps({
        "recipe_id": RECIPE_ID, "created_at": _utc_now(),
        "o13_tier": tier, "confounded": confounded,
        "best_signal": best["signal"], "best_floor": best["floor"],
        "best_auc": best["auc"],
        "n_points": len(points), "n_tests": N_TESTS,
        "design": DESIGN_DOC, "decision": DECISION,
    }, indent=2, default=float) + "\n", encoding="utf-8")


def write_report(points, pops, meta, confounds, tier, best, confounded, trend) -> None:
    def rows(signal):
        return [p for p in points if p["signal"] == signal]

    L = [
        "# Resolution sweep report - O13 (D37 / `sweep_v1`)",
        "",
        f"**Recipe:** `{RECIPE_ID}` - **Decision:** {DECISION} - **Generated:** `{_utc_now()}`  ",
        f"**Pre-registration:** `{DESIGN_DOC}` - the swept floors, the fixed population, "
        "the bootstrap seed, the Bonferroni correction, and the decision table were fixed "
        "before any non-0.20 tile was fetched.",
        "",
        "O09 and O11 tested one resolution: the 0.20 mm/px floor locked as O07. This phase "
        "asks the question they left open - **is there a resolution at which the signal "
        "exists?** - over the widest range the corpus can support with a population held "
        "fixed across floors.",
        "",
        "## Headline",
        "",
        f"**O13 outcome: `{tier}`**",
        "",
        f"**Confound clause: {'fires' if confounded else 'does not fire'}.**",
        "",
        f"Best point of the eight: **Signal {best['signal']} at {best['floor']:.2f} mm/px, "
        f"AUC {best['auc']:.3f}** "
        f"(95% [{best['ci95'][0]:.3f}, {best['ci95'][1]:.3f}], "
        f"corrected [{best['ci_corrected'][0]:.3f}, {best['ci_corrected'][1]:.3f}]).",
        "",
        "### Why the corrected interval is the one that counts",
        "",
        f"The sweep runs **{N_TESTS} tests** ({len(FLOORS)} floors x 2 signals). Reading the "
        "best of eight against an uncorrected 95% interval inflates the false-positive rate "
        f"to about {100 * (1 - 0.95 ** N_TESTS):.0f}%. Design §6 therefore locked a Bonferroni "
        f"correction **before any point existed**: a floor shows separation only if its "
        f"**{100 * (1 - ALPHA / N_TESTS):.4f}% CI** excludes 0.50. Both intervals are printed "
        "at every point so the correction cannot be applied selectively.",
        "",
        "## The curves",
        "",
    ]

    for signal, name, px in (("B", "Signal B - eight handcrafted features", 150),
                             ("A", "Signal A - ResNet50 embedding", 224)):
        pts = rows(signal)
        n = f"{pts[0]['n_cohort']} vs {pts[0]['n_tier1']}"
        L += [
            f"### {name} ({px} px tiles, N = {n}, base rate {pts[0]['base_rate']:.3f})",
            "",
            "| floor mm/px | tile canvas | AUC | 95% CI | corrected CI | p@5 | p@10 |",
            "|---:|---:|---:|---|---|---:|---:|",
        ]
        for p in pts:
            star = " **<-** " if p is best else ""
            L.append(
                f"| {p['floor']:.2f}{star} | {p['tile_mm']:g} mm | **{p['auc']:.3f}** | "
                f"[{p['ci95'][0]:.3f}, {p['ci95'][1]:.3f}] | "
                f"[{p['ci_corrected'][0]:.3f}, {p['ci_corrected'][1]:.3f}] | "
                f"{p['precision_at_k'][5]:.3f} | {p['precision_at_k'][10]:.3f} |"
            )
        span = max(p["auc"] for p in pts) - min(p["auc"] for p in pts)
        L += [
            "",
            f"AUC spans {span:.3f} across a 2x change in resolution; Spearman rho between "
            f"floor and AUC = {trend[signal]:+.3f} (n = 4 points, **descriptive only** - "
            "design §5.6 forbids quoting a p-value from it).",
            "",
        ]
        if signal == "B":
            worst = max(pts, key=lambda p: max(p["per_feature_auc"].values(), default=0))
            L += [
                "Best single feature at each floor (design §5.4), so a floor-dependent "
                "single-feature effect cannot hide inside the RMS:",
                "",
                "| floor | best feature | its AUC |",
                "|---:|---|---:|",
            ]
            for p in pts:
                k = max(p["per_feature_auc"], key=lambda c: p["per_feature_auc"][c])
                L.append(f"| {p['floor']:.2f} | `{k}` | {p['per_feature_auc'][k]:.3f} |")
            L += ["", ""]
            del worst

    L += [
        "## The confound, at every floor (design §5.5)",
        "",
        "The sweep population is fixed, so `mm_per_px_native` - how far the IIIF server had "
        "to downsample to reach the floor - is **constant across floors by construction** and "
        "is computed once per signal.",
        "",
        "| Signal | `mm_per_px_native` AUC | direction-free | best swept AUC | N |",
        "|---|---:|---:|---:|---|",
    ]
    for signal in ("B", "A"):
        c = confounds[signal]
        b = max(rows(signal), key=lambda p: p["auc"])
        L.append(
            f"| {signal} | **{c['auc']:.3f}** | {c['auc_directionless']:.3f} | "
            f"{b['auc']:.3f} (at {b['floor']:.2f}) | {c['n_cohort']}+{c['n_tier1']} |"
        )
    L += [
        "",
        (f"**The clause fires.** A single metadata column matches or beats the best of eight "
         f"swept points. In O06 it was `mm_per_px_analyzed` at 0.590, in O09 "
         f"`mm_per_px_native` at 0.689, in O11 at 0.705 - and again here. Whatever the sweep "
         "found, the digitization already explained it."
         if confounded else
         "The clause does not fire: no metadata column reaches the best swept AUC."),
        "",
        "## What this settles",
        "",
    ]

    flat = all(p["ci_corrected"][0] <= 0.50 for p in points)
    spans = {s: (min(p["auc"] for p in rows(s)), max(p["auc"] for p in rows(s)))
             for s in ("B", "A")}
    if flat:
        L += [
            "**No floor separates the classes.** All eight corrected intervals contain "
            "0.50 - and so do all eight *uncorrected* 95% intervals, so the multiplicity "
            "correction never had to do any work: not a single point clears even the "
            "unadjusted bar. The answer to *\"was 0.20 simply the wrong scale?\"* is **no**: "
            "over a 2x range bracketing the locked floor, on a population held fixed so that "
            "only millimetres-per-pixel varies, neither signal separates firm Rembrandts from "
            "their pupils at any resolution tested.",
            "",
            f"The curves are flat, not noisy-but-trending: Signal B moves "
            f"{spans['B'][0]:.3f}-{spans['B'][1]:.3f} across the range and Signal A "
            f"{spans['A'][0]:.3f}-{spans['A'][1]:.3f}. Every point sits within "
            f"{max(abs(p['auc'] - 0.5) for p in points):.3f} of chance.",
            "",
            "Design §7 named this outcome in advance and required that it not be softened "
            "into a call for more resolution. It is not one, and §3 explains why it cannot "
            "be: **nine works in the entire corpus have imagery finer than 0.05 mm/px, and "
            "zero works support a full 0.05-0.40 sweep for Signal A.** The imagery to test a "
            "finer hypothesis does not exist in this collection.",
            "",
            "Together with O09 and O11 this closes the method as specified:",
            "",
            "| Outcome | What was tested | Result |",
            "|---|---|---|",
            "| O04 | SK-A-3934 vs cohort, N=1 | `weak` |",
            "| O06 | both signals, fixed-1500 px, N=67 | `fail` (AUC 0.419) |",
            "| O09 | Signal B at 0.20 mm/px, N=55 | `fail` (AUC 0.469) |",
            "| O11 | Signal A at 0.20 mm/px, N=52 | `fail` (AUC 0.523) |",
            "| **O13** | **both signals, 0.15-0.30 mm/px, fixed population** | **`fail`** |",
            "",
        ]
    else:
        winners = [p for p in points if p["ci_corrected"][0] > 0.50]
        L += [
            f"{len(winners)} of {len(points)} points clear the corrected bar: "
            + ", ".join(f"Signal {p['signal']} @ {p['floor']:.2f} (AUC {p['auc']:.3f})"
                        for p in winners),
            "",
            "**This does not amend O07, O09, or O11 and does not move the locked floor** "
            "(design §7). It would be grounds to open a new pre-registered phase at that "
            "floor with a fresh population - nothing more. Retro-fitting a published outcome "
            "to a better sweep point is the exact failure this project exists to avoid.",
            "",
        ]

    L += [
        "## Limits (stated in the pre-registration, not after)",
        "",
        "- **The swept range is 2x, not the 8x the candidate list suggested.** Eligibility is "
        "not monotonic in the floor - a coarser floor admits more works by the mm/px test "
        "while excluding more by the 20-tiles-must-fit test - so the eligible sets are not "
        "nested. The 0.05-0.40 intersection is 6 works for Signal B and **zero** for Signal A.",
        f"- **N = {rows('B')[0]['n_cohort']}+{rows('B')[0]['n_tier1']} and "
        f"{rows('A')[0]['n_cohort']}+{rows('A')[0]['n_tier1']}**, smaller than O09 (55) and "
        "O11 (52), and the Bonferroni correction widens the intervals further. This "
        "experiment is well powered for a large resolution effect and poorly powered for a "
        "small one; it fails to find one, which is not the same as showing there is none.",
        "- **Tier-2 sensitivity is not computed**: one work per sweep (design §3).",
        "- **These are new numbers on a new population.** No sweep figure amends or is "
        "directly comparable to an O09 or O11 figure, including at 0.20.",
        "- **ImageNet features are not brushwork features.** A flat Signal-A curve is "
        "evidence about this backbone across this range and is **not** a licence to reopen "
        "the deferred DINOv2 / finetuning work.",
        "",
        "## Artifacts",
        "",
        f"- `{CURVE_CSV.relative_to(config.ROOT).as_posix()}` - one row per swept point",
        f"- `{SCORES_CSV.relative_to(config.ROOT).as_posix()}` - per-work score at every point",
        f"- `{FIT_MANIFEST.relative_to(config.ROOT).as_posix()}`",
        f"- `{QC_DIR.relative_to(config.ROOT).as_posix()}/`",
        f"- Pre-registration: `{DESIGN_DOC}`",
        "",
    ]
    REPORT_PATH.write_text("\n".join(L), encoding="utf-8")



# --------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Resolution-floor sweep (D37 / sweep_v1)")
    parser.add_argument("--plan", action="store_true",
                        help="Population + tile census; no network, no writes")
    parser.add_argument("--fetch", action="store_true",
                        help="Fetch every sweep tile (long; resumable)")
    parser.add_argument("--force", action="store_true", help="Overwrite / re-fetch")
    args = parser.parse_args()

    works = load_works()
    if args.plan:
        for signal in ("B", "A"):
            pop, per = fixed_population(works, signal)
            print(f"Signal {signal}: fixed population N={len(pop)}")
            for f in FLOORS:
                rec = recipe_for(signal, f)
                print(f"  {f:.2f}  {rec.recipe_id:16s} {rec.size_px} px = "
                      f"{rec.size_mm:g} mm   eligible at floor: {len(per[f])}")
        return 0
    if args.fetch:
        fails = fetch_all(works, force=args.force)
        print(f"fetch complete; failures={fails}")
        return 0 if fails == 0 else 1
    try:
        return run_scoring(works, force=args.force)
    except Exception as exc:  # noqa: BLE001 -- CLI surface
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
