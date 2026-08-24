"""
CohortScope demo viewer (D31 / T080) — read-only Gradio UI for the human demo video (T072).

Loads precomputed scores + local JPEGs only. Does not import score/embed/acquire
or recompute anything. Not a product claim: the method is closed as a negative
result (O04 weak, O06/O09/O11/O13 all fail). See results/dossier/ for the findings page.
Created solely as a presentation aid for the datathon video submission.
"""

from __future__ import annotations

import argparse
import socket
import sys
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
    "**Demo viewer — the method does not work and this ranking is not usable.**\n\n"
    "Read-only view of `scores_v1.csv` + `data/images/`; scores are not recomputed. "
    "Five pre-registered held-out outcomes: O04 `weak` (N=1), then O06, O09, O11 and "
    "O13 all `fail`. Against 67 documented Rembrandt pupils this ranking scores "
    "AUC 0.419 — below chance — and it stays at chance after the scale confound is "
    "removed (O09/O11) and across a 2× resolution sweep (O13). In all four pupil "
    "tests a single acquisition-metadata column separates the classes better than "
    "the whole pipeline.\n\n"
    "The findings page is `results/dossier/` (build with `python dossier.py`); the "
    "reports are `results/pupil_validation_report.md`, `tile_validation_report.md`, "
    "`tile_embedding_report.md` and `resolution_sweep_report.md`."
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


PAGES_URL = "https://jialaiying.github.io/CohortScope/"

SHARE_BLOCKED_HELP = f"""
Gradio's public share link could not start.

Gradio tunnels through a helper binary (frpc) that it downloads from Hugging Face.
On this machine Windows Application Control / Smart App Control refuses to execute
that binary (OSError WinError 4557, "Potentially unwanted application"), so the
tunnel process never starts. The binary is present and the tunnel server is
reachable; the operating system is blocking the launch, and nothing in this
repository can work around that.

Three things that do give you a URL:

  1. The findings page is static HTML and is already published:
         {PAGES_URL}
     That is the deliverable. It needs no tunnel and no running process.

  2. To show this viewer on another device on the same network, run:
         python demo_app.py --host 0.0.0.0
     and open http://<this machine's LAN IP>:7860 from the other device.

  3. If you specifically need a gradio.live link, run it from a machine without
     Application Control, or from Colab / Codespaces / WSL.
"""


def lan_ip() -> str:
    """Best-effort local address, for the --host 0.0.0.0 hint. No traffic is sent."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--share",
        action="store_true",
        help="attempt a public gradio.live tunnel (blocked by Application Control on "
             "some Windows machines; see --help output on failure)",
    )
    ap.add_argument(
        "--host",
        default="127.0.0.1",
        help="bind address; use 0.0.0.0 to reach the viewer from another device on "
             "the same network (default: 127.0.0.1)",
    )
    # Default None so Gradio scans upward from 7860 instead of dying on a stale server.
    ap.add_argument("--port", type=int, default=None, help="bind port (default: first free from 7860)")
    args = ap.parse_args()

    app = build_app()

    if args.host == "0.0.0.0":
        print(f"Reachable on this network at http://{lan_ip()}:{args.port or 7860} "
              "(check the port Gradio prints below)")

    # Gradio does not raise when the tunnel fails; it prints a one-line warning and
    # serves locally anyway, which is what made this look like it "just doesn't work".
    # Launch without blocking, inspect whether a share URL actually materialised, say
    # something useful if it did not, then block.
    app.launch(
        share=args.share,
        server_name=args.host,
        server_port=args.port,
        prevent_thread_lock=True,
    )

    if args.share and not getattr(app, "share_url", None):
        print(SHARE_BLOCKED_HELP, file=sys.stderr)
    elif args.share:
        print(f"Public URL: {app.share_url}")

    app.block_thread()


if __name__ == "__main__":
    main()
