"""
CohortScope demo viewer (D31 / T080) — read-only Gradio UI for the human demo video (T072).

Loads precomputed scores + local JPEGs only. Does not import score/embed/acquire
or recompute anything. Not a product claim: O04 = weak (N=1); O06 = fail (N=67).
Created solely as a presentation aid for the datathon video submission.
"""

from __future__ import annotations

from pathlib import Path

import gradio as gr
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent
SCORES_CSV = ROOT / "results" / "scores" / "scores_v1.csv"
IMAGES_DIR = ROOT / "data" / "images"

# From results/validation_report.md (scores_v1) — labeled as report values, not recomputed.
COHORT_MEDIAN_COMBINED = -0.116810
COHORT_P95_COMBINED = 2.106898
VALIDATION_ID = "SK-A-3934"
AMBIGUOUS_ID = "SK-A-4096"

BANNER_DEFAULT = (
    "**Demo viewer — O04 = weak (N=1), O06 = fail (N=67). Not a validated product.**\n\n"
    "Read-only view of `scores_v1.csv` + `data/images/`. "
    "Scores are not recomputed; science deliverable remains tables/CSV. "
    "Against 67 documented Rembrandt pupils this ranking scores AUC 0.419 — below "
    "chance; see `results/pupil_validation_report.md`."
)
BANNER_AMBIGUOUS = (
    "**ambiguous — excluded from O04 (D21)**\n\n"
    f"`{AMBIGUOUS_ID}` is scored exploratorily only. "
    "It never fits normals and never counts toward O04 / T043."
)


def load_scores() -> pd.DataFrame:
    if not SCORES_CSV.is_file():
        raise FileNotFoundError(f"Missing scores CSV: {SCORES_CSV}")
    df = pd.read_csv(SCORES_CSV)
    df = df.sort_values("rank_combined", ascending=True).reset_index(drop=True)
    return df


DF = load_scores()
LABEL_TO_ROW = {
    f"{int(r.rank_combined):02d} | {r.object_number} | {r.split} | {r.title}": r
    for r in DF.itertuples(index=False)
}
DROPDOWN_CHOICES = list(LABEL_TO_ROW.keys())
DEFAULT_LABEL = next(
    (lab for lab, row in LABEL_TO_ROW.items() if row.object_number == VALIDATION_ID),
    DROPDOWN_CHOICES[0],
)


def _image_path(object_number: str) -> Path | None:
    path = IMAGES_DIR / f"{object_number}.jpg"
    return path if path.is_file() else None


def _z_bar_chart(z_a: float, z_b: float):
    fig, ax = plt.subplots(figsize=(4.5, 2.8))
    ax.bar(["z_A (embed)", "z_B (hand)"], [z_a, z_b], color=["#4C78A8", "#F58518"])
    ax.axhline(0.0, color="#333333", linewidth=0.8)
    ax.set_ylabel("z-score")
    ax.set_title("z_A vs z_B (precomputed)")
    fig.tight_layout()
    return fig


def _split_badge(split: str) -> str:
    return f"**Split:** `{split}`"


def _detail_markdown(row) -> str:
    lines = [
        f"### {row.object_number} — {row.title}",
        _split_badge(row.split),
        "",
        f"| Metric | Value |",
        f"|---|---|",
        f"| rank_combined | {int(row.rank_combined)} / 25 |",
        f"| combined | {row.combined:.6f} |",
        f"| dominant_signal | {row.dominant_signal} |",
        f"| z_A | {row.z_A:.6f} |",
        f"| z_B | {row.z_B:.6f} |",
        f"| driver_A | `{row.driver_A}` |",
        f"| driver_B_1 | `{row.driver_B_1}` |",
        f"| driver_B_2 | `{row.driver_B_2}` |",
    ]
    return "\n".join(lines)


def _validation_spotlight_md(row) -> str:
    clears_median = row.combined >= COHORT_MEDIAN_COMBINED
    clears_p95 = row.combined >= COHORT_P95_COMBINED
    return "\n".join(
        [
            "### Validation spotlight — SK-A-3934",
            "",
            f"- **combined** = `{row.combined:.6f}` · **rank** = `{int(row.rank_combined)}` / 25",
            "- **O04 = `weak`** (pre-registered rule; not retuned)",
            "",
            "Cohort reference (from `results/validation_report.md`, hard-coded):",
            f"- cohort median combined = `{COHORT_MEDIAN_COMBINED}`",
            f"- cohort p95 combined (O04 bar) = `{COHORT_P95_COMBINED}`",
            "",
            f"- clears median: **{clears_median}**",
            f"- clears p95: **{clears_p95}**",
            "",
            "**Explicit:** clears median, does **NOT** clear p95 → **weak**",
        ]
    )


def select_work(label: str):
    row = LABEL_TO_ROW[label]
    banner = BANNER_AMBIGUOUS if row.object_number == AMBIGUOUS_ID else BANNER_DEFAULT
    img = str(_image_path(row.object_number) or "")
    detail = _detail_markdown(row)
    fig = _z_bar_chart(float(row.z_A), float(row.z_B))
    if row.object_number == VALIDATION_ID:
        spotlight = _validation_spotlight_md(row)
    else:
        spotlight = (
            "_Select **SK-A-3934** (or use Validation spotlight) to show O04 weak detail._"
        )
    return banner, img, detail, fig, spotlight


def jump_validation():
    return DEFAULT_LABEL, *select_work(DEFAULT_LABEL)


def build_app() -> gr.Blocks:
    table_cols = [
        "rank_combined",
        "object_number",
        "split",
        "title",
        "combined",
        "dominant_signal",
        "z_A",
        "z_B",
    ]
    table_df = DF[table_cols].rename(columns={"rank_combined": "rank"})

    with gr.Blocks(title="CohortScope demo viewer") as demo:
        banner = gr.Markdown(BANNER_DEFAULT)

        gr.Markdown(f"### Rank explorer (all {len(DF)} scored works)")
        gr.Dataframe(value=table_df, interactive=False, wrap=True)

        with gr.Row():
            dropdown = gr.Dropdown(
                choices=DROPDOWN_CHOICES,
                value=DEFAULT_LABEL,
                label="Select work (sorted by rank_combined)",
                scale=4,
            )
            spotlight_btn = gr.Button("Validation spotlight → SK-A-3934", scale=1)

        with gr.Row():
            image = gr.Image(type="filepath", label="Image", height=420)
            with gr.Column():
                detail = gr.Markdown()
                chart = gr.Plot(label="z_A vs z_B")

        spotlight = gr.Markdown()

        demo.load(
            fn=select_work,
            inputs=dropdown,
            outputs=[banner, image, detail, chart, spotlight],
        )
        dropdown.change(
            fn=select_work,
            inputs=dropdown,
            outputs=[banner, image, detail, chart, spotlight],
        )
        spotlight_btn.click(
            fn=jump_validation,
            inputs=None,
            outputs=[dropdown, banner, image, detail, chart, spotlight],
        )

    return demo


def main() -> None:
    app = build_app()
    app.launch(share=False)


if __name__ == "__main__":
    main()
