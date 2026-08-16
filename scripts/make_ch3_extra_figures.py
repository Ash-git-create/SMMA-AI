"""Two more Chapter 3 figures.

Fig 3.2  The three error injections, shown as before/after triplets.
Fig 3.3  The experiment pipeline: clean room -> inject -> per-step run -> measure.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from pathlib import Path

OUT = Path(r"D:/Master Thesis/SMMA_AI_Systems/docs/figures")
INK = "#222222"
GREEN = "#4C9F70"
RED = "#C0504D"
BLUE = "#3B6EA5"
GREY = "#666666"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})


def _box(ax, x, y, w, h, color, text, fs=9, bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.05",
                                linewidth=1.4, edgecolor=color, facecolor=color + "18"))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            fontweight="bold" if bold else "normal", color=INK)


def _arrow(ax, p0, p1, color=INK):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=13, linewidth=1.5,
                                 color=color, shrinkA=2, shrinkB=2))


def fig_injection():
    fig, ax = plt.subplots(figsize=(9.0, 3.6))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 6)
    ax.axis("off")
    rows = [
        ("entity disambiguation", "(Georgia, capital is, Tbilisi)", "(Georgia, capital is, Atlanta)"),
        ("qualifier loss", "(Obama, president of, USA in 2009-2017)", "(Obama, president of, USA)"),
        ("relation strengthening", "(exercise, associated with, longer life)", "(exercise, caused, longer life)"),
    ]
    ys = [4.3, 2.6, 0.9]
    for (label, before, after), y in zip(rows, ys):
        _box(ax, 0.2, y, 4.2, 1.1, GREEN, before, fs=8)
        _box(ax, 7.6, y, 4.2, 1.1, RED, after, fs=8)
        _arrow(ax, (4.5, y + 0.55), (7.5, y + 0.55), color=RED)
        ax.text(6.0, y + 0.95, label, ha="center", fontsize=8, color=RED)
    ax.text(2.3, 5.6, "original fact", ha="center", fontsize=8.5, color=GREEN, fontweight="bold")
    ax.text(9.7, 5.6, "corrupted fact", ha="center", fontsize=8.5, color=RED, fontweight="bold")
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"fig_injection.{ext}", dpi=200, bbox_inches="tight")
    plt.close(fig)


def fig_pipeline():
    fig, ax = plt.subplots(figsize=(9.4, 3.4))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 5)
    ax.axis("off")
    _box(ax, 0.2, 2.6, 2.7, 1.6, GREY,
         "Clean room\nclear graph, load\n50,000 T-REx facts,\nreplay extraction", fs=8)
    _box(ax, 3.4, 2.6, 2.4, 1.6, RED, "Inject\n15 index cases\nper error type", fs=8)
    _box(ax, 6.3, 2.6, 2.7, 1.6, BLUE,
         "Run, each step\nretrieve, synthesise,\nwrite back\n(audit if enabled)", fs=8)
    _box(ax, 9.5, 2.6, 2.3, 1.6, GREEN, "Measure\nprobes, task\nmetrics, SIR fit", fs=8)
    _arrow(ax, (2.9, 3.4), (3.4, 3.4))
    _arrow(ax, (5.8, 3.4), (6.3, 3.4))
    _arrow(ax, (9.0, 3.4), (9.5, 3.4))
    # loop arrow on "Run"
    _arrow(ax, (7.0, 2.6), (7.0, 1.7), color=BLUE)
    _arrow(ax, (7.0, 1.7), (8.3, 1.7), color=BLUE)
    _arrow(ax, (8.3, 1.7), (8.3, 2.6), color=BLUE)
    ax.text(7.65, 1.45, "repeat for 10 steps", ha="center", fontsize=7.5, color=BLUE)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"fig_pipeline.{ext}", dpi=200, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    fig_injection()
    fig_pipeline()
    print("wrote fig_injection and fig_pipeline (png+pdf)")
