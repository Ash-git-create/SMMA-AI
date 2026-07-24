"""
Phase 4.1 -- formal statistical backbone for the thesis's cross-arm claims.

Every headline comparison used loosely in ch3/ch5 prose so far (mitigated vs
oracle-noisy R0, baseline vs mitigated propagation/exposure, the "mitigated
destabilises transmission" variance claim, baseline-vs-mitigated detection
AUROC) gets a formal test here: Welch's t (two-sided, unequal variance),
Mann-Whitney U (two-sided, distribution-free cross-check), and a 10,000-
resample bootstrap CI on the mean difference. Per CLAUDE.md's "Analysis &
Write-up Discipline", every number is read out of an archived CSV in
results/summaries/ -- nothing here is hand-typed -- and every n=4 comparison
is reported as "suggestive" unless a test says otherwise.

INPUT FILES (results/summaries/, all pre-existing, none modified)
-------------------------------------------------------------------
SIR fits:
  phase35_sir_fit.csv                      baseline seeds 42/43/44/45 (r0 NA,
                                            gamma=0 by construction) + the
                                            *mitigated seed-42* row (the 4th
                                            mitigated seed lives here, not in
                                            phase37).
  phase37_sir_fit_mitigated_seeds.csv      mitigated seeds 43/44/45.
  phase38_sir_fit_oracle.csv               perfect-oracle seed 42 (n=1).
  phase40_sir_fit_oracle_noisy_p{10,50,75}[_s{43,44,45}].csv
                                            noisy-oracle seeds 42/43/44/45 at
                                            three FN/FP noise points. p25 has
                                            only seed 42 (n=1, reported
                                            descriptively, not in a named
                                            contrast).

Trajectories (final-step, step==10, row):
  phase32_baseline_trajectory.csv + phase33_baseline_s{43,44,45}_trajectory.csv
  phase32_mitigated_trajectory.csv + phase37_mitigated_s{43,44,45}_trajectory.csv
  phase40_oracle_noisy_p{10,50,75}[_s{43,44,45}]_trajectory.csv, p25 (n=1)

KNOWN CONSTRUCTION-IDENTICAL DUPLICATE PAIRS (thesis_log 2026-07-24)
-----------------------------------------------------------------------
phase40_sir_fit_oracle_noisy_p50_s44.csv is numerically identical to
phase40_sir_fit_oracle_noisy_p10_s44.csv, and p50_s45 is numerically
identical to p75_s45. This is a documented metric-construction effect, not a
data error -- each arm keeps its own value (no de-duplication across arms),
but any contrast touching p10/p50/p75 carries a test_note flag so the CSV is
self-documenting.

OUTPUT
------
results/summaries/phase41_stats_tests.csv -- one row per contrast/summary:
  contrast, group_a, group_b, n_a, n_b, mean_a, mean_b, sd_a, sd_b,
  welch_t, welch_p, mwu_u, mwu_p, boot_ci_lo, boot_ci_hi, test_note
Descriptive rows (per-arm summaries, per-run quarantine precision) leave the
test columns NA and say "descriptive" in test_note -- no significance claim
is attached to them.

Usage:
    venv\\Scripts\\python.exe scripts\\stats_tests.py
"""

from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
from scipy import stats

SUMMARIES_DIR = ROOT / "results" / "summaries"
OUTPUT_PATH = SUMMARIES_DIR / "phase41_stats_tests.csv"

N_BOOT = 10_000
BOOT_SEED = 42

ERROR_TYPES = ("entity_disambiguation", "qualifier_loss", "relation_strengthening")

DUP_NOTE = {
    "oracle_noisy_p10": (
        "construction-identical dup: this arm's s44 value == oracle_noisy_p50 s44 "
        "(thesis_log 2026-07-24, metric-construction effect, not deduplicated)"
    ),
    "oracle_noisy_p50": (
        "construction-identical dups: this arm's s44 value == oracle_noisy_p10 s44, "
        "and this arm's s45 value == oracle_noisy_p75 s45 "
        "(thesis_log 2026-07-24, metric-construction effect, not deduplicated)"
    ),
    "oracle_noisy_p75": (
        "construction-identical dup: this arm's s45 value == oracle_noisy_p50 s45 "
        "(thesis_log 2026-07-24, metric-construction effect, not deduplicated)"
    ),
}


# --------------------------------------------------------------------------
# Loaders -- every number comes from a file, nothing hand-typed.
# --------------------------------------------------------------------------

def _fit_rows(path: str, run_tags: list[str] | None = None) -> pd.DataFrame:
    df = pd.read_csv(SUMMARIES_DIR / path)
    if run_tags is not None:
        df = df[df["run_tag"].isin(run_tags)].copy()
    df["r0"] = pd.to_numeric(df["r0"], errors="coerce")
    df["beta"] = pd.to_numeric(df["beta"], errors="coerce")
    df["gamma"] = pd.to_numeric(df["gamma"], errors="coerce")
    return df.reset_index(drop=True)


def _traj_final(path: str) -> pd.Series:
    df = pd.read_csv(SUMMARIES_DIR / path)
    row = df[df["step"] == df["step"].max()].iloc[0]
    propagated = sum(float(row[f"gt_prop_{t}"]) for t in ERROR_TYPES)
    return pd.Series({
        "cum_exposed": float(row["cum_exposed"]),
        "propagated": propagated,
        "det_R_contam": float(row["det_R_contam"]),
        "det_R_clean": float(row["det_R_clean"]),
        "detection_auroc": float(row["detection_auroc"]) if pd.notna(row.get("detection_auroc")) else np.nan,
    })


# Fit groups (R0 / beta), n=4 each unless noted.
BASELINE_FIT = _fit_rows("phase35_sir_fit.csv", ["baseline", "baseline_s43", "baseline_s44", "baseline_s45"])
MITIGATED_FIT = pd.concat([
    _fit_rows("phase35_sir_fit.csv", ["mitigated"]),
    _fit_rows("phase37_sir_fit_mitigated_seeds.csv"),
], ignore_index=True)
ORACLE_PERFECT_FIT = _fit_rows("phase38_sir_fit_oracle.csv")  # n=1
ORACLE_NOISY_P10_FIT = pd.concat([
    _fit_rows("phase40_sir_fit_oracle_noisy_p10.csv"),
    _fit_rows("phase40_sir_fit_oracle_noisy_p10_s43.csv"),
    _fit_rows("phase40_sir_fit_oracle_noisy_p10_s44.csv"),
    _fit_rows("phase40_sir_fit_oracle_noisy_p10_s45.csv"),
], ignore_index=True)
ORACLE_NOISY_P50_FIT = pd.concat([
    _fit_rows("phase40_sir_fit_oracle_noisy_p50.csv"),
    _fit_rows("phase40_sir_fit_oracle_noisy_p50_s43.csv"),
    _fit_rows("phase40_sir_fit_oracle_noisy_p50_s44.csv"),
    _fit_rows("phase40_sir_fit_oracle_noisy_p50_s45.csv"),
], ignore_index=True)
ORACLE_NOISY_P75_FIT = pd.concat([
    _fit_rows("phase40_sir_fit_oracle_noisy_p75.csv"),
    _fit_rows("phase40_sir_fit_oracle_noisy_p75_s43.csv"),
    _fit_rows("phase40_sir_fit_oracle_noisy_p75_s44.csv"),
    _fit_rows("phase40_sir_fit_oracle_noisy_p75_s45.csv"),
], ignore_index=True)
ORACLE_NOISY_P25_FIT = _fit_rows("phase40_sir_fit_oracle_noisy_p25.csv")  # n=1, bonus

# Trajectory (final-step) groups, n=4 each unless noted.
BASELINE_TRAJ = pd.DataFrame([
    _traj_final("phase32_baseline_trajectory.csv"),
    _traj_final("phase33_baseline_s43_trajectory.csv"),
    _traj_final("phase33_baseline_s44_trajectory.csv"),
    _traj_final("phase33_baseline_s45_trajectory.csv"),
]).reset_index(drop=True)
MITIGATED_TRAJ = pd.DataFrame([
    _traj_final("phase32_mitigated_trajectory.csv"),
    _traj_final("phase37_mitigated_s43_trajectory.csv"),
    _traj_final("phase37_mitigated_s44_trajectory.csv"),
    _traj_final("phase37_mitigated_s45_trajectory.csv"),
]).reset_index(drop=True)
ORACLE_NOISY_P10_TRAJ = pd.DataFrame([
    _traj_final("phase40_oracle_noisy_p10_trajectory.csv"),
    _traj_final("phase40_oracle_noisy_p10_s43_trajectory.csv"),
    _traj_final("phase40_oracle_noisy_p10_s44_trajectory.csv"),
    _traj_final("phase40_oracle_noisy_p10_s45_trajectory.csv"),
]).reset_index(drop=True)

# Per-run quarantine precision (item 8) needs every phase40 trajectory file,
# individually, including p25 (n=1, no 4-seed group).
QUARANTINE_RUNS = {
    "oracle_noisy_p10": "phase40_oracle_noisy_p10_trajectory.csv",
    "oracle_noisy_p10_s43": "phase40_oracle_noisy_p10_s43_trajectory.csv",
    "oracle_noisy_p10_s44": "phase40_oracle_noisy_p10_s44_trajectory.csv",
    "oracle_noisy_p10_s45": "phase40_oracle_noisy_p10_s45_trajectory.csv",
    "oracle_noisy_p25": "phase40_oracle_noisy_p25_trajectory.csv",
    "oracle_noisy_p50": "phase40_oracle_noisy_p50_trajectory.csv",
    "oracle_noisy_p50_s43": "phase40_oracle_noisy_p50_s43_trajectory.csv",
    "oracle_noisy_p50_s44": "phase40_oracle_noisy_p50_s44_trajectory.csv",
    "oracle_noisy_p50_s45": "phase40_oracle_noisy_p50_s45_trajectory.csv",
    "oracle_noisy_p75": "phase40_oracle_noisy_p75_trajectory.csv",
    "oracle_noisy_p75_s43": "phase40_oracle_noisy_p75_s43_trajectory.csv",
    "oracle_noisy_p75_s44": "phase40_oracle_noisy_p75_s44_trajectory.csv",
    "oracle_noisy_p75_s45": "phase40_oracle_noisy_p75_s45_trajectory.csv",
}


# --------------------------------------------------------------------------
# Stats helpers
# --------------------------------------------------------------------------

def bootstrap_mean_diff_ci(a: np.ndarray, b: np.ndarray, n_boot: int = N_BOOT, seed: int = BOOT_SEED) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    na, nb = len(a), len(b)
    idx_a = rng.integers(0, na, size=(n_boot, na))
    idx_b = rng.integers(0, nb, size=(n_boot, nb))
    diffs = a[idx_a].mean(axis=1) - b[idx_b].mean(axis=1)
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return float(lo), float(hi)


def bootstrap_var_ratio_ci(a: np.ndarray, b: np.ndarray, n_boot: int = N_BOOT, seed: int = BOOT_SEED) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    na, nb = len(a), len(b)
    idx_a = rng.integers(0, na, size=(n_boot, na))
    idx_b = rng.integers(0, nb, size=(n_boot, nb))
    var_a = a[idx_a].var(axis=1, ddof=1)
    var_b = b[idx_b].var(axis=1, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = var_a / var_b
    ratio = ratio[np.isfinite(ratio)]
    lo, hi = np.percentile(ratio, [2.5, 97.5])
    return float(lo), float(hi)


def contrast_row(contrast: str, name_a: str, a, name_b: str, b, note: str = "") -> dict:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    t_stat, t_p = stats.ttest_ind(a, b, equal_var=False)
    u_stat, u_p = stats.mannwhitneyu(a, b, alternative="two-sided")
    ci_lo, ci_hi = bootstrap_mean_diff_ci(a, b)
    return {
        "contrast": contrast,
        "group_a": name_a,
        "group_b": name_b,
        "n_a": len(a),
        "n_b": len(b),
        "mean_a": float(np.mean(a)),
        "mean_b": float(np.mean(b)),
        "sd_a": float(np.std(a, ddof=1)) if len(a) > 1 else np.nan,
        "sd_b": float(np.std(b, ddof=1)) if len(b) > 1 else np.nan,
        "welch_t": float(t_stat),
        "welch_p": float(t_p),
        "mwu_u": float(u_stat),
        "mwu_p": float(u_p),
        "boot_ci_lo": ci_lo,
        "boot_ci_hi": ci_hi,
        "test_note": note,
    }


def descriptive_row(contrast: str, name_a: str, a, note: str = "") -> dict:
    a = np.asarray(a, dtype=float)
    valid = a[~np.isnan(a)]
    return {
        "contrast": contrast,
        "group_a": name_a,
        "group_b": np.nan,
        "n_a": len(a),
        "n_b": np.nan,
        "mean_a": float(np.mean(valid)) if len(valid) else np.nan,
        "mean_b": np.nan,
        "sd_a": float(np.std(valid, ddof=1)) if len(valid) > 1 else np.nan,
        "sd_b": np.nan,
        "welch_t": np.nan,
        "welch_p": np.nan,
        "mwu_u": np.nan,
        "mwu_p": np.nan,
        "boot_ci_lo": np.nan,
        "boot_ci_hi": np.nan,
        "test_note": "descriptive (no significance test); " + note,
    }


def dup_note_for(*arm_names: str) -> str:
    notes = [DUP_NOTE[a] for a in arm_names if a in DUP_NOTE]
    return " | ".join(notes)


def main() -> None:
    rows: list[dict] = []

    mit_r0 = MITIGATED_FIT["r0"].to_numpy()
    p10_r0 = ORACLE_NOISY_P10_FIT["r0"].to_numpy()
    p50_r0 = ORACLE_NOISY_P50_FIT["r0"].to_numpy()
    p75_r0 = ORACLE_NOISY_P75_FIT["r0"].to_numpy()

    # --- 1. R0: mitigated vs oracle_noisy_p10 --------------------------------
    rows.append(contrast_row(
        "r0_mitigated_vs_oracle_noisy_p10", "mitigated", mit_r0, "oracle_noisy_p10", p10_r0,
        note="mitigated seeds: seed42 from phase35_sir_fit.csv (run_tag=mitigated), "
             "seeds43-45 from phase37_sir_fit_mitigated_seeds.csv. " + dup_note_for("oracle_noisy_p10"),
    ))

    # --- 2. R0: mitigated vs oracle_noisy_p75, and vs p50 ---------------------
    rows.append(contrast_row(
        "r0_mitigated_vs_oracle_noisy_p75", "mitigated", mit_r0, "oracle_noisy_p75", p75_r0,
        note=dup_note_for("oracle_noisy_p75"),
    ))
    rows.append(contrast_row(
        "r0_mitigated_vs_oracle_noisy_p50", "mitigated", mit_r0, "oracle_noisy_p50", p50_r0,
        note=dup_note_for("oracle_noisy_p50"),
    ))

    # --- 3. R0 among the three n=4 noisy points (expected null) --------------
    rows.append(contrast_row(
        "r0_noisy_p75_vs_p50", "oracle_noisy_p75", p75_r0, "oracle_noisy_p50", p50_r0,
        note="expected null (clustering claim). " + dup_note_for("oracle_noisy_p75", "oracle_noisy_p50"),
    ))
    rows.append(contrast_row(
        "r0_noisy_p75_vs_p10", "oracle_noisy_p75", p75_r0, "oracle_noisy_p10", p10_r0,
        note="expected null (clustering claim). " + dup_note_for("oracle_noisy_p75", "oracle_noisy_p10"),
    ))
    rows.append(contrast_row(
        "r0_noisy_p50_vs_p10", "oracle_noisy_p50", p50_r0, "oracle_noisy_p10", p10_r0,
        note="expected null (clustering claim). " + dup_note_for("oracle_noisy_p50", "oracle_noisy_p10"),
    ))

    # --- 4. Final propagated / cum_exposed: baseline vs p10, baseline vs mitigated
    base_prop = BASELINE_TRAJ["propagated"].to_numpy()
    base_exp = BASELINE_TRAJ["cum_exposed"].to_numpy()
    mit_prop = MITIGATED_TRAJ["propagated"].to_numpy()
    mit_exp = MITIGATED_TRAJ["cum_exposed"].to_numpy()
    p10_prop = ORACLE_NOISY_P10_TRAJ["propagated"].to_numpy()
    p10_exp = ORACLE_NOISY_P10_TRAJ["cum_exposed"].to_numpy()

    rows.append(contrast_row(
        "final_propagated_baseline_vs_oracle_noisy_p10", "baseline", base_prop, "oracle_noisy_p10", p10_prop,
        note="propagated = gt_prop_entity_disambiguation + gt_prop_qualifier_loss + "
             "gt_prop_relation_strengthening at final step (step 10) of each trajectory CSV.",
    ))
    rows.append(contrast_row(
        "final_propagated_baseline_vs_mitigated", "baseline", base_prop, "mitigated", mit_prop,
        note="propagated = sum of gt_prop_* at final step. Cf. thesis_log 2026-07-12: "
             "full-Trio seed-42 harm was retracted as a point estimate in the 4-seed replication.",
    ))
    rows.append(contrast_row(
        "final_cum_exposed_baseline_vs_oracle_noisy_p10", "baseline", base_exp, "oracle_noisy_p10", p10_exp,
        note="cum_exposed at final step (step 10) of each trajectory CSV.",
    ))
    rows.append(contrast_row(
        "final_cum_exposed_baseline_vs_mitigated", "baseline", base_exp, "mitigated", mit_exp,
        note="cum_exposed at final step (step 10) of each trajectory CSV.",
    ))

    # --- 5. Variance ratio: mitigated beta vs baseline beta -------------------
    mit_beta = MITIGATED_FIT["beta"].to_numpy()
    base_beta = BASELINE_FIT["beta"].to_numpy()
    lev_stat, lev_p = stats.levene(mit_beta, base_beta)
    var_ratio_ci = bootstrap_var_ratio_ci(mit_beta, base_beta)
    var_mit = float(np.var(mit_beta, ddof=1))
    var_base = float(np.var(base_beta, ddof=1))
    f_stat = var_mit / var_base
    dof_a, dof_b = len(mit_beta) - 1, len(base_beta) - 1
    f_p = 2 * min(stats.f.cdf(f_stat, dof_a, dof_b), stats.f.sf(f_stat, dof_a, dof_b))
    rows.append({
        "contrast": "beta_variance_levene", "group_a": "mitigated", "group_b": "baseline",
        "n_a": len(mit_beta), "n_b": len(base_beta),
        "mean_a": float(np.mean(mit_beta)), "mean_b": float(np.mean(base_beta)),
        "sd_a": float(np.std(mit_beta, ddof=1)), "sd_b": float(np.std(base_beta, ddof=1)),
        "welch_t": float(lev_stat), "welch_p": float(lev_p),
        "mwu_u": np.nan, "mwu_p": np.nan,
        "boot_ci_lo": var_ratio_ci[0], "boot_ci_hi": var_ratio_ci[1],
        "test_note": (
            "Levene's test for equal variances on beta (not a mean-difference test): "
            "welch_t/welch_p columns hold the Levene W statistic and p-value. "
            "boot_ci is the 10k-resample percentile CI on the variance ratio "
            "var(mitigated_beta)/var(baseline_beta), seed=42. n=4 per group -- "
            "per CLAUDE.md discipline, treat as suggestive only, not significant, "
            "unless the test itself says otherwise. Backs (or refutes) the ch5 "
            "'mitigation destabilises transmission' variance claim."
        ),
    })
    rows.append({
        "contrast": "beta_variance_fratio", "group_a": "mitigated", "group_b": "baseline",
        "n_a": len(mit_beta), "n_b": len(base_beta),
        "mean_a": float(np.mean(mit_beta)), "mean_b": float(np.mean(base_beta)),
        "sd_a": float(np.std(mit_beta, ddof=1)), "sd_b": float(np.std(base_beta, ddof=1)),
        "welch_t": float(f_stat), "welch_p": float(f_p),
        "mwu_u": np.nan, "mwu_p": np.nan,
        "boot_ci_lo": var_ratio_ci[0], "boot_ci_hi": var_ratio_ci[1],
        "test_note": (
            "F-ratio test on beta variances: welch_t holds F = var(mitigated_beta)/var(baseline_beta) "
            "(dof=3,3), welch_p the two-sided F-test p-value. CAVEAT: F-ratio test is fragile and "
            "highly sensitive to non-normality at n=4 per group -- report only alongside Levene's "
            "(row above) and treat as suggestive, per CLAUDE.md 'Analysis & Write-up Discipline' "
            "rule 4 (variance claims at n=4 are 'suggestive' unless the test says otherwise)."
        ),
    })

    # --- 6. Detection AUROC: baseline vs mitigated seeds -----------------------
    base_auroc = BASELINE_TRAJ["detection_auroc"].to_numpy()
    mit_auroc = MITIGATED_TRAJ["detection_auroc"].to_numpy()
    rows.append(contrast_row(
        "detection_auroc_baseline_vs_mitigated", "baseline", base_auroc, "mitigated", mit_auroc,
        note="detection_auroc at final step (step 10) of each trajectory CSV. Cf. thesis_log "
             "2026-07-12: full-Trio pooled quarantine precision 5.9%, AUROC 0.899->0.859 (p=0.004) "
             "was the only significant effect found there (confidence-laundering finding).",
    ))

    # --- 7. Per-arm summary rows (descriptive) ---------------------------------
    def r0_summary_note(r0_vals: np.ndarray) -> str:
        valid = r0_vals[~np.isnan(r0_vals)]
        if len(valid) == 0:
            return "min=NA, max=NA, n_r0_gt_1=NA"
        return f"min={valid.min():.4f}, max={valid.max():.4f}, n_r0_gt_1={int(np.sum(valid > 1))}/{len(valid)}"

    rows.append(descriptive_row(
        "arm_summary_baseline_beta", "baseline", base_beta,
        note="baseline gamma=0 by construction (no ValidationAgent audit pass) so r0 is undefined "
             "(NA) for every baseline seed; reporting beta stats instead. "
             + r0_summary_note(base_beta).replace("r0", "beta"),
    ))
    rows.append(descriptive_row(
        "arm_summary_mitigated_r0", "mitigated", mit_r0,
        note=r0_summary_note(mit_r0),
    ))
    rows.append(descriptive_row(
        "arm_summary_oracle_perfect_r0", "oracle_perfect", ORACLE_PERFECT_FIT["r0"].to_numpy(),
        note="n=1 (seed 42 only, phase38_sir_fit_oracle.csv). oracle_s43/44/45 fit CSVs not present "
             "in results/summaries/ at run time (were reported as landing after this run). "
             + r0_summary_note(ORACLE_PERFECT_FIT["r0"].to_numpy()),
    ))
    rows.append(descriptive_row(
        "arm_summary_oracle_noisy_p10_r0", "oracle_noisy_p10", p10_r0,
        note=r0_summary_note(p10_r0) + ". " + dup_note_for("oracle_noisy_p10"),
    ))
    rows.append(descriptive_row(
        "arm_summary_oracle_noisy_p50_r0", "oracle_noisy_p50", p50_r0,
        note=r0_summary_note(p50_r0) + ". " + dup_note_for("oracle_noisy_p50"),
    ))
    rows.append(descriptive_row(
        "arm_summary_oracle_noisy_p75_r0", "oracle_noisy_p75", p75_r0,
        note=r0_summary_note(p75_r0) + ". " + dup_note_for("oracle_noisy_p75"),
    ))
    rows.append(descriptive_row(
        "arm_summary_oracle_noisy_p25_r0", "oracle_noisy_p25", ORACLE_NOISY_P25_FIT["r0"].to_numpy(),
        note="n=1 (seed 42 only, phase40_sir_fit_oracle_noisy_p25.csv; no companion seeds landed). "
             + r0_summary_note(ORACLE_NOISY_P25_FIT["r0"].to_numpy()),
    ))

    # --- 8. Realized quarantine precision per noisy-oracle run (descriptive) ---
    for run_tag, fname in QUARANTINE_RUNS.items():
        final = _traj_final(fname)
        contam, clean = final["det_R_contam"], final["det_R_clean"]
        denom = contam + clean
        precision = contam / denom if denom > 0 else np.nan
        rows.append({
            "contrast": "quarantine_precision", "group_a": run_tag, "group_b": np.nan,
            "n_a": 1, "n_b": np.nan,
            "mean_a": precision, "mean_b": np.nan,
            "sd_a": np.nan, "sd_b": np.nan,
            "welch_t": np.nan, "welch_p": np.nan, "mwu_u": np.nan, "mwu_p": np.nan,
            "boot_ci_lo": np.nan, "boot_ci_hi": np.nan,
            "test_note": (
                f"descriptive (no significance test); det_R_contam={contam:.0f}, "
                f"det_R_clean={clean:.0f} at final step (step 10) of {fname}"
                + (f"; NaN because det_R_contam+det_R_clean=0" if denom == 0 else "")
            ),
        })

    # --------------------------------------------------------------------
    out_df = pd.DataFrame.from_records(rows, columns=[
        "contrast", "group_a", "group_b", "n_a", "n_b", "mean_a", "mean_b",
        "sd_a", "sd_b", "welch_t", "welch_p", "mwu_u", "mwu_p",
        "boot_ci_lo", "boot_ci_hi", "test_note",
    ])
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(OUTPUT_PATH, index=False)

    with pd.option_context("display.max_columns", None, "display.width", 220, "display.float_format", "{:.4f}".format):
        print(f"Wrote {OUTPUT_PATH} ({len(out_df)} rows)\n")
        print(out_df.drop(columns=["test_note"]).to_string(index=False))

    print("\n--- Headline p-values ---")
    for r in rows:
        if r["contrast"] in (
            "r0_mitigated_vs_oracle_noisy_p10", "r0_mitigated_vs_oracle_noisy_p75",
            "r0_mitigated_vs_oracle_noisy_p50", "r0_noisy_p75_vs_p50", "r0_noisy_p75_vs_p10",
            "r0_noisy_p50_vs_p10", "final_propagated_baseline_vs_oracle_noisy_p10",
            "final_propagated_baseline_vs_mitigated", "final_cum_exposed_baseline_vs_oracle_noisy_p10",
            "final_cum_exposed_baseline_vs_mitigated", "beta_variance_levene", "beta_variance_fratio",
            "detection_auroc_baseline_vs_mitigated",
        ):
            print(f"{r['contrast']:52s} welch_p={r['welch_p']:.4f}  mwu_p={r['mwu_p']:.4f}" if not np.isnan(r["welch_p"]) else f"{r['contrast']:52s}")


if __name__ == "__main__":
    main()
