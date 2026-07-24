"""
measure_judge_recall.py

Token-free, archives-only computation of the LLM judge's IN-RUN RECALL on
contaminated nodes, per arm, for the task-#20/#23 "structural blindness"
finding (see docs/thesis_log.md, CLAUDE.md Analysis & Write-up Discipline).

Reads only files already present in results/summaries/ (trajectory CSVs and
run manifests). Writes nothing except results/summaries/phase41_judge_recall.csv.

Definitions computed per run (see task spec / thesis_log for derivation):

1. END-OF-RUN CATCH RATE (primary number)
       end_catch_rate = det_R_contam(final_step) / gt_total(final_step)
   i.e. of all ground-truth-contaminated nodes that existed by the end of
   the run, what fraction had been quarantined (R-state, ground-truth
   contaminated) by then.

2. CATCH RATE ON SEEDED INDEX CASES ONLY
   The trajectory CSV carries gt_seed_<error_type> and gt_prop_<error_type>
   columns, so the *denominator* (how many ground-truth-contaminated nodes
   were seeded index cases vs. propagated) is derivable and is reported as
   `seeded_count` / `propagated_count` (cross-checked against the manifest's
   `seed_records` list, which independently gives the seeded count).
   The *numerator* is NOT derivable: det_R_contam is a single aggregate
   "quarantined contaminated" count with no seeded/propagated split, and no
   per-node quarantine log/ids exist in the trajectory or the manifest
   (manifest keys are: config, timestamp, extraction_manifest,
   n_active_keys, seed_records, transmissions, trajectory_csv -- seed_records
   and transmissions describe injection/propagation EVENTS, not audit
   outcomes). Per the task's explicit instruction, this is reported as
   "not derivable from archives" rather than approximated.

3. PER-STEP CATCH TRAJECTORY
       catch_rate(t) = det_R_contam(t) / gt_total(t)  for t = 0..final_step
   shows whether catching keeps pace with ground-truth growth.

Audit-budget control check: audits_per_step, audit_sample and audit_targeted
are read from each run's manifest `config` block and asserted identical
across all runs before any cross-arm comparison is made (rather than trusted
from the task prompt).

JUDGE-RECALL DEFICIT (the headline derived number):
    deficit(arm) = mean(end_catch_rate over oracle_noisy_* runs, all p-levels
                        pooled, same audit budget)
                 - mean(end_catch_rate over <arm> runs)
The oracle_noisy_p10/p25/p50/p75 arms all have oracle_sensitivity == 1.0 in
their manifests (verified below) -- i.e. perfect judge recall, with the p
suffix instead varying oracle_false_alarm (audit precision), not recall. So
their catch rate under the identical 25-targeted-audits/step budget is the
correct "perfect recall + this audit coverage" calibration line, and the gap
below it for an LLM-judge arm is attributable to judge recall specifically
(not audit budget).
"""

import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SUMMARIES = ROOT / "results" / "summaries"
OUT_CSV = SUMMARIES / "phase41_judge_recall.csv"

# (arm, seed_label, file_stem)
RUNS = [
    # --- LLM judge, default prompt, mitigated (full Trio) arm, 4 seeds ---
    ("mitigated", "42", "phase32_mitigated"),
    ("mitigated", "43", "phase37_mitigated_s43"),
    ("mitigated", "44", "phase37_mitigated_s44"),
    ("mitigated", "45", "phase37_mitigated_s45"),
    # --- LLM judge, tuned prompt (task #20), 1 seed ---
    ("mitigated_tuned", "42", "phase39_mitigated_tuned"),
    # --- LLM judge, validation-only ablation, 1 seed ---
    ("ablation_validation", "42", "phase32_ablation_validation"),
    # --- perfect judge, sanity anchor, 1 seed ---
    ("oracle", "42", "phase38_oracle"),
    # --- perfect-sensitivity, varying-false-alarm oracle, calibration arms ---
    ("oracle_noisy_p75", "42", "phase40_oracle_noisy_p75"),
    ("oracle_noisy_p75", "43", "phase40_oracle_noisy_p75_s43"),
    ("oracle_noisy_p75", "44", "phase40_oracle_noisy_p75_s44"),
    ("oracle_noisy_p75", "45", "phase40_oracle_noisy_p75_s45"),
    ("oracle_noisy_p50", "42", "phase40_oracle_noisy_p50"),
    ("oracle_noisy_p50", "43", "phase40_oracle_noisy_p50_s43"),
    ("oracle_noisy_p50", "44", "phase40_oracle_noisy_p50_s44"),
    ("oracle_noisy_p50", "45", "phase40_oracle_noisy_p50_s45"),
    ("oracle_noisy_p25", "42", "phase40_oracle_noisy_p25"),  # single seed only
    ("oracle_noisy_p10", "42", "phase40_oracle_noisy_p10"),
    ("oracle_noisy_p10", "43", "phase40_oracle_noisy_p10_s43"),
    ("oracle_noisy_p10", "44", "phase40_oracle_noisy_p10_s44"),
    ("oracle_noisy_p10", "45", "phase40_oracle_noisy_p10_s45"),
]

LLM_JUDGE_ARMS = {"mitigated", "mitigated_tuned", "ablation_validation"}
NOISY_ORACLE_ARMS = {"oracle_noisy_p10", "oracle_noisy_p25", "oracle_noisy_p50", "oracle_noisy_p75"}

SEED_ERR_TYPES = ["entity_disambiguation", "qualifier_loss", "relation_strengthening"]


def load_trajectory(stem):
    path = SUMMARIES / f"{stem}_trajectory.csv"
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_manifest(stem):
    path = SUMMARIES / f"{stem}_manifest.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def safe_div(a, b):
    return (a / b) if b else None


def main():
    rows = load_all_runs()
    check_audit_budget_uniform(rows)
    out_rows = build_output_rows(rows)
    write_csv(out_rows)
    print_summary(rows)


def load_all_runs():
    runs = []
    for arm, seed, stem in RUNS:
        traj = load_trajectory(stem)
        manifest = load_manifest(stem)
        cfg = manifest["config"]

        steps = [int(r["step"]) for r in traj]
        gt_total = [int(r["gt_total"]) for r in traj]
        det_r_contam = [int(r["det_R_contam"]) for r in traj]
        catch_rate = [safe_div(d, g) for d, g in zip(det_r_contam, gt_total)]

        # seeded / propagated ground-truth split, from trajectory gt_seed_*/gt_prop_*
        # columns (constant seeded_count after step 0; propagated grows over time).
        final = traj[-1]
        seeded_count_traj = sum(
            int(final[f"gt_seed_{et}"]) for et in SEED_ERR_TYPES if f"gt_seed_{et}" in final
        )
        propagated_count_traj = sum(
            int(final[f"gt_prop_{et}"]) for et in SEED_ERR_TYPES if f"gt_prop_{et}" in final
        )
        seeded_count_manifest = len(manifest.get("seed_records", []))

        runs.append(
            {
                "arm": arm,
                "seed": seed,
                "stem": stem,
                "steps": steps,
                "gt_total": gt_total,
                "det_R_contam": det_r_contam,
                "catch_rate": catch_rate,
                "final_gt_total": gt_total[-1],
                "final_det_R_contam": det_r_contam[-1],
                "end_catch_rate": catch_rate[-1],
                "seeded_count_traj": seeded_count_traj,
                "propagated_count_traj": propagated_count_traj,
                "seeded_count_manifest": seeded_count_manifest,
                "audits_per_step": cfg.get("audits_per_step"),
                "audit_sample": cfg.get("audit_sample"),
                "audit_targeted": cfg.get("audit_targeted"),
                "oracle_sensitivity": cfg.get("oracle_sensitivity"),
                "oracle_false_alarm": cfg.get("oracle_false_alarm"),
                "validator_prompt": cfg.get("validator_prompt"),
                "random_seed_cfg": cfg.get("random_seed"),
            }
        )
    return runs


def check_audit_budget_uniform(runs):
    budgets = {(r["audits_per_step"], r["audit_sample"], r["audit_targeted"]) for r in runs}
    if len(budgets) != 1:
        print("WARNING: audit budget is NOT uniform across runs:", budgets)
    else:
        (aps, asamp, atarg) = next(iter(budgets))
        print(
            f"Audit budget verified uniform across all {len(runs)} runs: "
            f"audits_per_step={aps}, audit_sample={asamp}, audit_targeted={atarg}"
        )
    for arm in NOISY_ORACLE_ARMS:
        sens = {r["oracle_sensitivity"] for r in runs if r["arm"] == arm}
        print(f"  {arm}: oracle_sensitivity values = {sens}")


def build_output_rows(runs):
    out = []

    # --- per-run rows ---
    for r in runs:
        row = {
            "row_type": "run",
            "arm": r["arm"],
            "seed": r["seed"],
            "final_step": r["steps"][-1],
            "final_gt_total": r["final_gt_total"],
            "final_det_R_contam": r["final_det_R_contam"],
            "end_catch_rate": round(r["end_catch_rate"], 4) if r["end_catch_rate"] is not None else "",
            "seeded_count": r["seeded_count_traj"],
            "propagated_count_final": r["propagated_count_traj"],
            "seeded_count_manifest_crosscheck": r["seeded_count_manifest"],
            "seeded_catch_rate": "not derivable from archives",
            "seeded_catch_rate_note": (
                "det_R_contam is an aggregate quarantined+ground-truth-contaminated "
                "count with no seeded/propagated split, and no per-node quarantine "
                "id/log exists in trajectory or manifest (manifest only has "
                "seed_records/transmissions = injection/propagation events, not "
                "audit outcomes); numerator for this metric cannot be reconstructed"
            ),
            "audits_per_step": r["audits_per_step"],
            "audit_sample": r["audit_sample"],
            "audit_targeted": r["audit_targeted"],
            "oracle_sensitivity": r["oracle_sensitivity"] if r["oracle_sensitivity"] is not None else "",
            "oracle_false_alarm": r["oracle_false_alarm"] if r["oracle_false_alarm"] is not None else "",
            "validator_prompt": r["validator_prompt"] if r["validator_prompt"] is not None else "",
            "source_stem": r["stem"],
        }
        for step, cr in zip(r["steps"], r["catch_rate"]):
            row[f"catch_step{step}"] = round(cr, 4) if cr is not None else ""
        row["per_step_gt_total_json"] = json.dumps(r["gt_total"])
        row["per_step_det_R_contam_json"] = json.dumps(r["det_R_contam"])
        out.append(row)

    # --- per-arm summary rows (mean / SD of end_catch_rate) ---
    arms = sorted({r["arm"] for r in runs})
    arm_stats = {}
    for arm in arms:
        vals = [r["end_catch_rate"] for r in runs if r["arm"] == arm and r["end_catch_rate"] is not None]
        n = len(vals)
        mean = statistics.mean(vals) if vals else None
        sd = statistics.stdev(vals) if n > 1 else (0.0 if n == 1 else None)
        arm_stats[arm] = {"n": n, "mean": mean, "sd": sd}
        out.append(
            {
                "row_type": "summary",
                "arm": arm,
                "seed": f"MEAN (n={n})",
                "end_catch_rate": round(mean, 4) if mean is not None else "",
            }
        )
        out.append(
            {
                "row_type": "summary",
                "arm": arm,
                "seed": "SD" + ("" if n > 1 else " (n=1, undefined)"),
                "end_catch_rate": round(sd, 4) if sd is not None else "",
            }
        )

    # --- pooled noisy-oracle calibration line (all p-levels, same audit budget) ---
    noisy_vals = [
        r["end_catch_rate"] for r in runs if r["arm"] in NOISY_ORACLE_ARMS and r["end_catch_rate"] is not None
    ]
    noisy_mean = statistics.mean(noisy_vals)
    noisy_sd = statistics.stdev(noisy_vals) if len(noisy_vals) > 1 else 0.0
    out.append(
        {
            "row_type": "summary",
            "arm": "oracle_noisy_ALL_POOLED",
            "seed": f"MEAN (n={len(noisy_vals)})",
            "end_catch_rate": round(noisy_mean, 4),
        }
    )
    out.append(
        {
            "row_type": "summary",
            "arm": "oracle_noisy_ALL_POOLED",
            "seed": "SD",
            "end_catch_rate": round(noisy_sd, 4),
        }
    )

    # --- deficit rows: pooled noisy-oracle mean minus each LLM-judge arm mean ---
    for arm in sorted(LLM_JUDGE_ARMS):
        arm_mean = arm_stats[arm]["mean"]
        n = arm_stats[arm]["n"]
        if arm_mean is None:
            continue
        deficit = noisy_mean - arm_mean
        out.append(
            {
                "row_type": "deficit",
                "arm": f"{arm}_vs_oracle_noisy_ALL_POOLED",
                "seed": "",
                "end_catch_rate": "",
                "final_gt_total": "",
                "final_det_R_contam": "",
                "seeded_count": "",
                "seeded_catch_rate": "",
                "seeded_catch_rate_note": (
                    f"JUDGE-RECALL DEFICIT = oracle_noisy_ALL_POOLED mean end_catch_rate "
                    f"({noisy_mean:.4f}, n={len(noisy_vals)}) - {arm} mean end_catch_rate "
                    f"({arm_mean:.4f}, n={n}) = {deficit:.4f}"
                ),
                "deficit_value": round(deficit, 4),
            }
        )

    # deficit vs plain (perfect) oracle too, for the upper-upper-bound comparison
    oracle_val = next((r["end_catch_rate"] for r in runs if r["arm"] == "oracle"), None)
    if oracle_val is not None:
        for arm in sorted(LLM_JUDGE_ARMS):
            arm_mean = arm_stats[arm]["mean"]
            if arm_mean is None:
                continue
            deficit = oracle_val - arm_mean
            out.append(
                {
                    "row_type": "deficit",
                    "arm": f"{arm}_vs_oracle_perfect_single_seed42",
                    "seed": "",
                    "end_catch_rate": "",
                    "seeded_catch_rate": "",
                    "seeded_catch_rate_note": (
                        f"vs single-seed perfect-judge oracle end_catch_rate={oracle_val:.4f}: "
                        f"deficit = {deficit:.4f} (single-seed comparator, not the primary "
                        f"deficit number; use *_vs_oracle_noisy_ALL_POOLED rows for that)"
                    ),
                    "deficit_value": round(deficit, 4),
                }
            )

    return out


def write_csv(out_rows):
    fieldnames = [
        "row_type",
        "arm",
        "seed",
        "final_step",
        "final_gt_total",
        "final_det_R_contam",
        "end_catch_rate",
        "seeded_count",
        "propagated_count_final",
        "seeded_count_manifest_crosscheck",
        "seeded_catch_rate",
        "seeded_catch_rate_note",
        "deficit_value",
        "audits_per_step",
        "audit_sample",
        "audit_targeted",
        "oracle_sensitivity",
        "oracle_false_alarm",
        "validator_prompt",
        "source_stem",
    ] + [f"catch_step{i}" for i in range(0, 11)] + [
        "per_step_gt_total_json",
        "per_step_det_R_contam_json",
    ]

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, restval="")
        writer.writeheader()
        for row in out_rows:
            writer.writerow(row)

    print(f"\nWrote {len(out_rows)} rows to {OUT_CSV}")


def print_summary(runs):
    print("\n" + "=" * 78)
    print("JUDGE IN-RUN RECALL (end-of-run catch rate = det_R_contam(final) / gt_total(final))")
    print("=" * 78)

    arms = sorted({r["arm"] for r in runs}, key=lambda a: (a not in LLM_JUDGE_ARMS, a))
    for arm in arms:
        arm_runs = [r for r in runs if r["arm"] == arm]
        vals = [r["end_catch_rate"] for r in arm_runs]
        seeds = ", ".join(f"s{r['seed']}={r['end_catch_rate']:.3f}" for r in arm_runs)
        mean = statistics.mean(vals)
        sd = statistics.stdev(vals) if len(vals) > 1 else float("nan")
        tag = "  <-- LLM judge" if arm in LLM_JUDGE_ARMS else (
            "  <-- perfect judge, sanity anchor" if arm == "oracle" else ""
        )
        print(f"{arm:24s} n={len(vals)}  mean={mean:.4f}  sd={sd:.4f}   [{seeds}]{tag}")

    noisy_vals = [r["end_catch_rate"] for r in runs if r["arm"] in NOISY_ORACLE_ARMS]
    noisy_mean = statistics.mean(noisy_vals)
    print(f"\n{'oracle_noisy_ALL_POOLED':24s} n={len(noisy_vals)}  mean={noisy_mean:.4f}  "
          f"sd={statistics.stdev(noisy_vals):.4f}   (perfect-sensitivity calibration line, same 25-audit/step budget)")

    print("\n--- JUDGE-RECALL DEFICIT (oracle_noisy_ALL_POOLED mean minus LLM-judge arm mean) ---")
    for arm in sorted(LLM_JUDGE_ARMS):
        arm_vals = [r["end_catch_rate"] for r in runs if r["arm"] == arm]
        arm_mean = statistics.mean(arm_vals)
        deficit = noisy_mean - arm_mean
        note = ""
        if arm == "mitigated_tuned":
            note = "  (single seed; tuned-prompt arm, task #20)"
        print(f"  {arm:24s} mean_catch={arm_mean:.4f}  deficit={deficit:.4f}{note}")

    print("\n--- seeded-only catch rate (definition 2) ---")
    print("  NOT DERIVABLE FROM ARCHIVES: det_R_contam has no seeded/propagated split")
    print("  and no per-node quarantine id/log exists in trajectory CSVs or manifests.")
    print("  Denominator context only (from trajectory gt_seed_*/gt_prop_* columns,")
    print("  cross-checked against manifest seed_records length):")
    for r in runs:
        print(
            f"    {r['arm']:24s} s{r['seed']:>3s}  seeded={r['seeded_count_traj']:3d} "
            f"(manifest={r['seeded_count_manifest']:3d})  propagated_final={r['propagated_count_traj']:3d}"
        )


if __name__ == "__main__":
    main()
