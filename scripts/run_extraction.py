"""
Phase 2.1 — extraction pipeline: HotpotQA/FEVER documents → ExtractionAgent → Neo4j.

The write-back loop this implements is the mechanism contamination spreads by:
  1. For each document unit, retrieve related facts from the KG (possibly
     contaminated) — the retrieval component of beta.
  2. Show those facts to the ExtractionAgent alongside the passage — the
     susceptibility component of beta.
  3. Write the extracted triplets back to the KG with lineage formulas AND
     DERIVED_FROM edges to the retrieved parents — making the Trio cascade
     (Phase 3) walkable.

Document units:
  HotpotQA — the supporting-fact paragraphs of each question (title + sentences)
  FEVER    — the claim sentence itself

Run from project root with venv active:
    python scripts/run_extraction.py --config experiments/configs/extraction_baseline.yaml
    python scripts/run_extraction.py --dataset hotpotqa --num-docs 10 --dry-run
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

# Windows consoles default to cp1252
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.agents.extraction_agent import ExtractionAgent
from src.graph.neo4j_client import Neo4jClient

logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

PROC_DIR = ROOT / "data" / "processed"
RESULTS_DIR = ROOT / "results" / "raw"


def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def hotpotqa_units(docs: list[dict], paragraphs_per_doc: int) -> list[dict]:
    """One unit per supporting-fact paragraph: {unit_id, key, text}."""
    units = []
    for doc in docs:
        supporting_titles = {sf["title"] for sf in doc.get("supporting_facts", [])}
        paragraphs = [p for p in doc.get("context", []) if p["title"] in supporting_titles]
        if not paragraphs:  # fall back to the first paragraphs if no match
            paragraphs = doc.get("context", [])
        for p in paragraphs[:paragraphs_per_doc]:
            text = f"{p['title']}. " + " ".join(p.get("sentences", []))
            units.append({
                "unit_id": f"hotpot_{doc['id']}_{p['title']}",
                "dataset": "hotpotqa",
                "key":     p["title"],       # entity key for KG context retrieval
                "text":    text[:2000],
            })
    return units


def fever_units(docs: list[dict]) -> list[dict]:
    """One unit per claim: {unit_id, key, text}."""
    units = []
    for doc in docs:
        claim = doc.get("claim", "").strip()
        if not claim:
            continue
        units.append({
            "unit_id": f"fever_{doc['id']}",
            "dataset": "fever",
            "key":     _leading_entity(claim),
            "text":    claim,
        })
    return units


def _leading_entity(claim: str) -> str:
    """FEVER claims usually open with the subject entity — take the leading
    run of capitalized tokens as the KG retrieval key."""
    tokens = claim.replace(",", " ").split()
    entity = []
    for tok in tokens:
        if tok[:1].isupper():
            entity.append(tok)
        else:
            break
    key = " ".join(entity)
    # A lone sentence-initial article is not an entity — skip retrieval for it
    if key in ("The", "A", "An", "It", "There", "This", "In", "On"):
        return ""
    return key


def run_pipeline(args) -> dict:
    # --- Collect document units (seeded sample) ---
    rng = random.Random(args.random_seed)
    units: list[dict] = []

    # Split filtering matches run_baseline_eval.py: with the same seed and
    # num_docs == num_questions, extraction and evaluation sample the SAME
    # documents — so the KG contains the facts the eval questions need.
    if args.dataset in ("hotpotqa", "both"):
        docs = load_jsonl(PROC_DIR / "hotpotqa.jsonl")
        if args.split != "any":
            docs = [d for d in docs if d.get("split") == args.split]
        docs = rng.sample(docs, min(args.num_docs, len(docs)))
        units += hotpotqa_units(docs, args.paragraphs_per_doc)

    if args.dataset in ("fever", "both"):
        docs = load_jsonl(PROC_DIR / "fever.jsonl")
        if args.split != "any":
            fever_split = "dev" if args.split == "validation" else args.split
            filtered = [d for d in docs if d.get("split") == fever_split]
            docs = filtered or docs
        docs = rng.sample(docs, min(args.num_docs, len(docs)))
        units += fever_units(docs)

    logger.info(f"{len(units)} document units to extract from "
                f"(dataset={args.dataset}, num_docs={args.num_docs}, seed={args.random_seed})")

    # --- Extraction loop ---
    manifest = []
    total_triplets = 0
    total_edges = 0
    failures = 0

    with Neo4jClient() as client:
        agent = ExtractionAgent(
            agent_id="extraction_pipeline",
            neo4j_client=client,
        )

        for i, unit in enumerate(units, 1):
            # 1. Retrieve KG context for this unit's entity (beta: retrieval)
            context_facts = []
            if args.kg_context and unit["key"]:
                context_facts = client.get_related_triplets(
                    subject=unit["key"],
                    obj=unit["key"],
                    exclude_id="",
                    min_confidence=args.retrieval_threshold,
                    limit=args.context_limit,
                )

            # 2 + 3. Extract with context and write back with lineage
            if args.dry_run:
                triplets = agent.extract_only(unit["text"], context_facts or None)
                records = [{"id": "(dry-run)"} for _ in triplets]
            else:
                records = agent.extract_and_store(
                    text=unit["text"],
                    source_label=f"{unit['dataset']}_extraction",
                    context_facts=context_facts or None,
                )

            n_edges = len(records) * len(context_facts)
            total_triplets += len(records)
            total_edges += 0 if args.dry_run else n_edges
            if not records:
                failures += 1  # parse/LLM failure or genuinely empty text

            manifest.append({
                "unit_id":     unit["unit_id"],
                "dataset":     unit["dataset"],
                "key":         unit["key"],
                "n_context":   len(context_facts),
                "n_triplets":  len(records),
                "triplet_ids": ";".join(r["id"] for r in records),
            })

            logger.info(
                f"[{i}/{len(units)}] {unit['unit_id'][:60]} — "
                f"context={len(context_facts)}, triplets={len(records)}"
            )
            if args.sleep > 0 and i < len(units):
                time.sleep(args.sleep)  # free-tier rate limiting

    # --- Manifest for provenance / later analysis ---
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    manifest_path = RESULTS_DIR / f"extraction_{args.dataset}_{ts}.csv"
    with open(manifest_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=manifest[0].keys())
        writer.writeheader()
        writer.writerows(manifest)

    summary = {
        "units":        len(units),
        "triplets":     total_triplets,
        "lineage_edges": total_edges,
        "empty_or_failed": failures,
        "manifest":     str(manifest_path),
    }
    logger.success(f"Extraction complete: {summary}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 2.1 extraction pipeline")
    parser.add_argument("--config",             type=str,   default=None, help="YAML config; CLI flags override")
    parser.add_argument("--dataset",            type=str,   default="both", choices=["hotpotqa", "fever", "both"])
    parser.add_argument("--split",              type=str,   default="validation", choices=["validation", "train", "any"],
                        help="Dataset split (validation aligns with run_baseline_eval.py)")
    parser.add_argument("--num-docs",           type=int,   default=50,   help="Documents sampled per dataset")
    parser.add_argument("--paragraphs-per-doc", type=int,   default=2,    help="HotpotQA paragraphs per document")
    parser.add_argument("--context-limit",      type=int,   default=5,    help="Max KG facts retrieved per unit")
    parser.add_argument("--retrieval-threshold", type=float, default=0.0, help="Confidence floor for KG context (0 = baseline, no floor)")
    parser.add_argument("--no-kg-context",      dest="kg_context", action="store_false",
                        help="Disable KG context retrieval (isolated extraction)")
    parser.add_argument("--random-seed",        type=int,   default=42)
    parser.add_argument("--sleep",              type=float, default=1.0,  help="Seconds between LLM calls (rate limiting)")
    parser.add_argument("--dry-run",            action="store_true",      help="Extract but do not write to Neo4j")

    pre_args, _ = parser.parse_known_args()
    if pre_args.config:
        from src.config import load_config
        cfg = load_config(pre_args.config)
        known = {a.dest for a in parser._actions}
        parser.set_defaults(**{k: v for k, v in cfg.items() if k in known})
    args = parser.parse_args()

    logger.info("=== Phase 2.1 Extraction Pipeline ===")
    run_pipeline(args)


if __name__ == "__main__":
    main()
