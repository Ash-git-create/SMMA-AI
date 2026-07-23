"""
Phase 5 publication figures (task #26).

Renders the two [FIG] markers in docs/chapters/ch5_results_phase23.md into
thesis-ready figures under docs/figures/ (both .png at 300 dpi and .pdf).

    python scripts/make_figures.py        # from repo root

HARD RULE (CLAUDE.md "Analysis & Write-up Discipline" #1): every number plotted
comes from an archived CSV in results/summaries/. Nothing is hand-typed. The
fitted SIR curves are forward-simulated with the *same* difference equations used
by scripts/fit_sir.py (src/sir/sir_model.py) so the drawn curve is literally what
the archived (beta, gamma) reproduce.

Figures produced
----------------
1. fig_baseline_trajectories       (ch5 line 27, S5.1) cumulative propagated /
   exposed per baseline seed (42-45) + seed-mean.  Reads the 4 baseline
   trajectory CSVs.
2. fig_sir_fit_It                   (ch5 line 346, S5.5) empirical vs fitted I(t),
   small-multiples per arm.  Reads every arm's trajectory CSV for the empirical
   I(t) and the archived SIR-fit CSVs for (beta, gamma).
3. fig_r0_by_arm                    (ch5 line 346, S5.5) fitted R0 per arm with the
   R0 = 1 critical line; gamma = 0 arms annotated "undefined" rather than faked.
   Reads the archived SIR-fit CSVs.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SUMM = ROOT / "results" / "summaries"
OUTDIR = ROOT / "docs" / "figures"
OUTDIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Style: thesis-appropriate serif, colourblind-safe categorical hues (validated
# dataviz reference palette, light surface #fcfcfb).
# ---------------------------------------------------------------------------
plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["DejaVu Serif", "Times New Roman", "Nimbus Roman", "serif"],
    "mathtext.fontset": "dejavuserif",
    "font.size": 10,
    "axes.titlesize": 11,
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 8.5,
    "axes.edgecolor": "#c3c2b7",
    "axes.linewidth": 0.8,
    "axes.grid": True,
    "grid.color": "#e1e0d9",
    "grid.linewidth": 0.6,
    "figure.facecolor": "#fcfcfb",
    "axes.facecolor": "#fcfcfb",
    "savefig.facecolor": "#fcfcfb",
})

INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"

# Fixed arm -> hue map (dataviz categorical slots), consistent across figures.
ARM_COLOR = {
    "baseline":            "#2a78d6",  # blue
    "ablation_floor":      "#1baf7a",  # aqua
    "ablation_validation": "#4a3aa7",  # violet
    "mitigated":           "#eb6834",  # orange
    "mitigated_tuned":     "#eda100",  # yellow
    "oracle":              "#008300",  # green
    "control":             "#e34948",  # red (reserved)
}
ARM_LABEL = {
    "baseline": "baseline",
    "ablation_floor": "floor",
    "ablation_validation": "validation",
    "mitigated": "mitigated",
    "mitigated_tuned": "mitigated_tuned",
    "oracle": "oracle",
}

ERROR_TYPES = ("entity_disambiguation", "qualifier_loss", "relation_strengthening")


# ---------------------------------------------------------------------------
# Robust CSV reading (some archives are cp1252 from Excel re-saves).
# ---------------------------------------------------------------------------
def read_rows(path: Path) -> list[dict]:
    for enc in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            with open(path, newline="", encoding=enc) as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    # last resort: replace undecodable bytes
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))


def _f(v, default=np.nan):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# SIR forward simulation (identical equations to src/sir/sir_model.py).
# ---------------------------------------------------------------------------
def simulate_I(beta: float, gamma: float, S0: float, I0: float, steps: int) -> np.ndarray:
    S, I, R = float(S0), float(I0), 0.0
    out = [I]
    for _ in range(steps):
        N = S + I + R
        if N == 0:
            S = I = R = 0.0
            out.append(I)
            continue
        new_inf = min(beta * (S / N) * I, S)
        new_rec = min(gamma * I, I)
        S = S - new_inf
        I = I + new_inf - new_rec
        R = R + new_rec
        out.append(I)
    return np.array(out)


def empirical_I(rows: list[dict]) -> tuple[np.ndarray, np.ndarray, float, float]:
    """Reconstruct SIR compartment I(t) = gt_total - det_R_contam (see fit_sir.py)."""
    steps = np.array([int(_f(r["step"])) for r in rows])
    gt_total = np.array([_f(r["gt_total"]) for r in rows])
    det_R = np.array([_f(r["det_R_contam"]) for r in rows])
    I_obs = gt_total - det_R
    N = _f(rows[0]["S"])
    I0 = float(I_obs[0])
    return steps, I_obs, N, I0


def cumulative_series(rows: list[dict]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """steps, cumulative propagated (sum gt_prop_*), cumulative exposed (cum_exposed)."""
    steps = np.array([int(_f(r["step"])) for r in rows])
    prop = np.array([
        sum(_f(r.get(f"gt_prop_{t}", 0.0), 0.0) for t in ERROR_TYPES) for r in rows
    ])
    exposed = np.array([_f(r["cum_exposed"]) for r in rows])
    return steps, prop, exposed


# ---------------------------------------------------------------------------
# SIR-fit parameter lookup keyed by run_tag.
# ---------------------------------------------------------------------------
def load_fits() -> dict[str, dict]:
    fits: dict[str, dict] = {}
    fit_files = [
        "phase35_sir_fit.csv",
        "phase37_sir_fit_mitigated_seeds.csv",
        "phase38_sir_fit_oracle.csv",
        "phase39_sir_fit_mitigated_tuned.csv",
    ]
    for fname in fit_files:
        p = SUMM / fname
        if not p.exists():
            print(f"  WARNING: fit file missing: {fname}")
            continue
        for r in read_rows(p):
            tag = r["run_tag"]
            r0_raw = r.get("r0", "NA")
            r0 = _f(r0_raw, np.nan)
            fits[tag] = {
                "beta": _f(r["beta"]),
                "gamma": _f(r["gamma"]),
                "r0": r0,
                "seed": r.get("seed"),
            }
    return fits


def savefig(fig, stem: str) -> None:
    for ext in ("png", "pdf"):
        out = OUTDIR / f"{stem}.{ext}"
        fig.savefig(out, dpi=300, bbox_inches="tight")
        print(f"  wrote {out.relative_to(ROOT)}")
    plt.close(fig)


# ===========================================================================
# FIGURE 1 - baseline cumulative propagated / exposed per seed (ch5 S5.1)
# ===========================================================================
def fig_baseline_trajectories() -> None:
    print("Figure 1: baseline trajectories per seed")
    seed_files = {
        42: "phase32_baseline_trajectory.csv",
        43: "phase33_baseline_s43_trajectory.csv",
        44: "phase33_baseline_s44_trajectory.csv",
        45: "phase33_baseline_s45_trajectory.csv",
    }
    prop_by_seed, exp_by_seed, steps_ref = {}, {}, None
    for seed, fname in seed_files.items():
        p = SUMM / fname
        if not p.exists():
            print(f"  MISSING: {fname} -- seed {seed} skipped")
            continue
        steps, prop, exposed = cumulative_series(read_rows(p))
        prop_by_seed[seed] = prop
        exp_by_seed[seed] = exposed
        steps_ref = steps
    if not prop_by_seed:
        print("  no baseline data; figure skipped")
        return

    prop_mat = np.vstack(list(prop_by_seed.values()))
    exp_mat = np.vstack(list(exp_by_seed.values()))
    prop_mean = prop_mat.mean(axis=0)
    exp_mean = exp_mat.mean(axis=0)

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.2), sharex=True)
    panels = [
        (axes[0], prop_by_seed, prop_mean, "Cumulative propagated errors",
         "#2a78d6"),
        (axes[1], exp_by_seed, exp_mean, "Cumulative exposed contexts",
         "#eb6834"),
    ]
    for ax, by_seed, mean, ylabel, hue in panels:
        for seed, y in sorted(by_seed.items()):
            ax.plot(steps_ref, y, color=hue, alpha=0.35, linewidth=1.2, zorder=2)
        ax.plot(steps_ref, mean, color=hue, alpha=1.0, linewidth=2.4,
                zorder=3, label="seed mean (n=4)")
        # direct-label each seed's endpoint
        for seed, y in sorted(by_seed.items()):
            ax.annotate(f"s{seed}", xy=(steps_ref[-1], y[-1]),
                        xytext=(3, 0), textcoords="offset points",
                        va="center", ha="left", fontsize=7.5, color=INK2)
        ax.set_ylabel(ylabel, color=INK)
        ax.set_xlabel("Pipeline step", color=INK)
        ax.set_xlim(0, steps_ref[-1] + 1.2)
        ax.set_xticks(range(0, int(steps_ref[-1]) + 1, 2))
        ax.margins(y=0.08)
        ax.legend(loc="upper left", frameon=False)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)

    fig.suptitle("Baseline contamination trajectories, seeds 42-45",
                 fontsize=12, color=INK, y=1.02)
    fig.tight_layout()
    savefig(fig, "fig_baseline_trajectories")


# ===========================================================================
# FIGURE 2 - empirical vs fitted I(t) per arm (ch5 S5.5)
# ===========================================================================
def fig_sir_fit() -> None:
    print("Figure 2: empirical vs fitted I(t) per arm")
    fits = load_fits()

    # (arm, seed, trajectory file, fit run_tag)
    records = [
        ("baseline", 42, "phase32_baseline_trajectory.csv", "baseline"),
        ("baseline", 43, "phase33_baseline_s43_trajectory.csv", "baseline_s43"),
        ("baseline", 44, "phase33_baseline_s44_trajectory.csv", "baseline_s44"),
        ("baseline", 45, "phase33_baseline_s45_trajectory.csv", "baseline_s45"),
        ("ablation_floor", 42, "phase32_ablation_floor_trajectory.csv", "ablation_floor"),
        ("ablation_validation", 42, "phase32_ablation_validation_trajectory.csv", "ablation_validation"),
        ("mitigated", 42, "phase32_mitigated_trajectory.csv", "mitigated"),
        ("mitigated", 43, "phase37_mitigated_s43_trajectory.csv", "mitigated_s43"),
        ("mitigated", 44, "phase37_mitigated_s44_trajectory.csv", "mitigated_s44"),
        ("mitigated", 45, "phase37_mitigated_s45_trajectory.csv", "mitigated_s45"),
        ("oracle", 42, "phase38_oracle_trajectory.csv", "oracle"),
        ("mitigated_tuned", 42, "phase39_mitigated_tuned_trajectory.csv", "mitigated_tuned"),
    ]

    arm_order = ["baseline", "ablation_floor", "ablation_validation",
                 "mitigated", "oracle", "mitigated_tuned"]
    by_arm: dict[str, list] = {a: [] for a in arm_order}
    for arm, seed, fname, tag in records:
        p = SUMM / fname
        if not p.exists():
            print(f"  MISSING trajectory: {fname} ({arm} s{seed}) skipped")
            continue
        if tag not in fits:
            print(f"  MISSING fit row: {tag} ({arm} s{seed}) skipped")
            continue
        steps, I_obs, N, I0 = empirical_I(read_rows(p))
        f = fits[tag]
        I_fit = simulate_I(f["beta"], f["gamma"], N - I0, I0, int(steps[-1]))
        by_arm[arm].append({
            "seed": seed, "steps": steps, "I_obs": I_obs, "I_fit": I_fit,
            "beta": f["beta"], "gamma": f["gamma"], "r0": f["r0"],
        })

    fig, axes = plt.subplots(2, 3, figsize=(9.5, 5.6), sharex=True)
    axes = axes.ravel()
    for ax, arm in zip(axes, arm_order):
        hue = ARM_COLOR[arm]
        series = by_arm[arm]
        multiseed = len(series) > 1
        for s in series:
            a_pt = 0.45 if multiseed else 0.9
            a_ln = 0.5 if multiseed else 1.0
            ax.plot(s["steps"], s["I_obs"], marker="o", markersize=4.5,
                    linestyle="none", color=hue, alpha=a_pt, zorder=3,
                    markeredgecolor="#fcfcfb", markeredgewidth=0.5)
            ax.plot(s["steps"], s["I_fit"], color=hue, linewidth=1.8,
                    alpha=a_ln, zorder=2)
        # annotate fit params (seed-42 for multiseed, else the single seed)
        ref = next((s for s in series if s["seed"] == 42), series[0]) if series else None
        if ref is not None:
            g = ref["gamma"]
            r0 = ref["r0"]
            if np.isfinite(r0) and g > 0:
                txt = rf"$\beta$={ref['beta']:.3f}, $\gamma$={g:.3f}, $R_0$={r0:.2f}"
            else:
                txt = rf"$\beta$={ref['beta']:.3f}, $\gamma$=0 ($R_0$ undef.)"
            if multiseed:
                txt = "seed 42: " + txt
            ax.text(0.03, 0.97, txt, transform=ax.transAxes, va="top", ha="left",
                    fontsize=7.3, color=INK2)
        ax.set_title(ARM_LABEL[arm], color=hue, fontweight="bold")
        ax.set_xlim(0, 10.4)
        ax.set_xticks(range(0, 11, 2))
        ax.margins(y=0.12)
        for spine in ("top", "right"):
            ax.spines[spine].set_visible(False)

    # shared axis labels
    for ax in axes[3:]:
        ax.set_xlabel("Pipeline step", color=INK)
    for ax in (axes[0], axes[3]):
        ax.set_ylabel("Infected nodes I(t)", color=INK)

    # legend proxy (marks = empirical, line = fitted)
    from matplotlib.lines import Line2D
    proxies = [
        Line2D([0], [0], marker="o", linestyle="none", color=MUTED,
               markeredgecolor="#fcfcfb", markersize=6, label="empirical I(t)"),
        Line2D([0], [0], color=MUTED, linewidth=2, label="fitted SIR I(t)"),
    ]
    fig.legend(handles=proxies, loc="lower center", ncol=2, frameon=False,
               bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("Empirical vs fitted infected-node trajectories per arm",
                 fontsize=12.5, color=INK, y=1.0)
    fig.tight_layout(rect=(0, 0.03, 1, 0.99))
    savefig(fig, "fig_sir_fit_It")


# ===========================================================================
# FIGURE 3 - R0 per arm with R0 = 1 critical line (ch5 S5.5)
# ===========================================================================
def fig_r0_by_arm() -> None:
    print("Figure 3: R0 per arm")
    fits = load_fits()

    # mitigated R0 mean +/- SD across the 4 seeds (archived per-seed fits).
    mit_tags = ["mitigated", "mitigated_s43", "mitigated_s44", "mitigated_s45"]
    mit_r0 = [fits[t]["r0"] for t in mit_tags if t in fits and np.isfinite(fits[t]["r0"])]
    mit_mean = float(np.mean(mit_r0)) if mit_r0 else np.nan
    mit_sd = float(np.std(mit_r0, ddof=1)) if len(mit_r0) > 1 else 0.0

    # arm, R0 value, error (or None), defined?
    arms = [
        ("baseline",            None,      None,   False),  # gamma = 0
        ("ablation_floor",      None,      None,   False),  # gamma = 0
        ("ablation_validation", fits.get("ablation_validation", {}).get("r0"), None, True),
        ("mitigated",           mit_mean,  mit_sd, True),
        ("mitigated_tuned",     None,      None,   False),  # gamma = 0
        ("oracle",              fits.get("oracle", {}).get("r0"), None, True),
    ]

    fig, ax = plt.subplots(figsize=(7.4, 4.0))
    x = np.arange(len(arms))
    ymax = 0.0
    for i, (arm, val, err, defined) in enumerate(arms):
        hue = ARM_COLOR[arm]
        if defined and val is not None and np.isfinite(val):
            ax.bar(i, val, width=0.62, color=hue, edgecolor="#fcfcfb",
                   linewidth=0.8, zorder=3)
            if err:
                ax.errorbar(i, val, yerr=err, fmt="none", ecolor=INK2,
                            elinewidth=1.2, capsize=4, zorder=4)
            top = val + (err or 0)
            ymax = max(ymax, top)
            lbl = f"{val:.2f}"
            if err:
                lbl += f"\n$\\pm${err:.2f}"
            ax.annotate(lbl, xy=(i, top), xytext=(0, 4),
                        textcoords="offset points", ha="center", va="bottom",
                        fontsize=8.5, color=INK)
        else:
            # honest representation of the gamma=0 / undefined arms
            ax.annotate("undefined\n($\\gamma$=0)", xy=(i, 0), xytext=(0, 8),
                        textcoords="offset points", ha="center", va="bottom",
                        fontsize=8, color=MUTED, style="italic")

    # R0 = 1 critical line
    ax.axhline(1.0, color="#d03b3b", linestyle="--", linewidth=1.4, zorder=2)
    ax.annotate("$R_0=1$ (epidemic threshold)", xy=(0.05, 1.0),
                xytext=(0, 4), textcoords="offset points", ha="left", va="bottom",
                fontsize=9, color="#d03b3b", fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([ARM_LABEL[a] for a, *_ in arms], rotation=15, ha="right")
    ax.set_ylabel("Basic reproduction number $R_0$", color=INK)
    ax.set_ylim(0, ymax * 1.18 if ymax else 8)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.set_axisbelow(True)
    ax.grid(axis="x", visible=False)
    ax.set_title("Fitted $R_0$ per arm (SIR fit to reconstructed I/R)",
                 color=INK, fontsize=12)
    fig.tight_layout()
    savefig(fig, "fig_r0_by_arm")


def main() -> None:
    print(f"Reading archived CSVs from {SUMM}")
    print(f"Writing figures to {OUTDIR}\n")
    fig_baseline_trajectories()
    print()
    fig_sir_fit()
    print()
    fig_r0_by_arm()
    print("\nDone.")


if __name__ == "__main__":
    sys.exit(main())
