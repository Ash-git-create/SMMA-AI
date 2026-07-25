"""
Resumable chain runner — task #34 cross-family judge replication.

Runs the 4-seed contamination_mitigated_haiku_s{42,43,44,45}.yaml configs
(mitigated Trio arm, in-run validator judge routed to Claude Haiku instead
of Groq Llama-3.1-8B) through the standard 3-stage clean room (CLAUDE.md
rule 8):

    python scripts/load_kg.py --clear
    python scripts/run_extraction.py --config experiments/configs/extraction_baseline.yaml
    python scripts/run_contamination.py --config experiments/configs/contamination_mitigated_haiku_s<S>.yaml

with a Neo4j preflight poll before each chain link. This SPENDS REAL MONEY
(Anthropic API, ~250 Haiku calls/run per the audit_sample=25 x 10 steps
cap) — see the cost estimate in the module docstring of the requesting
session's task notes / thesis_log before launching.

Resumable by construction: before launching a seed, checks whether its
archive already exists in results/summaries/
(phase50_mitigated_haiku_s<S>_manifest.json) and skips it if so. A killed
or failed chain can be relaunched with the identical command and will pick
up where it left off — nothing is archived until run_contamination.py
exits 0 AND its trajectory/manifest are found in results/raw, so a partial
run can never be mistaken for a complete one.

This script never starts Neo4j (Desktop-managed — only Ashwin starts it,
per CLAUDE.md); the preflight only polls and reports.

Usage (from project root, venv active, Neo4j already started manually):
    python scripts/run_haiku_validator_arm.py                # full 4-seed chain
    python scripts/run_haiku_validator_arm.py --only s43       # single seed
    python scripts/run_haiku_validator_arm.py --dry-run        # print the plan, no side effects
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

ARCHIVE_PREFIX = "phase50_mitigated_haiku"

# (seed label, config filename) — the 4-seed replication of the mitigated
# Trio arm with the judge routed to Claude Haiku.
RUNS = [
    (f"s{s}", f"contamination_mitigated_haiku_s{s}.yaml")
    for s in (42, 43, 44, 45)
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


def archive_exists(seed_label: str) -> bool:
    return (SUMMARY_DIR / f"{ARCHIVE_PREFIX}_{seed_label}_manifest.json").exists()


def latest_raw(tag: str, kind: str) -> Path | None:
    """Newest results/raw/contamination_<tag>_<ts>_<kind>.{csv,json} for
    this arm's tag — same newest-by-mtime pattern as
    run_contamination.latest_extraction_manifest."""
    ext = "csv" if kind == "trajectory" else "json"
    candidates = list(RAW_DIR.glob(f"contamination_{tag}_*_{kind}.{ext}"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def archive_run(seed_label: str, tag: str) -> bool:
    """Copy this run's newest trajectory+manifest from results/raw into
    results/summaries under the phase50_mitigated_haiku_ prefix. Returns
    True iff both files were found and copied — archive_exists (the
    resumability check) depends on the manifest landing here."""
    traj = latest_raw(tag, "trajectory")
    manifest = latest_raw(tag, "manifest")
    if traj is None or manifest is None:
        logger.error(f"[{seed_label}] run_contamination did not produce results/raw "
                     f"trajectory/manifest for tag='{tag}' — not archiving.")
        return False
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    dst_traj = SUMMARY_DIR / f"{ARCHIVE_PREFIX}_{seed_label}_trajectory.csv"
    dst_manifest = SUMMARY_DIR / f"{ARCHIVE_PREFIX}_{seed_label}_manifest.json"
    shutil.copy2(traj, dst_traj)
    shutil.copy2(manifest, dst_manifest)
    logger.success(f"[{seed_label}] archived -> {dst_traj.name}, {dst_manifest.name}")
    return True


def run_stage(cmd: list[str], label: str) -> bool:
    logger.info(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        logger.error(f"{label} FAILED (exit {result.returncode})")
        return False
    return True


def run_seed(seed_label: str, config_name: str, tag: str) -> bool:
    logger.info(f"=== Seed {seed_label} (config={config_name}) ===")
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
    return archive_run(seed_label, tag)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resumable task #34 cross-family judge replication chain "
                     "(mitigated Trio, judge=Claude Haiku, 4 seeds)")
    parser.add_argument("--only", type=str, default=None,
                        help="Run only this seed label (e.g. s43) instead of the full chain")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the plan (which seeds would run/skip) and exit — "
                             "no Neo4j preflight, no subprocess calls, NO API SPEND")
    args = parser.parse_args()

    plan = RUNS if args.only is None else [r for r in RUNS if r[0] == args.only]
    if not plan:
        logger.error(f"--only '{args.only}' does not match any seed. Known seeds: "
                     f"{', '.join(a for a, _ in RUNS)}")
        sys.exit(1)

    logger.info(f"Task #34 Haiku-validator chain: {len(plan)} seed(s) planned")
    for seed_label, config_name in plan:
        status = "SKIP (already archived)" if archive_exists(seed_label) else "RUN"
        logger.info(f"  {seed_label:6s} {config_name:42s} -> {status}")
    if args.dry_run:
        return

    completed, skipped, failed = [], [], []
    for seed_label, config_name in plan:
        if archive_exists(seed_label):
            logger.info(f"[{seed_label}] archive already exists — skipping (resumable)")
            skipped.append(seed_label)
            continue
        tag = f"mitigated_haiku_{seed_label}"  # must match the `tag:` key in the seed's yaml
        ok = run_seed(seed_label, config_name, tag)
        (completed if ok else failed).append(seed_label)
        if not ok:
            logger.error(f"[{seed_label}] FAILED — stopping the chain. Fix the issue and "
                         f"re-run this script with the same command; completed/skipped "
                         f"seeds are detected automatically and not repeated.")
            break

    logger.success(f"Chain summary: completed={completed}, skipped={skipped}, failed={failed}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
