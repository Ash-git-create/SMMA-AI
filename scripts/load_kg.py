"""
Load preprocessed T-REx triplets into Neo4j as the pristine baseline KG.

Each triplet is created as a Triplet node (state=S, confidence=1.0) linked
to two Entity nodes (subject, object) via SUBJECT_OF and HAS_OBJECT edges.

Run from project root with venv active:
    python scripts/load_kg.py

Options:
    --clear             Wipe the database before loading (default: False)
    --limit N           Load only first N triplets (default: all)
    --density F         KG-level structural density factor (default: 1.0 —
                         byte-identical to current/default behavior). F < 1.0
                         sparsifies via degree-aware subsampling; F > 1.0
                         densifies-by-restriction (same triplets, fewer
                         entities). See src/graph/density.py for the exact
                         algorithms. REQUIRES --clear (task #21 / RQ3).
    --density-seed N    RNG seed for the sparsification sampler (default:
                         42). Decoupled from --limit/other seeds. Unused
                         (but accepted) for --density > 1.0, which is a
                         pure ranking with no randomness.

Density manipulation happens AFTER --limit slicing and BEFORE provenance
metadata is attached, so `--limit N --density F` composes as "take the
first N T-REx records, then reshape their structural density" — the
density pool is exactly the N-record slice actually loaded.
"""

import argparse
import json
import sys
from pathlib import Path

from loguru import logger

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.graph.density import apply_density
from src.graph.neo4j_client import Neo4jClient
from src.graph.provenance_schema import TripletMetadata


logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")


def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main(
    clear: bool,
    limit: int | None,
    density: float,
    density_seed: int,
    tag: str | None,
) -> None:
    if density != 1.0 and not clear:
        logger.error(
            f"--density {density} requires --clear: a density-manipulated "
            "KG must never be mistaken for the standard baseline KG "
            "(task #21 invariant)."
        )
        sys.exit(1)

    proc_path = ROOT / "data" / "processed" / "trex_triplets.jsonl"
    if not proc_path.exists():
        logger.error(f"Processed T-REx not found: {proc_path}")
        logger.error("Run: python scripts/preprocess_datasets.py")
        sys.exit(1)

    raw = load_jsonl(proc_path)
    if limit:
        raw = raw[:limit]
    logger.info(f"Loaded {len(raw):,} T-REx triplets from {proc_path}")

    density_stats = None
    if density != 1.0:
        logger.info(f"Applying density factor {density} (seed={density_seed})...")
        raw, density_stats = apply_density(raw, density, seed=density_seed)
        logger.info(
            f"Density-manipulated pool: {density_stats['algorithm']} "
            f"-> {len(raw):,} triplets (requested factor {density_stats['requested_factor']}, "
            f"realized factor {density_stats['realized_factor']})"
        )

    # Attach baseline provenance metadata to each record
    records = []
    for r in raw:
        r["meta"] = TripletMetadata.baseline(source_id=r["id"])
        records.append(r)

    with Neo4jClient() as client:
        if clear:
            logger.warning("Clearing existing database...")
            client.clear_all()
        else:
            # Triplets are CREATEd with deterministic ids (trex_0, trex_1, ...)
            # — a second load without --clear would crash on the uniqueness
            # constraint mid-batch and leave a partially doubled entity graph.
            existing = client.count_by_state()
            if existing:
                total = sum(existing.values())
                logger.error(f"KG already contains {total:,} triplets: {existing}")
                logger.error("Re-run with --clear to wipe and reload.")
                sys.exit(1)

        logger.info("Creating indexes and constraints...")
        client.create_indexes()

        logger.info(f"Loading {len(records):,} triplets in batches of 500...")
        n = client.bulk_load_triplets(records)
        logger.success(f"Loaded {n:,} triplets into Neo4j")

        counts = client.count_by_state()
        logger.info(f"SIR state counts: {counts}")
        logger.success("Baseline KG ready. All nodes are Susceptible (S).")

    if density_stats is not None:
        sidecar_tag = tag or f"density_{density}"
        sidecar_dir = ROOT / "results" / "raw"
        sidecar_dir.mkdir(parents=True, exist_ok=True)
        sidecar_path = sidecar_dir / f"kg_density_{sidecar_tag}.json"
        sidecar_path.write_text(json.dumps(density_stats, indent=2), encoding="utf-8")
        logger.success(f"Density stats archived -> {sidecar_path}")
        logger.info(
            f"Realized: n_triplets={density_stats['realized']['n_triplets']:,} "
            f"n_entities={density_stats['realized']['n_entities']:,} "
            f"mean_degree={density_stats['realized']['mean_degree']} "
            f"median_degree={density_stats['realized']['median_degree']} "
            f"p90_degree={density_stats['realized']['p90_degree']}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true", help="Wipe DB before loading")
    parser.add_argument("--limit", type=int, default=None, help="Load only first N records")
    parser.add_argument("--density", type=float, default=1.0,
                        help="Structural density factor: <1.0 sparsifies, >1.0 "
                             "densifies-by-restriction, 1.0 = byte-identical "
                             "default. Requires --clear when != 1.0.")
    parser.add_argument("--density-seed", type=int, default=42,
                        help="RNG seed for degree-aware sparsification (decoupled "
                             "from all other seeds; unused for --density > 1.0)")
    parser.add_argument("--tag", type=str, default=None,
                        help="Tag for the density stats sidecar filename "
                             "(results/raw/kg_density_<tag>.json); defaults to "
                             "'density_<factor>'")
    args = parser.parse_args()
    main(
        clear=args.clear,
        limit=args.limit,
        density=args.density,
        density_seed=args.density_seed,
        tag=args.tag,
    )
