"""
Phase 2.3 — run a controlled error-injection pass against the KG.

Writes a JSON manifest (results/raw/injection_<ts>.json) recording every
corruption: triplet id, error type, before/after values, seed, and config —
the ground-truth record that Detection AUROC and R₀-per-error-type are
computed against.

Run from project root with venv active:
    python scripts/run_injection.py --per-type 50
    python scripts/run_injection.py --error-type qualifier_loss --count 100 --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.graph.neo4j_client import Neo4jClient
from src.injection.error_injector import ERROR_TYPES, ErrorInjector

logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

RESULTS_DIR = ROOT / "results" / "raw"


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 2.3 error injection")
    parser.add_argument("--config",      type=str, default=None)
    parser.add_argument("--error-type",  type=str, default="all",
                        choices=[*ERROR_TYPES, "all"])
    parser.add_argument("--count",       type=int, default=50,
                        help="Injections for a single --error-type")
    parser.add_argument("--per-type",    type=int, default=None,
                        help="Injections per type when --error-type all (overrides --count)")
    parser.add_argument("--random-seed", type=int, default=42)
    parser.add_argument("--dry-run",     action="store_true",
                        help="Compute corruptions but do not write them")

    pre_args, _ = parser.parse_known_args()
    if pre_args.config:
        from src.config import load_config
        cfg = load_config(pre_args.config)
        known = {a.dest for a in parser._actions}
        parser.set_defaults(**{k: v for k, v in cfg.items() if k in known})
    args = parser.parse_args()

    logger.info(f"=== Phase 2.3 Error Injection === (seed={args.random_seed}, "
                f"dry_run={args.dry_run})")

    with Neo4jClient() as client:
        injector = ErrorInjector(neo4j_client=client, random_seed=args.random_seed)
        if args.error_type == "all":
            n = args.per_type if args.per_type is not None else args.count
            records = injector.inject_all_types(n, dry_run=args.dry_run)
        else:
            records = injector.inject(args.error_type, args.count, dry_run=args.dry_run)

        counts = client.count_by_state()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    manifest = {
        "timestamp":   ts,
        "random_seed": args.random_seed,
        "dry_run":     args.dry_run,
        "requested":   {"error_type": args.error_type,
                        "count": args.count, "per_type": args.per_type},
        "applied":     len(records),
        "by_type":     {et: sum(1 for r in records if r["error_type"] == et)
                        for et in ERROR_TYPES},
        "sir_counts_after": counts,
        "injections":  records,
    }
    out = RESULTS_DIR / f"injection_{ts}{'_dryrun' if args.dry_run else ''}.json"
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.success(f"{len(records)} injections ({manifest['by_type']}) — manifest → {out.name}")


if __name__ == "__main__":
    main()
