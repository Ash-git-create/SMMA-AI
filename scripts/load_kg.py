"""
Load preprocessed T-REx triplets into Neo4j as the pristine baseline KG.

Each triplet is created as a Triplet node (state=S, confidence=1.0) linked
to two Entity nodes (subject, object) via SUBJECT_OF and HAS_OBJECT edges.

Run from project root with venv active:
    python scripts/load_kg.py

Options:
    --clear     Wipe the database before loading (default: False)
    --limit N   Load only first N triplets (default: all)
"""

import argparse
import json
import sys
from pathlib import Path

from loguru import logger

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.graph.neo4j_client import Neo4jClient
from src.graph.provenance_schema import TripletMetadata


logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")


def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main(clear: bool, limit: int | None) -> None:
    proc_path = ROOT / "data" / "processed" / "trex_triplets.jsonl"
    if not proc_path.exists():
        logger.error(f"Processed T-REx not found: {proc_path}")
        logger.error("Run: python scripts/preprocess_datasets.py")
        sys.exit(1)

    raw = load_jsonl(proc_path)
    if limit:
        raw = raw[:limit]
    logger.info(f"Loaded {len(raw):,} T-REx triplets from {proc_path}")

    # Attach baseline provenance metadata to each record
    records = []
    for r in raw:
        r["meta"] = TripletMetadata.baseline(source_id=r["id"])
        records.append(r)

    with Neo4jClient() as client:
        if clear:
            logger.warning("Clearing existing database...")
            client.clear_all()

        logger.info("Creating indexes and constraints...")
        client.create_indexes()

        logger.info(f"Loading {len(records):,} triplets in batches of 500...")
        n = client.bulk_load_triplets(records)
        logger.success(f"Loaded {n:,} triplets into Neo4j")

        counts = client.count_by_state()
        logger.info(f"SIR state counts: {counts}")
        logger.success("Baseline KG ready. All nodes are Susceptible (S).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true", help="Wipe DB before loading")
    parser.add_argument("--limit", type=int, default=None, help="Load only first N records")
    args = parser.parse_args()
    main(clear=args.clear, limit=args.limit)
