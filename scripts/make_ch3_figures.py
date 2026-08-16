"""Chapter 3 conceptual figures.

Fig 3.1  System architecture: three agents around a central Neo4j knowledge graph,
         with the retrieval (beta) and validation (gamma) channels marked.

Outputs PNG + PDF to docs/figures/. Print-oriented: white background, dark text.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from pathlib import Path

OUT = Path(r"D:/Master Thesis/SMMA_AI_Systems/docs/figures")
OUT.mkdir(parents=True, exist_ok=True)

INK = "#222222"
KGC = "#3B6EA5"
EXT = "#4C9F70"
ORC = "#B8860B"
VAL = "#7A5195"
RED = "#C0504D"
GREY = "#666666"

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})


def box(ax, x, y, w, h, color, title, sub="", fc=None):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
                                linewidth=1.6, edgecolor=color,
                                facecolor=(fc if fc else color + "18")))
    ax.text(x + w / 2, y + h * (0.63 if sub else 0.5), title, ha="center", va="center",
            fontsize=10.5, fontweight="bold", color=color)
    if sub:
        ax.text(x + w / 2, y + h * 0.28, sub, ha="center", va="center", fontsize=7.8, color=INK)


def arr(ax, p0, p1, color=INK, style="-|>", lw=1.6, dashed=False):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=14, linewidth=lw,
                                 color=color, shrinkA=2, shrinkB=2,
                                 linestyle="--" if dashed else "-"))


def fig_arch():
    fig, ax = plt.subplots(figsize=(9.4, 5.8))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis("off")

    # Central knowledge graph
    box(ax, 4.4, 3.3, 3.4, 1.8, KGC, "Neo4j knowledge graph",
        "shared memory\neach fact: value, confidence,\nlineage, provenance")

    # Text sources + extraction/synthesis (left) -- Mistral drives the propagation loop
    box(ax, 0.3, 6.3, 3.0, 1.1, GREY, "Text sources", "HotpotQA, FEVER")
    box(ax, 0.3, 3.5, 3.3, 1.7, EXT, "ExtractionAgent",
        "Mistral Nemo 12B\nextract facts from text,\nand synthesise new facts\nfrom retrieved ones")
    arr(ax, (1.8, 6.3), (1.8, 5.2), color=GREY)
    # write channel (extracted + derived facts) into KG
    arr(ax, (3.6, 4.7), (4.4, 4.6), color=EXT)
    ax.text(4.0, 4.92, "write facts", ha="center", fontsize=7, color=EXT)
    # retrieval channel out of KG (beta) -- feeds synthesis
    arr(ax, (4.4, 3.9), (3.6, 3.9), color=EXT)
    ax.text(4.0, 3.62, r"retrieve ($\beta$)", ha="center", fontsize=7, color=EXT)

    # Validation (right), with the OrchestrationAgent judge inside it -- Llama
    box(ax, 8.6, 2.4, 3.1, 2.0, VAL, "ValidationAgent",
        "Llama 3.1 8B\naudit, quarantine,\ncascade-deprecate\n(judge: OrchestrationAgent)")
    arr(ax, (7.8, 4.3), (8.6, 3.7), color=VAL)
    ax.text(8.2, 4.25, "audit", ha="center", fontsize=7.5, color=VAL)
    arr(ax, (8.6, 3.1), (7.8, 3.6), color=VAL)
    ax.text(8.25, 2.95, r"quarantine ($\gamma$)", ha="center", fontsize=7.5, color=VAL)

    # Error injector (bottom left, controlled)
    box(ax, 0.3, 0.7, 3.0, 1.3, RED, "ErrorInjector", "controlled\n3 error types")
    arr(ax, (3.3, 1.5), (4.7, 3.3), color=RED, dashed=True)
    ax.text(4.05, 2.15, "inject\nindex cases", ha="center", fontsize=7, color=RED)

    ax.text(6.1, 0.5, "Mistral Nemo runs extraction and synthesis; Llama 3.1 8B runs the "
            "validation judge.", ha="center", fontsize=7.5, color=GREY)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(OUT / f"fig_architecture.{ext}", dpi=200, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    fig_arch()
    print("wrote fig_architecture (png+pdf) to", OUT)
