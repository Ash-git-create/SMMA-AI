"""
Phase 3.5 — per-error-type contamination analysis (RQ2: which error types
are most harmful?).

Aggregates seeded vs. transmitted (propagated) counts by error type directly
from the contamination-run manifests (results/summaries/phase32_*_manifest.json,
phase33_baseline_s4*_manifest.json). Each manifest has:
  seed_records  — the injected "patient zero" cases, each carrying
                  error_type in {entity_disambiguation, qualifier_loss,
                  relation_strengthening}.
  transmissions — the propagated contaminated facts the pipeline generated
                  from those seeds during the run, each already carrying
                  root_type: the error type of the seed case it descended
                  from. No separate parent/lineage lookup is required —
                  root_type is populated on every transmission record in
                  every manifest inspected for this analysis (verified
                  below at load time; any transmission missing it is
                  counted explicitly as UNATTRIBUTED rather than guessed).

For each run this computes, per error type:
  seeded_count          — how many patient-zero cases of this type were injected
  transmitted_count      — how many propagated facts trace back to this type
  reproduction_per_seed  — transmitted_count / seeded_count (empirical,
                            model-free "how many new bad facts does one seed
                            of this type spawn" — the per-type analogue of
                            the whole-run reproduction_per_seed already used
                            in results/summaries/phase32_arm_comparison.csv)

These are aggregated (mean +/- sd) across the four baseline seeds
(42, 43, 44, 45), and compared across the four seed-42 arms (baseline,
ablation_floor, ablation_validation, mitigated) to see whether mitigation
shifts which error type dominates the propagated pool.

Usage (from project root, with venv active):
    python scripts/analyze_error_types.py
    python scripts/analyze_error_types.py --manifests results/summaries/phase32_baseline_manifest.json
    python scripts/analyze_error_types.py --output results/summaries/phase35_error_type_analysis.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
from loguru import logger

logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

SUMMARIES_DIR = ROOT / "results" / "summaries"

ERROR_TYPES = ("entity_disambiguation", "qualifier_loss", "relation_strengthening")
UNATTRIBUTED = "UNATTRIBUTED"

DEFAULT_MANIFESTS = [
    "phase32_baseline_manifest.json",
    "phase32_ablation_floor_manifest.json",
    "phase32_ablation_validation_manifest.json",
    "phase32_mitigated_manifest.json",
    "phase33_baseline_s43_manifest.json",
    "phase33_baseline_s44_manifest.json",
    "phase33_baseline_s45_manifest.json",
]

BASELINE_ARM = "baseline"


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


def load_manifest(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        manifest = json.load(f)
    tag = manifest["config"].get("tag", path.stem.replace("_manifest", ""))
    seed = manifest["config"].get("random_seed")
    arm = _arm_from_name(path.stem)
    return {
        "path": path,
        "tag": tag,
        "seed": seed,
        "arm": arm,
        "seed_records": manifest["seed_records"],
        "transmissions": manifest["transmissions"],
    }


def per_run_type_stats(run: dict) -> list[dict]:
    """One row per error type (+ an UNATTRIBUTED row if any transmission
    lacks a root_type), for this run."""
    seed_counts = Counter(s["error_type"] for s in run["seed_records"])

    unattributed = [t for t in run["transmissions"] if not t.get("root_type")]
    attributed = [t for t in run["transmissions"] if t.get("root_type")]
    if unattributed:
        logger.warning(
            f"{run['tag']}: {len(unattributed)} transmission(s) lack root_type — "
            "counted as UNATTRIBUTED, not guessed."
        )
    trans_counts = Counter(t["root_type"] for t in attributed)

    total_seeded = sum(seed_counts.values())
    total_transmitted = len(run["transmissions"])

    rows = []
    for etype in ERROR_TYPES:
        seeded = seed_counts.get(etype, 0)
        transmitted = trans_counts.get(etype, 0)
        rows.append({
            "run_tag": run["tag"],
            "seed": run["seed"],
            "arm": run["arm"],
            "error_type": etype,
            "seeded_count": seeded,
            "transmitted_count": transmitted,
            "reproduction_per_seed": (transmitted / seeded) if seeded > 0 else float("nan"),
            "seeded_share": (seeded / total_seeded) if total_seeded > 0 else float("nan"),
            "transmitted_share": (transmitted / total_transmitted) if total_transmitted > 0 else float("nan"),
        })

    if unattributed:
        rows.append({
            "run_tag": run["tag"],
            "seed": run["seed"],
            "arm": run["arm"],
            "error_type": UNATTRIBUTED,
            "seeded_count": float("nan"),
            "transmitted_count": len(unattributed),
            "reproduction_per_seed": float("nan"),
            "seeded_share": float("nan"),
            "transmitted_share": (len(unattributed) / total_transmitted) if total_transmitted > 0 else float("nan"),
        })

    return rows


def resolve_manifests(patterns: list[str] | None) -> list[Path]:
    if not patterns:
        paths = [SUMMARIES_DIR / name for name in DEFAULT_MANIFESTS]
        missing = [p for p in paths if not p.exists()]
        for m in missing:
            logger.warning(f"Default manifest not found, skipping: {m}")
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
    parser = argparse.ArgumentParser(description="Per-error-type contamination analysis (RQ2).")
    parser.add_argument(
        "--manifests", nargs="*", default=None,
        help="Manifest JSON paths or glob patterns (default: the 4 phase32 arms + 3 phase33 baseline seeds).",
    )
    parser.add_argument(
        "--output", type=str, default=str(SUMMARIES_DIR / "phase35_error_type_analysis.csv"),
        help="Output CSV path.",
    )
    args = parser.parse_args()

    manifest_paths = resolve_manifests(args.manifests)
    if not manifest_paths:
        logger.error("No manifest files resolved. Nothing to analyze.")
        sys.exit(1)

    logger.info(f"Analyzing per-error-type stats for {len(manifest_paths)} run(s)")

    all_rows: list[dict] = []
    for path in manifest_paths:
        run = load_manifest(path)
        rows = per_run_type_stats(run)
        all_rows.extend(rows)
        total_transmitted = sum(r["transmitted_count"] for r in rows)
        logger.info(
            f"{run['tag']:22s} seed={run['seed']!s:4s} "
            + ", ".join(f"{r['error_type']}={r['transmitted_count']}/{r['seeded_count']}" for r in rows)
            + f"  (total transmitted={total_transmitted})"
        )

    df = pd.DataFrame.from_records(all_rows)

    # --- Aggregate across the 4 baseline seeds (42, 43, 44, 45), per error type ---
    baseline_df = df[(df["arm"] == BASELINE_ARM) & (df["error_type"] != UNATTRIBUTED)]
    agg_rows = []
    for etype in ERROR_TYPES:
        sub = baseline_df[baseline_df["error_type"] == etype]
        numeric_cols = ["seeded_count", "transmitted_count", "reproduction_per_seed",
                         "seeded_share", "transmitted_share"]
        mean_row = {"run_tag": "baseline_mean", "seed": "NA", "arm": BASELINE_ARM, "error_type": etype}
        sd_row = {"run_tag": "baseline_sd", "seed": "NA", "arm": BASELINE_ARM, "error_type": etype}
        mean_row.update(sub[numeric_cols].mean().to_dict())
        sd_row.update(sub[numeric_cols].std(ddof=1).to_dict())
        agg_rows.append(mean_row)
        agg_rows.append(sd_row)

    df = pd.concat([df, pd.DataFrame(agg_rows)], ignore_index=True)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    logger.info(f"Wrote {output_path}")

    with pd.option_context("display.max_columns", None, "display.width", 200, "display.float_format", "{:.4f}".format):
        print()
        print("=== Per-run, per-error-type ===")
        print(df[df["seed"] != "NA"].to_string(index=False))
        print()
        print("=== Baseline mean +/- sd across seeds 42/43/44/45 ===")
        print(df[df["seed"] == "NA"].to_string(index=False))
        print()
        print("=== Seed-42 arm comparison: transmitted_share by error type ===")
        seed42 = df[(df["seed"] == 42) & (df["error_type"] != UNATTRIBUTED)]
        pivot = seed42.pivot_table(index="arm", columns="error_type", values="transmitted_share")
        print(pivot.to_string())


if __name__ == "__main__":
    main()
