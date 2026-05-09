"""
SIR curve plotter — generates sanity-check figures for the thesis.

Produces two plots saved to results/summaries/:
  1. sir_scenarios.png — S/I/R curves for three R₀ scenarios (controlled / borderline / epidemic)
  2. r0_sensitivity.png — peak infection % vs R₀ for a range of β/γ combinations

No Neo4j or LLM calls required. Run from project root with venv active:
    python scripts/plot_sir_curves.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from mpl_toolkits.axes_grid1.inset_locator import inset_axes

from src.sir.sir_model import SIRModel
from src.sir.r0_calculator import R0Calculator

SUMMARIES_DIR = ROOT / "results" / "summaries"
SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)

# KG baseline: 50K T-REx nodes, 10 initially infected
N_TOTAL = 50_000
I_SEED  = 10
S_INIT  = N_TOTAL - I_SEED
STEPS   = 200

SCENARIOS = [
    {"label": "Controlled  (R₀ = 0.5)",  "beta": 0.10, "gamma": 0.20, "color": "#2ca02c"},
    {"label": "Borderline  (R₀ = 1.0)",  "beta": 0.10, "gamma": 0.10, "color": "#ff7f0e"},
    {"label": "Epidemic    (R₀ = 3.0)",  "beta": 0.30, "gamma": 0.10, "color": "#d62728"},
]


def plot_scenarios() -> Path:
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), sharey=False)
    fig.suptitle(
        "SIR Model — KG Contamination Scenarios\n"
        f"(N={N_TOTAL:,} nodes, seed={I_SEED} infected)",
        fontsize=13, y=1.02,
    )

    for ax, scenario in zip(axes, SCENARIOS):
        model = SIRModel(beta=scenario["beta"], gamma=scenario["gamma"])
        calc  = R0Calculator.from_beta_gamma(beta=scenario["beta"], gamma=scenario["gamma"])
        traj  = model.run(S0=S_INIT, I0=I_SEED, R0=0, steps=STEPS)

        steps = [r["step"] for r in traj]
        S_pct = [r["S"] / N_TOTAL * 100 for r in traj]
        I_pct = [r["I"] / N_TOTAL * 100 for r in traj]
        R_pct = [r["R"] / N_TOTAL * 100 for r in traj]

        ax.plot(steps, S_pct, label="S (Susceptible)", color="#1f77b4", lw=2)
        ax.plot(steps, I_pct, label="I (Infected)",    color=scenario["color"], lw=2)
        ax.plot(steps, R_pct, label="R (Recovered)",   color="#9467bd", lw=2, linestyle="--")

        peak = model.peak_infected(S0=S_INIT, I0=I_SEED, R0=0, steps=STEPS)
        peak_pct = peak["I"] / N_TOTAL * 100

        ax.axvline(peak["step"], color=scenario["color"], lw=1, linestyle=":", alpha=0.7)

        # For near-zero peaks, show absolute count instead of 0.0%
        if peak_pct < 0.05:
            peak_label = f"Peak I: {peak['I']:.1f} nodes\nat T={peak['step']}"
        else:
            peak_label = f"Peak I: {peak_pct:.1f}%\nat T={peak['step']}"

        # Place annotation where it's visible regardless of scale
        ann_y = max(peak_pct, 5.0)
        ax.annotate(
            peak_label,
            xy=(peak["step"], peak_pct),
            xytext=(peak["step"] + 10, ann_y + 5),
            fontsize=8, color=scenario["color"],
            arrowprops=dict(arrowstyle="->", color=scenario["color"], lw=0.8),
        )

        ax.set_title(scenario["label"], fontsize=11)
        ax.set_xlabel("Time step")
        ax.set_ylabel("% of KG nodes")
        ax.set_ylim(0, 105)
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=0))
        ax.legend(fontsize=8, loc="upper right")
        ax.grid(True, alpha=0.3)
        ax.text(
            0.02, 0.97,
            f"β={scenario['beta']:.2f}  γ={scenario['gamma']:.2f}\nR₀={calc.r0:.1f}",
            transform=ax.transAxes, fontsize=8, va="top",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.8),
        )

        # For sub-epidemic scenarios: add a zoomed inset of the I curve
        if calc.r0 <= 1.0:
            axins = inset_axes(ax, width="45%", height="35%", loc="center right")
            axins.plot(steps[:30], I_pct[:30], color=scenario["color"], lw=1.5)
            axins.set_title("I (zoom)", fontsize=7)
            axins.yaxis.set_major_formatter(
                mticker.FuncFormatter(lambda v, _: f"{v*N_TOTAL/100:.0f}")
            )
            axins.set_ylabel("nodes", fontsize=6)
            axins.set_xlabel("step", fontsize=6)
            axins.tick_params(labelsize=6)
            axins.grid(True, alpha=0.3)

    fig.tight_layout()
    out = SUMMARIES_DIR / "sir_scenarios.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Saved: {out}")
    return out


def plot_r0_sensitivity() -> Path:
    """Peak infection % as a function of R₀ across a sweep of β/γ values."""
    r0_values = np.linspace(0.1, 5.0, 60)
    peak_pcts  = []

    for r0 in r0_values:
        beta  = r0 * 0.05          # fix γ=0.05, vary β
        gamma = 0.05
        model = SIRModel(beta=beta, gamma=gamma)
        peak  = model.peak_infected(S0=S_INIT, I0=I_SEED, R0=0, steps=500)
        peak_pcts.append(peak["I"] / N_TOTAL * 100)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.plot(r0_values, peak_pcts, color="#d62728", lw=2)
    ax.axvline(1.0, color="gray", lw=1.2, linestyle="--", label="R₀ = 1 (threshold)")
    ax.fill_between(r0_values, peak_pcts, alpha=0.15, color="#d62728")

    ax.set_xlabel("Basic Reproduction Number (R₀)", fontsize=11)
    ax.set_ylabel("Peak Infected (% of KG nodes)", fontsize=11)
    ax.set_title(
        f"R₀ Sensitivity — Peak KG Contamination\n(γ=0.05 fixed, N={N_TOTAL:,})",
        fontsize=12,
    )
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(decimals=1))
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, 5)
    ax.set_ylim(0, 105)

    # Annotate the epidemic threshold
    ax.annotate(
        "Epidemic\nzone",
        xy=(3.5, 60), fontsize=9, color="#d62728",
        ha="center",
    )
    ax.annotate(
        "Controlled\nzone",
        xy=(0.4, 10), fontsize=9, color="#2ca02c",
        ha="center",
    )

    fig.tight_layout()
    out = SUMMARIES_DIR / "r0_sensitivity.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Saved: {out}")
    return out


if __name__ == "__main__":
    print("Generating SIR plots...")
    plot_scenarios()
    plot_r0_sensitivity()
    print("\nDone. Open results/summaries/ to view the figures.")
