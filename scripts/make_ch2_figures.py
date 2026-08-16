"""Chapter 2 conceptual figures.

Fig 2.1  SIR compartments mapped onto knowledge-graph facts (S->I->R, beta/gamma).
Fig 2.2  Message-chain contagion (dilutes) vs shared-graph contagion (reinforces).

Outputs PNG + PDF to docs/figures/. Print-oriented: white background, dark text.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle
from pathlib import Path

OUT = Path(r"D:/Master Thesis/SMMA_AI_Systems/docs/figures")
OUT.mkdir(parents=True, exist_ok=True)

GREEN = "#4C9F70"
RED = "#C0504D"
BLUE = "#5B7DB1"
GREY = "#777777"
INK = "#222222"

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})


def box(ax, x, y, w, h, color, label, sub):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                linewidth=1.5, edgecolor=color, facecolor=color + "22"))
    ax.text(x + w / 2, y + h * 0.62, label, ha="center", va="center",
            fontsize=15, fontweight="bold", color=color)
    ax.text(x + w / 2, y + h * 0.24, sub, ha="center", va="center", fontsize=8.5, color=INK)


def arrow(ax, x0, y0, x1, y1, color=INK):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=16,
                                 linewidth=1.6, color=color, shrinkA=0, shrinkB=0))


def fig_sir():
    fig, ax = plt.subplots(figsize=(8.2, 2.7))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 3)
    ax.axis("off")
    box(ax, 0.4, 0.9, 2.4, 1.3, GREEN, "S", "clean fact,\nnot yet checked")
    box(ax, 3.8, 0.9, 2.4, 1.3, RED, "I", "contaminated\nfact")
    box(ax, 7.2, 0.9, 2.4, 1.3, BLUE, "R", "quarantined\nfact")
    arrow(ax, 2.85, 1.55, 3.75, 1.55)
    arrow(ax, 6.25, 1.55, 7.15, 1.55)
    ax.text(3.3, 1.95, r"$\beta$", ha="center", fontsize=14, color=INK)
    ax.text(3.3, 1.2, "retrieve +\nwrite error", ha="center", va="top", fontsize=7.5, color=GREY)
    ax.text(6.7, 1.95, r"$\gamma$", ha="center", fontsize=14, color=INK)
    ax.text(6.7, 1.2, "validation\ncatches it", ha="center", va="top", fontsize=7.5, color=GREY)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"fig_sir_compartments.{ext}", dpi=200, bbox_inches="tight")
    plt.close(fig)


def fig_contrast():
    fig, (axl, axr) = plt.subplots(1, 2, figsize=(9.2, 3.6))
    for ax in (axl, axr):
        ax.set_xlim(0, 10)
        ax.set_ylim(0, 8)
        ax.axis("off")

    # Left: message chain, error shrinks along the chain
    axl.set_title("Message chain: error is diluted", fontsize=10, color=INK)
    xs = [1.4, 3.8, 6.2, 8.6]
    sizes = [0.45, 0.33, 0.22, 0.12]
    for i, x in enumerate(xs):
        axl.add_patch(Circle((x, 3.2), 0.62, facecolor="#eeeeee", edgecolor=GREY, linewidth=1.3))
        axl.text(x, 3.2, f"A{i+1}", ha="center", va="center", fontsize=10, color=INK)
        axl.add_patch(Circle((x, 5.1), sizes[i], facecolor=RED, edgecolor="none",
                             alpha=0.35 + 0.15 * (3 - i)))
        if i < len(xs) - 1:
            arrow(axl, x + 0.66, 3.2, xs[i + 1] - 0.66, 3.2)
    axl.text(5.0, 6.4, "error passes once, shrinks each step", ha="center", fontsize=8.5, color=GREY)

    # Right: shared graph, one contaminated fact reused and spawns more
    axr.set_title("Shared graph: error is reinforced", fontsize=10, color=INK)
    axr.add_patch(Circle((5.0, 5.6), 0.7, facecolor=RED, edgecolor="none", alpha=0.85))
    axr.text(5.0, 5.6, "bad\nfact", ha="center", va="center", fontsize=8.5, color="white")
    # agents reading it
    for ax_x in (1.6, 5.0, 8.4):
        axr.add_patch(Circle((ax_x, 2.0), 0.55, facecolor="#eeeeee", edgecolor=GREY, linewidth=1.2))
        arrow(axr, 5.0, 5.0, ax_x, 2.5, color=GREY)
    axr.text(1.6, 2.0, "A", ha="center", va="center", fontsize=9)
    axr.text(5.0, 2.0, "A", ha="center", va="center", fontsize=9)
    axr.text(8.4, 2.0, "A", ha="center", va="center", fontsize=9)
    # new contaminated facts spawned
    for nx in (2.6, 7.4):
        axr.add_patch(Circle((nx, 6.7), 0.42, facecolor=RED, edgecolor="none", alpha=0.7))
        arrow(axr, 4.4, 6.0, nx + 0.3, 6.6, color=RED)
    axr.text(5.0, 0.5, "many agents retrieve it; it spawns more", ha="center", fontsize=8.5, color=GREY)

    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"fig_contagion_contrast.{ext}", dpi=200, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    fig_sir()
    fig_contrast()
    print("wrote fig_sir_compartments and fig_contagion_contrast (png+pdf) to", OUT)
