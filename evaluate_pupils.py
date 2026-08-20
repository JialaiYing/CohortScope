"""
O06 evaluation: does the cohort separate from documented Rembrandt pupils?

Implements exactly the metrics and decision rule pre-registered in
`results/phase7_pupil_validation_design.md` (D32 / O06), which was committed
before any pupil work was acquired or scored. Nothing here is tunable: the AUC
thresholds, bootstrap count, seed, and k values are transcribed from that
document and must not be edited to change an outcome.

Reads : results/scores/scores_v1.csv, data/cohortscope.sqlite
Writes: results/pupil_validation_report.md

This module does not fit anything and does not touch O04.

Usage (repo root, mamba env CohortScope):
  python evaluate_pupils.py
  python evaluate_pupils.py --force
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from datetime import datetime, timezone

import numpy as np
from scipy.stats import spearmanr

import config

# --- Pre-registered constants (design §4, §5). Do not retune. ---
N_BOOTSTRAP = 10_000
BOOTSTRAP_SEED = 20260819
PRECISION_AT_K = (5, 10, 20)
PASS_AUC = 0.70

SCORES_CSV = config.RESULTS_DIR / "scores" / "scores_v1.csv"
REPORT_PATH = config.RESULTS_DIR / "pupil_validation_report.md"
DESIGN_DOC = "results/phase7_pupil_validation_design.md"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------
# statistics
# --------------------------------------------------------------------------

def auc(neg: np.ndarray, pos: np.ndarray) -> float:
    """Mann-Whitney U / ROC area with ties at 0.5. P(pos score > neg score)."""
    if neg.size == 0 or pos.size == 0:
        return float("nan")
    allv = np.concatenate([neg, pos])
    order = allv.argsort(kind="mergesort")
    ranks = np.empty(allv.size, dtype=np.float64)
    ranks[order] = np.arange(1, allv.size + 1, dtype=np.float64)
    # average ranks within tie groups
    sorted_v = allv[order]
    i = 0
    while i < sorted_v.size:
        j = i
        while j + 1 < sorted_v.size and sorted_v[j + 1] == sorted_v[i]:
            j += 1
        if j > i:
            ranks[order[i : j + 1]] = (i + 1 + j + 1) / 2.0
        i = j + 1
    r_pos = ranks[neg.size :].sum()
    n_pos, n_neg = float(pos.size), float(neg.size)
    return float((r_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def bootstrap_auc_ci(
    neg: np.ndarray, pos: np.ndarray, *, n: int = N_BOOTSTRAP, seed: int = BOOTSTRAP_SEED
) -> tuple[float, float]:
    """Stratified percentile bootstrap 95% CI (design §4.2)."""
    rng = np.random.default_rng(seed)
    vals = np.empty(n, dtype=np.float64)
    for i in range(n):
        b_neg = neg[rng.integers(0, neg.size, neg.size)]
        b_pos = pos[rng.integers(0, pos.size, pos.size)]
        vals[i] = auc(b_neg, b_pos)
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def precision_at_k(labels_by_rank: list[int], k: int) -> float:
    """labels_by_rank: 1 = positive (pupil), 0 = negative, ordered most-anomalous first."""
    if k > len(labels_by_rank):
        return float("nan")
    return sum(labels_by_rank[:k]) / float(k)


def spearman(a: np.ndarray, b: np.ndarray) -> float:
    """Rank correlation with tied ranks averaged (scipy handles the tie case)."""
    return float(spearmanr(a, b).statistic)


def o06_tier(auc_value: float, ci_low: float) -> str:
    """Design §5, verbatim."""
    if ci_low <= 0.50:
        return "fail"
    if auc_value >= PASS_AUC:
        return "pass"
    return "weak"


# --------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------

def load_rows() -> list[dict]:
    if not SCORES_CSV.is_file():
        raise FileNotFoundError(f"missing {SCORES_CSV}; run score.py first")
    with SCORES_CSV.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    # Geometry lives on `works` (Fix 1); there is no side-cache to fall out of sync.
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        meta = {
            r["object_number"]: dict(r)
            for r in conn.execute(
                "SELECT object_number, pupil_tier, source_query, "
                "mm_per_px_analyzed, native_px_width FROM works"
            )
        }
    finally:
        conn.close()

    out = []
    for r in rows:
        oid = r["object_number"]
        d = meta.get(oid, {})
        out.append(
            {
                "object_number": oid,
                "split": r["split"],
                "title": r["title"],
                "tier": d.get("pupil_tier"),
                "creator": d.get("source_query") if r["split"] == "pupil" else None,
                "combined": float(r["combined"]),
                "z_A": float(r["z_A"]),
                "z_B": float(r["z_B"]),
                "mm_per_px": d.get("mm_per_px_analyzed"),
                "native_px_width": d.get("native_px_width"),
            }
        )
    return out


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

def fmt(x: float, nd: int = 4) -> str:
    return "n/a" if x != x else f"{x:.{nd}f}"


def build_report(rows: list[dict]) -> tuple[str, dict]:
    cohort = [r for r in rows if r["split"] == "cohort"]
    tier1 = [r for r in rows if r["split"] == "pupil" and r["tier"] == "tier1"]
    tier2 = [r for r in rows if r["split"] == "pupil" and r["tier"] == "tier2"]

    def arr(rs: list[dict], key: str) -> np.ndarray:
        return np.array([r[key] for r in rs], dtype=np.float64)

    c_comb = arr(cohort, "combined")
    t1_comb = arr(tier1, "combined")

    a_primary = auc(c_comb, t1_comb)
    ci_lo, ci_hi = bootstrap_auc_ci(c_comb, t1_comb)
    tier = o06_tier(a_primary, ci_lo)

    a_zA = auc(arr(cohort, "z_A"), arr(tier1, "z_A"))
    a_zB = auc(arr(cohort, "z_B"), arr(tier1, "z_B"))

    # precision@k over the pooled cohort + tier-1 ranking
    pool = sorted(cohort + tier1, key=lambda r: -r["combined"])
    labels = [1 if r["split"] == "pupil" else 0 for r in pool]
    base_rate = sum(labels) / len(labels)
    p_at_k = {k: precision_at_k(labels, k) for k in PRECISION_AT_K}

    # Tier 2 sensitivity, reported separately and never pooled (design §2)
    t2_comb = arr(tier2, "combined")
    a_t2 = auc(c_comb, t2_comb)
    t2_lo, t2_hi = bootstrap_auc_ci(c_comb, t2_comb)

    # §4.6 confounds
    conf = [r for r in cohort + tier1 if r["mm_per_px"] is not None]
    mmpx = np.array([r["mm_per_px"] for r in conf])
    natw = np.array([float(r["native_px_width"]) for r in conf])
    comb = np.array([r["combined"] for r in conf])
    rho_mm = spearman(mmpx, comb)
    rho_nat = spearman(natw, comb)
    auc_mm = auc(
        np.array([r["mm_per_px"] for r in conf if r["split"] == "cohort"]),
        np.array([r["mm_per_px"] for r in conf if r["split"] == "pupil"]),
    )

    # §4.5 per-artist
    by_artist: dict[str, list[float]] = {}
    for r in tier1:
        by_artist.setdefault(r["creator"] or "?", []).append(r["combined"])

    cohort_median = float(np.median(c_comb))

    L = [
        "# Pupil-cohort validation report (O06 / D32)",
        "",
        f"**Design:** [`{DESIGN_DOC}`]({DESIGN_DOC.split('/')[-1]}) · "
        f"**Scores:** `scores_v1` · **Generated:** `{_utc_now()}`",
        "",
        "Every threshold, seed, and k below is transcribed from the pre-registration, "
        "which was committed before any pupil work was acquired or scored.",
        "",
        "## Counts",
        "",
        "| Group | N | Role |",
        "|---|---:|---|",
        f"| cohort | {len(cohort)} | fit normals (LOO self-scores); negative class |",
        f"| pupil — Tier 1 (documented pupils) | {len(tier1)} | positive class, primary analysis |",
        f"| pupil — Tier 2 (associates) | {len(tier2)} | sensitivity only, never pooled |",
        "",
        f"Held-out negatives available to the D04 probe before this phase: **1**. "
        f"Available to O06 now: **{len(tier1)}**.",
        "",
        "### Acquisition adherence",
        "",
        "The pre-registered roster listed 87 search hits (Tier 1 = 69, Tier 2 = 18). "
        "Four were lost to rules written before acquisition, none by choice after "
        "seeing a score:",
        "",
        "| Work | Creator | Why dropped |",
        "|---|---|---|",
        "| `SK-C-371` | Govert Flinck | already claimed as `excluded/other_artist` by a "
        "Phase 1 description probe; design §3.1 forbids re-splitting a claimed work |",
        "| `SK-C-1598` | Jan Lievens | same (title *Portret van Rembrandt*) |",
        "| `SK-A-1627` | Jan Lievens | same |",
        "| `SK-A-4034` | Aert de Gelder | IIIF returned 400; fail-closed to "
        "`excluded/missing_image` per the standing rule |",
        "",
        "Reading §3.1 literally costs three works. Amending it after seeing which three "
        "would have been a post-hoc change to a pre-registered rule, so it was not done.",
        "",
        "## O06 outcome",
        "",
        f"**Result: `{tier}`**",
        "",
        "| Quantity | Value |",
        "|---|---|",
        f"| AUC (cohort vs Tier 1, `combined`) | **{fmt(a_primary)}** |",
        f"| bootstrap 95% CI | [{fmt(ci_lo)}, {fmt(ci_hi)}] |",
        f"| CI lower bound `L` vs 0.50 | {'above' if ci_lo > 0.5 else 'at or below'} |",
        f"| resamples / seed | {N_BOOTSTRAP} / {BOOTSTRAP_SEED} |",
        "",
        "Rule (design §5, not retuned): **pass** = `L > 0.50` and AUC ≥ 0.70; "
        "**weak** = `L > 0.50` and 0.50 < AUC < 0.70; **fail** = `L ≤ 0.50`.",
        "",
        "## Per-signal AUC (design §4.4)",
        "",
        "| Signal | AUC |",
        "|---|---|",
        f"| `z_A` — ResNet50 cosine-to-centroid | {fmt(a_zA)} |",
        f"| `z_B` — RMS of 8 feature z-scores | {fmt(a_zB)} |",
        f"| `combined` = z_A + z_B | {fmt(a_primary)} |",
        "",
        "## precision@k (design §4.3)",
        "",
        f"Pooled cohort + Tier 1 ranking by `combined` descending, N={len(pool)}. "
        f"Base rate (a random pick being a pupil) = **{base_rate:.3f}**.",
        "",
        "| k | precision@k | vs base rate |",
        "|---:|---|---|",
    ]
    for k in PRECISION_AT_K:
        v = p_at_k[k]
        L.append(f"| {k} | {fmt(v, 3)} | {v - base_rate:+.3f} |")

    L += [
        "",
        "## Tier 2 sensitivity (design §2 — reported, never pooled)",
        "",
        "| Quantity | Value |",
        "|---|---|",
        f"| N | {len(tier2)} |",
        f"| AUC (cohort vs Tier 2) | {fmt(a_t2)} |",
        f"| bootstrap 95% CI | [{fmt(t2_lo)}, {fmt(t2_hi)}] |",
        "",
        "## Confound checks (design §4.6)",
        "",
        "| Check | Value | Reading |",
        "|---|---|---|",
        f"| Spearman ρ(mm/px of analyzed image, `combined`) | {fmt(rho_mm, 3)} | "
        "non-zero ⇒ the score partly tracks digitization scale, not handling |",
        f"| Spearman ρ(native IIIF pixel width, `combined`) | {fmt(rho_nat, 3)} | "
        "non-zero ⇒ the score partly tracks how large a file the museum published |",
        f"| AUC on mm/px **alone** (cohort vs Tier 1) | {fmt(auc_mm)} | "
        "compare against the `combined` AUC above |",
        "",
        f"mm/px across the analyzed corpus spans {mmpx.min():.3f}–{mmpx.max():.3f} "
        f"({mmpx.max() / mmpx.min():.0f}× spread), so texture features are not measuring "
        "the same physical quantity across works. Design §6.4 records this as unfixed "
        "at this phase.",
        "",
        "## Per-artist breakdown (design §4.5)",
        "",
        f"Cohort median `combined` = {cohort_median:.4f}. A pupil group above it scores "
        "as more anomalous than the median firm Rembrandt.",
        "",
        "| Tier 1 creator | N | median `combined` | vs cohort median |",
        "|---|---:|---|---|",
    ]
    for name, vals in sorted(by_artist.items(), key=lambda kv: -float(np.median(kv[1]))):
        med = float(np.median(vals))
        L.append(f"| {name} | {len(vals)} | {med:+.4f} | {med - cohort_median:+.4f} |")

    L += [
        "",
        "## What this does and does not establish",
        "",
        "- O06 is a **surrogate** for D04, not a substitute (design §6.1). Pupils "
        "catalogued under their own names are not workshop pictures produced under "
        "Rembrandt's supervision.",
        "- O04 is unchanged by this report. `SK-A-3934` remains the sole D04 probe and "
        "its outcome is still computed from cohort LOO percentiles alone.",
        "- No cohort normal was fitted on any pupil row. The Signal A centroid and the "
        "Signal B feature means/stds are bit-identical to the pre-D32 fit manifest.",
        "",
        "## Artifacts",
        "",
        "| Artifact | Path |",
        "|---|---|",
        "| Pre-registration | `results/phase7_pupil_validation_design.md` |",
        "| Scores | `results/scores/scores_v1.csv` |",
        "| Geometry | `data/cohortscope.sqlite` (`works.mm_per_px_analyzed`) |",
        "| D04 outcome (untouched) | `results/validation_report.md` |",
        "",
    ]

    summary = {
        "o06": tier,
        "auc": a_primary,
        "ci": [ci_lo, ci_hi],
        "auc_zA": a_zA,
        "auc_zB": a_zB,
        "precision_at_k": p_at_k,
        "base_rate": base_rate,
        "auc_tier2": a_t2,
        "rho_mm_per_px": rho_mm,
        "auc_mm_per_px": auc_mm,
        "n_cohort": len(cohort),
        "n_tier1": len(tier1),
        "n_tier2": len(tier2),
    }
    return "\n".join(L), summary


def run(*, force: bool) -> int:
    if REPORT_PATH.exists() and not force:
        print(f"Refusing to overwrite {REPORT_PATH}; pass --force", file=sys.stderr)
        return 1
    rows = load_rows()
    text, summary = build_report(rows)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(text, encoding="utf-8")
    print(f"Wrote {REPORT_PATH}")
    print(json.dumps(summary, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="O06 pupil-cohort evaluation (D32)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing report")
    args = parser.parse_args()
    return run(force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
