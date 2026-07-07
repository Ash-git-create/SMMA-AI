"""
Phase 3.5 — fit the discrete-time SIR model to observed contamination trajectories.

Reuses the exact difference equations in src/sir/sir_model.py (forward Euler,
same clamping behaviour) so the fitted curves are directly comparable to the
Phase-1 theoretical scenarios in scripts/plot_sir_curves.py.

WHY THE RAW CSV S/I/R COLUMNS ARE NOT USED DIRECTLY
-----------------------------------------------------
Every phase32/phase33 trajectory CSV already has columns literally named
S, I, R — but they are KG-size bookkeeping, not the epidemic compartments the
thesis's SIR model describes: I is 0 in every row of every run (contamination
is never labelled "currently infected, not yet reviewed" as a node state) and
R only tracks quarantine actions (= det_R_contam + det_R_clean, i.e. it also
counts false-positive quarantines of clean nodes as "recovered"). S is simply
the running total triplet count in the graph (it grows every step as new
triplets are extracted) and does not shrink as nodes get infected. So the raw
S/I/R columns cannot be dropped into the SIR difference equations as-is.

The actual epidemic signal lives in the ground-truth columns instead:
  gt_total(t)      = cumulative EVER-infected count (seed cases + everything
                      propagated from them so far, summed over the three
                      error types: gt_seed_X + gt_prop_X). This is monotone
                      non-decreasing by construction (propagation never
                      "un-happens").
  det_R_contam(t)  = cumulative count of TRUE-POSITIVE quarantines, i.e.
                      actually-contaminated nodes the ValidationAgent caught
                      and removed from circulation. This excludes
                      det_R_clean (false-positive quarantines of clean
                      nodes), which is a real cost the thesis discusses
                      elsewhere but is not part of the epidemic's I/R
                      bookkeeping.

From these we reconstruct proper SIR compartments:
  I(t) = gt_total(t) - det_R_contam(t)   (currently infected, not yet caught)
  R(t) = det_R_contam(t)                 (caught and removed from spread)
  I0   = gt_total(0)                     (the seeded "patient zero" cases)
  N    = S(0) from the raw CSV           (total KG triplet count at the start
                                           of the run — the population the
                                           outbreak is embedded in, matching
                                           the S0~50000 scale used in
                                           scripts/plot_sir_curves.py)
  S(t) = N - I(t) - R(t)

For the baseline and ablation_floor arms there is no ValidationAgent audit
pass (config audits_per_step == 0, confirmed from det_R_contam being 0 at
every step of those trajectories), so gamma is fixed at 0 rather than fit —
fitting a recovery rate against a curve that never recovers is both
meaningless and, if attempted via beta/gamma, a division-by-zero when R0 is
then derived.

FITTING METHOD
---------------
scipy.optimize.least_squares, forward-simulating SIRModel(beta, gamma).run(...)
exactly (so the fit inherits the model's own infection/recovery clamps) and
minimizing the residual between simulated and observed I(t) (plus R(t) when
gamma is fit). This was chosen over a closed-form estimator because the
model's ΔI equation is nonlinear in S/N and the trajectories are short
(11 points): a direct nonlinear least-squares fit against the same simulator
used elsewhere in the codebase is simpler to justify than deriving a separate
linearised estimator, and guarantees the fitted (beta, gamma) are literally
what src/sir/sir_model.py would reproduce if run forward.
  - Runs with no validation (gamma fixed at 0): 1-parameter fit (beta only).
  - Runs with validation (gamma free): 2-parameter joint fit (beta, gamma),
    residuals over both I(t) and R(t) so gamma is informed by the actual
    quarantine curve, not inferred solely from its effect on I(t).

R0 / EFFECTIVE REPRODUCTION
-----------------------------
R0 = beta / gamma is only reported where gamma > 0 (ablation_validation,
mitigated). For gamma == 0 runs (baseline, ablation_floor) R0 is reported as
NA and instead we report:
  - effective_reproduction: the per-step force of infection on the fitted
    curve, mean_t [ beta * S(t)/N ] — a finite, well-defined quantity even
    when gamma = 0.  Note S/N stays >= 0.999 throughout every run here (the
    outbreak is a few dozen nodes inside a ~50,000-node KG), so
    effective_reproduction ~= beta almost exactly for every arm — the
    classic SIR susceptible-depletion regime never kicks in at this scale.
  - empirical_reproduction_per_seed: (propagated at final step) / (seeded at
    step 0), a purely empirical, model-free number already used in
    results/summaries/phase32_arm_comparison.csv, reported here for every
    run as a cross-check on the fit.

Usage (from project root, with venv active):
    python scripts/fit_sir.py
    python scripts/fit_sir.py --trajectories results/summaries/phase32_baseline_trajectory.csv
    python scripts/fit_sir.py --output results/summaries/phase35_sir_fit.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from loguru import logger
from scipy.optimize import least_squares

from src.sir.sir_model import SIRModel
from src.sir.r0_calculator import R0Calculator

logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

SUMMARIES_DIR = ROOT / "results" / "summaries"

ERROR_TYPES = ("entity_disambiguation", "qualifier_loss", "relation_strengthening")

# The seven runs the thesis's Phase 3 comparison is built on.
DEFAULT_TRAJECTORIES = [
    "phase32_baseline_trajectory.csv",
    "phase32_ablation_floor_trajectory.csv",
    "phase32_ablation_validation_trajectory.csv",
    "phase32_mitigated_trajectory.csv",
    "phase33_baseline_s43_trajectory.csv",
    "phase33_baseline_s44_trajectory.csv",
    "phase33_baseline_s45_trajectory.csv",
]

BASELINE_ARM = "baseline"


def _manifest_path_for(csv_path: Path) -> Path:
    return Path(str(csv_path).replace("_trajectory.csv", "_manifest.json"))


def _arm_from_name(name: str) -> str:
    if "ablation_floor" in name:
        return "ablation_floor"
    if "ablation_validation" in name:
        return "ablation_validation"
    if "mitigated" in name:
        return "mitigated"
    if "baseline" in name:
        return "baseline"
    return "unknown"


def load_run(csv_path: Path) -> dict:
    """Load one trajectory CSV + its manifest, return raw rows and metadata."""
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise ValueError(f"{csv_path} has no rows")

    manifest_path = _manifest_path_for(csv_path)
    seed = None
    tag = csv_path.stem.replace("_trajectory", "")
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
        seed = manifest["config"].get("random_seed")
        tag = manifest["config"].get("tag", tag)
    else:
        logger.warning(f"No manifest found for {csv_path.name} (expected {manifest_path.name})")

    arm = _arm_from_name(csv_path.stem)
    return {"csv_path": csv_path, "rows": rows, "seed": seed, "tag": tag, "arm": arm}


def build_epidemic_series(rows: list[dict]) -> dict:
    """
    Reconstruct true SIR compartments from the ground-truth columns.
    See module docstring for why the raw S/I/R columns are not used directly.
    """
    steps = len(rows) - 1
    gt_total = np.array([float(r["gt_total"]) for r in rows])
    det_R_contam = np.array([float(r["det_R_contam"]) for r in rows])

    I_obs = gt_total - det_R_contam
    R_obs = det_R_contam
    N = float(rows[0]["S"])
    I0 = float(I_obs[0])
    S0 = N - I0  # R(0) is always 0 in every run here

    fit_gamma = bool(R_obs[-1] > 0)

    seeded_total = float(
        sum(float(rows[0].get(f"gt_seed_{t}", 0.0)) for t in ERROR_TYPES)
    )
    propagated_final = float(gt_total[-1] - seeded_total)

    return {
        "steps": steps,
        "N": N,
        "I0": I0,
        "S0": S0,
        "I_obs": I_obs,
        "R_obs": R_obs,
        "fit_gamma": fit_gamma,
        "seeded_total": seeded_total,
        "propagated_final": propagated_final,
    }


def _simulate(beta: float, gamma: float, S0: float, I0: float, steps: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    model = SIRModel(beta=beta, gamma=gamma)
    traj = model.run(S0=S0, I0=I0, R0=0, steps=steps)
    S = np.array([r["S"] for r in traj])
    I = np.array([r["I"] for r in traj])
    R = np.array([r["R"] for r in traj])
    return S, I, R


def fit_run(series: dict) -> dict:
    S0, I0, steps = series["S0"], series["I0"], series["steps"]
    I_obs, R_obs = series["I_obs"], series["R_obs"]
    fit_gamma = series["fit_gamma"]

    if fit_gamma:
        def residuals(params):
            beta, gamma = params
            _, I_sim, R_sim = _simulate(beta, gamma, S0, I0, steps)
            return np.concatenate([I_sim - I_obs, R_sim - R_obs])

        result = least_squares(
            residuals, x0=[0.1, 0.05], bounds=([0.0, 0.0], [5.0, 1.0])
        )
        beta, gamma = result.x
    else:
        def residuals(params):
            (beta,) = params
            _, I_sim, _ = _simulate(beta, 0.0, S0, I0, steps)
            return I_sim - I_obs

        result = least_squares(residuals, x0=[0.1], bounds=([0.0], [5.0]))
        beta = result.x[0]
        gamma = 0.0

    S_sim, I_sim, R_sim = _simulate(beta, gamma, S0, I0, steps)
    rmse_I = float(np.sqrt(np.mean((I_sim - I_obs) ** 2)))
    rmse_R = float(np.sqrt(np.mean((R_sim - R_obs) ** 2))) if fit_gamma else float("nan")
    if fit_gamma:
        rmse_total = float(np.sqrt(np.mean(np.concatenate([I_sim - I_obs, R_sim - R_obs]) ** 2)))
    else:
        rmse_total = rmse_I

    if gamma > 0:
        r0 = R0Calculator.from_beta_gamma(beta=beta, gamma=gamma).r0
    else:
        r0 = None  # NA — undefined without a recovery process

    N = series["N"]
    effective_reproduction = float(np.mean(beta * S_sim / N))

    empirical_reproduction = (
        series["propagated_final"] / series["seeded_total"]
        if series["seeded_total"] > 0
        else float("nan")
    )

    return {
        "beta": beta,
        "gamma": gamma,
        "r0": r0,
        "effective_reproduction": effective_reproduction,
        "empirical_reproduction_per_seed": empirical_reproduction,
        "fit_rmse_I": rmse_I,
        "fit_rmse_R": rmse_R,
        "fit_rmse_total": rmse_total,
        "I_sim_final": float(I_sim[-1]),
        "I_obs_final": float(I_obs[-1]),
    }


def resolve_trajectories(patterns: list[str] | None) -> list[Path]:
    if not patterns:
        paths = [SUMMARIES_DIR / name for name in DEFAULT_TRAJECTORIES]
        missing = [p for p in paths if not p.exists()]
        for m in missing:
            logger.warning(f"Default trajectory not found, skipping: {m}")
        return [p for p in paths if p.exists()]

    paths: list[Path] = []
    for pattern in patterns:
        p = Path(pattern)
        if p.is_absolute() or p.exists():
            paths.append(p)
        else:
            matches = sorted(SUMMARIES_DIR.glob(pattern))
            if not matches:
                matches = sorted(ROOT.glob(pattern))
            paths.extend(matches)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Fit discrete-time SIR parameters to observed contamination trajectories.")
    parser.add_argument(
        "--trajectories", nargs="*", default=None,
        help="Trajectory CSV paths or glob patterns (default: the 4 phase32 arms + 3 phase33 baseline seeds).",
    )
    parser.add_argument(
        "--output", type=str, default=str(SUMMARIES_DIR / "phase35_sir_fit.csv"),
        help="Output CSV path.",
    )
    args = parser.parse_args()

    traj_paths = resolve_trajectories(args.trajectories)
    if not traj_paths:
        logger.error("No trajectory files resolved. Nothing to fit.")
        sys.exit(1)

    logger.info(f"Fitting SIR parameters for {len(traj_paths)} run(s)")

    records = []
    for path in traj_paths:
        run = load_run(path)
        series = build_epidemic_series(run["rows"])
        fit = fit_run(series)

        record = {
            "run_tag": run["tag"],
            "seed": run["seed"],
            "arm": run["arm"],
            "N": series["N"],
            "I0": series["I0"],
            "steps": series["steps"],
            "beta": fit["beta"],
            "gamma": fit["gamma"],
            "r0": fit["r0"] if fit["r0"] is not None else "NA",
            "effective_reproduction": fit["effective_reproduction"],
            "empirical_reproduction_per_seed": fit["empirical_reproduction_per_seed"],
            "fit_rmse_I": fit["fit_rmse_I"],
            "fit_rmse_R": fit["fit_rmse_R"],
            "fit_rmse_total": fit["fit_rmse_total"],
        }
        records.append(record)
        logger.info(
            f"{record['run_tag']:22s} seed={record['seed']!s:4s} "
            f"beta={fit['beta']:.4f} gamma={fit['gamma']:.4f} "
            f"r0={record['r0']!s:8s} rmse={fit['fit_rmse_total']:.3f}"
        )

    df = pd.DataFrame.from_records(records)

    # Baseline mean +/- sd across the 4 baseline seeds (42, 43, 44, 45).
    baseline_mask = df["arm"] == BASELINE_ARM
    if baseline_mask.sum() > 0:
        numeric_cols = ["N", "I0", "beta", "gamma", "effective_reproduction",
                         "empirical_reproduction_per_seed", "fit_rmse_I", "fit_rmse_total"]
        base_df = df.loc[baseline_mask, numeric_cols]
        mean_row = {"run_tag": "baseline_mean", "seed": "NA", "arm": BASELINE_ARM,
                    "steps": df.loc[baseline_mask, "steps"].iloc[0], "r0": "NA", "fit_rmse_R": "NA"}
        sd_row = {"run_tag": "baseline_sd", "seed": "NA", "arm": BASELINE_ARM,
                  "steps": df.loc[baseline_mask, "steps"].iloc[0], "r0": "NA", "fit_rmse_R": "NA"}
        mean_row.update(base_df.mean().to_dict())
        sd_row.update(base_df.std(ddof=1).to_dict())
        df = pd.concat([df, pd.DataFrame([mean_row, sd_row])], ignore_index=True)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    logger.info(f"Wrote {output_path}")

    with pd.option_context("display.max_columns", None, "display.width", 200, "display.float_format", "{:.4f}".format):
        print()
        print(df.to_string(index=False))


if __name__ == "__main__":
    main()
