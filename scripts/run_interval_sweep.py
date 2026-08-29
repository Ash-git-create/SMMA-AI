"""
Resumable chain runner — RQ3 validation-interval sweep (--validate-every).

Closes the RQ3 exposé commitment ("how do validation intervals affect
contamination velocity and reach") for the oracle-validator arm. Runs the 9
oracle-arm interval configs — validate_every in {2, 5, 10} x seeds
{42, 43, 44} — through the standard 3-stage clean room (CLAUDE.md rule 8):

    python scripts/load_kg.py --clear
    python scripts/run_extraction.py --config experiments/configs/extraction_baseline.yaml
    python scripts/run_contamination.py --config experiments/configs/contamination_oracle_int<N>_s<S>.yaml

with a Neo4j preflight poll before each chain link. interval=1 is the
already-archived n=4 baseline (contamination_oracle.yaml, seeds 42-45) and
is intentionally NOT rerun here.

Resumable by construction: before launching an arm, checks whether its
archive already exists in results/summaries/
(phase48_interval_<arm>_manifest.json) and skips it if so. A killed or
failed chain can be relaunched with the identical command and will pick up
where it left off — nothing is archived until run_contamination.py exits 0
AND its trajectory/manifest are found in results/raw, so a partial run can
never be mistaken for a complete one.

This script never starts Neo4j (Desktop-managed and started manually);
the preflight only polls and reports.

Usage (from project root, venv active, Neo4j already started manually):
    python scripts/run_interval_sweep.py                # full 9-arm chain
    python scripts/run_interval_sweep.py --only int5_s43   # single arm
    python scripts/run_interval_sweep.py --dry-run          # print the plan, no side effects
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

from loguru import logger

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
PYTHON = ROOT / "venv" / "Scripts" / "python.exe"
RAW_DIR = ROOT / "results" / "raw"
SUMMARY_DIR = ROOT / "results" / "summaries"
CONFIG_DIR = ROOT / "experiments" / "configs"
EXTRACTION_CONFIG = CONFIG_DIR / "extraction_baseline.yaml"

logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

ARCHIVE_PREFIX = "phase48_interval"

# (arm label, config filename) — interval=1 (n=4, seeds 42-45) already
# archived as contamination_oracle.yaml / phase38_oracle*, NOT rerun here.
RUNS = [
    (f"int{n}_s{s}", f"contamination_oracle_int{n}_s{s}.yaml")
    for n in (2, 5, 10)
    for s in (42, 43, 44)
]


def neo4j_preflight(max_wait: float = 60.0, poll_every: float = 3.0) -> bool:
    """Poll Neo4j connectivity (same check as scripts/verify_setup.py's
    connectivity probe). Never starts Neo4j — just waits for it to become
    reachable if it's already coming up, and reports pass/fail either way."""
    import os
    from dotenv import load_dotenv
    from neo4j import GraphDatabase

    load_dotenv()
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USERNAME", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "")
    deadline = time.time() + max_wait
    last_exc: Exception | None = None
    while time.time() < deadline:
        try:
            driver = GraphDatabase.driver(uri, auth=(user, password))
            driver.verify_connectivity()
            driver.close()
            logger.success(f"Neo4j preflight OK ({uri})")
            return True
        except Exception as exc:  # noqa: BLE001 - report and retry
            last_exc = exc
            time.sleep(poll_every)
    logger.error(f"Neo4j preflight FAILED after {max_wait:.0f}s ({uri}): {last_exc}")
    return False


def archive_exists(arm: str) -> bool:
    return (SUMMARY_DIR / f"{ARCHIVE_PREFIX}_{arm}_manifest.json").exists()


def latest_raw(tag: str, kind: str) -> Path | None:
    """Newest results/raw/contamination_<tag>_<ts>_<kind>.{csv,json} for
    this arm's tag — same newest-by-mtime pattern as
    run_contamination.latest_extraction_manifest."""
    ext = "csv" if kind == "trajectory" else "json"
    candidates = list(RAW_DIR.glob(f"contamination_{tag}_*_{kind}.{ext}"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def archive_run(arm: str, tag: str) -> bool:
    """Copy this run's newest trajectory+manifest from results/raw into
    results/summaries under the phase48_interval_ prefix. Returns True iff
    both files were found and copied — archive_exists (the resumability
    check) depends on the manifest landing here."""
    traj = latest_raw(tag, "trajectory")
    manifest = latest_raw(tag, "manifest")
    if traj is None or manifest is None:
        logger.error(f"[{arm}] run_contamination did not produce results/raw "
                     f"trajectory/manifest for tag='{tag}' — not archiving.")
        return False
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    dst_traj = SUMMARY_DIR / f"{ARCHIVE_PREFIX}_{arm}_trajectory.csv"
    dst_manifest = SUMMARY_DIR / f"{ARCHIVE_PREFIX}_{arm}_manifest.json"
    shutil.copy2(traj, dst_traj)
    shutil.copy2(manifest, dst_manifest)
    logger.success(f"[{arm}] archived -> {dst_traj.name}, {dst_manifest.name}")
    return True


def run_stage(cmd: list[str], label: str) -> bool:
    logger.info(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        logger.error(f"{label} FAILED (exit {result.returncode})")
        return False
    return True


def run_arm(arm: str, config_name: str, tag: str) -> bool:
    logger.info(f"=== Arm {arm} (config={config_name}) ===")
    if not neo4j_preflight():
        return False
    if not run_stage([str(PYTHON), "scripts/load_kg.py", "--clear"], "load_kg"):
        return False
    if not run_stage(
        [str(PYTHON), "scripts/run_extraction.py", "--config", str(EXTRACTION_CONFIG)],
        "run_extraction",
    ):
        return False
    if not run_stage(
        [str(PYTHON), "scripts/run_contamination.py",
         "--config", str(CONFIG_DIR / config_name)],
        "run_contamination",
    ):
        return False
    return archive_run(arm, tag)


def main() -> None:
    parser = argparse.ArgumentParser(description="Resumable RQ3 validation-interval sweep chain")
    parser.add_argument("--only", type=str, default=None,
                        help="Run only this arm label (e.g. int5_s43) instead of the full chain")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the plan (which arms would run/skip) and exit — "
                             "no Neo4j preflight, no subprocess calls")
    args = parser.parse_args()

    plan = RUNS if args.only is None else [r for r in RUNS if r[0] == args.only]
    if not plan:
        logger.error(f"--only '{args.only}' does not match any arm. Known arms: "
                     f"{', '.join(a for a, _ in RUNS)}")
        sys.exit(1)

    logger.info(f"Validation-interval sweep chain: {len(plan)} arm(s) planned")
    for arm, config_name in plan:
        status = "SKIP (already archived)" if archive_exists(arm) else "RUN"
        logger.info(f"  {arm:12s} {config_name:42s} -> {status}")
    if args.dry_run:
        return

    completed, skipped, failed = [], [], []
    for arm, config_name in plan:
        if archive_exists(arm):
            logger.info(f"[{arm}] archive already exists — skipping (resumable)")
            skipped.append(arm)
            continue
        tag = f"oracle_{arm}"  # must match the `tag:` key in the arm's yaml
        ok = run_arm(arm, config_name, tag)
        (completed if ok else failed).append(arm)
        if not ok:
            logger.error(f"[{arm}] FAILED — stopping the chain. Fix the issue and re-run "
                         f"this script with the same command; completed/skipped arms are "
                         f"detected automatically and not repeated.")
            break

    logger.success(f"Chain summary: completed={completed}, skipped={skipped}, failed={failed}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
