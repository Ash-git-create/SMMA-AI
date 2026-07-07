"""
Task #9 — natural contamination rate audit.

Every contamination number so far is conditioned on INJECTED errors (RQ2-4).
RQ1 asks under what conditions NON-ADVERSARIAL errors arise and persist. This
script measures the base rate of that process: how often does the unmodified
ExtractionAgent write an erroneous triplet in the first place?

Method — fidelity audit of extraction-written triplets against their source:
  1. Re-derive each document unit's source text with the same sampling code,
     seed, and config as run_extraction.py (deterministic replay, no LLM).
  2. Fetch the triplets each unit actually wrote to the KG (extraction
     manifest triplet_ids -> Neo4j).
  3. Exclude any triplet ground-truth-flagged as injected/transmitted
     contamination (contamination manifest IDs + the node's own error_type).
  4. Have the validation-role LLM (Llama 3.1 8B — the same judge grade as the
     ValidationAgent) classify each triplet against its source passage:

       SUPPORTED       faithful to the passage
       QUALIFIER_LOSS  core fact right, temporal/spatial/conditional modifier lost
       ENTITY_ERROR    wrong entity substituted (disambiguation failure)
       RELATION_ERROR  predicate wrong or stronger than the passage supports
       UNSUPPORTED     not inferable from the passage (hallucination)

The middle three labels mirror the injected error taxonomy, so the audit also
tests whether the natural error distribution matches what Phase 2.3 injects
(RQ2 tie-in). NOTE: this is a *fidelity* audit (triplet vs passage), not a
truth audit — a faithfully extracted false FEVER claim counts as SUPPORTED.

Run from project root with venv active (Neo4j must be up):
    python scripts/audit_natural.py
    python scripts/audit_natural.py --limit 200 --sleep 1.0
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
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
sys.path.insert(0, str(ROOT / "scripts"))

from run_extraction import fever_units, hotpotqa_units, load_jsonl  # noqa: E402

from src.agents.llm_client import ModelRole, get_client  # noqa: E402
from src.graph.neo4j_client import Neo4jClient  # noqa: E402

logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

PROC_DIR = ROOT / "data" / "processed"
RESULTS_DIR = ROOT / "results" / "raw"

LABELS = ("SUPPORTED", "QUALIFIER_LOSS", "ENTITY_ERROR", "RELATION_ERROR", "UNSUPPORTED")

JUDGE_SYSTEM = (
    "You audit knowledge-graph triplets extracted from text. Judge ONLY whether "
    "the triplet is faithful to the given passage — not whether it is true in "
    "the real world. Answer with a single JSON object and nothing else."
)

JUDGE_PROMPT = """Passage:
\"\"\"{text}\"\"\"

Extracted triplet:
  subject:   {subject}
  predicate: {predicate}
  object:    {object}

Classify the triplet against the passage with exactly one label:
- SUPPORTED: the passage states this fact; no meaning was lost or changed.
- QUALIFIER_LOSS: the core fact is in the passage, but a temporal, spatial, or conditional qualifier present in the passage was dropped, changing the claim's scope.
- ENTITY_ERROR: the subject or object names a different entity than the passage supports (wrong person/place/work, merged entities).
- RELATION_ERROR: the predicate misstates the relationship (e.g. a weak association upgraded to a strong/causal one, reversed direction, wrong relation).
- UNSUPPORTED: the passage does not support this fact at all.

Answer as JSON: {{"label": "<one of the five labels>", "reason": "<one short sentence>"}}"""


def rebuild_unit_texts(cfg: dict) -> dict[str, str]:
    """Replicate run_extraction.run_pipeline's unit collection exactly:
    same rng, same sampling order (hotpotqa first, then fever)."""
    rng = random.Random(cfg["random_seed"])
    units: list[dict] = []

    docs = load_jsonl(PROC_DIR / "hotpotqa.jsonl")
    docs = [d for d in docs if d.get("split") == cfg["split"]]
    docs = rng.sample(docs, min(cfg["num_docs"], len(docs)))
    units += hotpotqa_units(docs, cfg["paragraphs_per_doc"])

    docs = load_jsonl(PROC_DIR / "fever.jsonl")
    fever_split = "dev" if cfg["split"] == "validation" else cfg["split"]
    filtered = [d for d in docs if d.get("split") == fever_split]
    docs = rng.sample(filtered or docs, min(cfg["num_docs"], len(docs)))
    units += fever_units(docs)

    return {u["unit_id"]: u["text"] for u in units}


def contaminated_ids(manifest_path: Path) -> set[str]:
    with open(manifest_path, encoding="utf-8") as f:
        m = json.load(f)
    ids = {r["triplet_id"] for r in m.get("seed_records", [])}
    ids |= {r["id"] for r in m.get("transmissions", [])}
    return ids


def parse_judgement(raw: str) -> tuple[str, str]:
    """JSON first; fall back to first label keyword in the raw text."""
    try:
        blob = re.search(r"\{.*\}", raw, re.DOTALL)
        if blob:
            obj = json.loads(blob.group(0))
            label = str(obj.get("label", "")).strip().upper().replace(" ", "_")
            if label in LABELS:
                return label, str(obj.get("reason", ""))[:300]
    except (json.JSONDecodeError, AttributeError):
        pass
    upper = raw.upper()
    hits = [(upper.find(lb), lb) for lb in LABELS if lb in upper]
    if hits:
        return min(hits)[1], raw.strip()[:300]
    return "PARSE_FAILURE", raw.strip()[:300]


def main() -> None:
    parser = argparse.ArgumentParser(description="Task #9 natural contamination audit")
    parser.add_argument("--extraction-manifest", type=str, default=None,
                        help="Extraction manifest CSV (default: latest extraction_*.csv)")
    parser.add_argument("--contamination-manifest", type=str, default=None,
                        help="Contamination manifest JSON whose gt IDs to exclude (default: latest)")
    parser.add_argument("--split",              type=str, default="validation")
    parser.add_argument("--num-docs",           type=int, default=50)
    parser.add_argument("--paragraphs-per-doc", type=int, default=2)
    parser.add_argument("--extraction-seed",    type=int, default=42,
                        help="Seed run_extraction used (unit-text replay must match)")
    parser.add_argument("--limit",              type=int, default=0,
                        help="Audit a random sample of this size (0 = all)")
    parser.add_argument("--random-seed",        type=int, default=42, help="Sampling seed for --limit")
    parser.add_argument("--sleep",              type=float, default=1.0)
    args = parser.parse_args()

    ex_path = Path(args.extraction_manifest) if args.extraction_manifest else \
        max(RESULTS_DIR.glob("extraction_*.csv"), key=lambda p: p.stat().st_mtime)
    ct_path = Path(args.contamination_manifest) if args.contamination_manifest else \
        max(RESULTS_DIR.glob("contamination_*_manifest.json"), key=lambda p: p.stat().st_mtime)

    logger.info(f"Extraction manifest:    {ex_path.name}")
    logger.info(f"Excluding gt IDs from:  {ct_path.name}")

    unit_texts = rebuild_unit_texts({
        "random_seed": args.extraction_seed, "split": args.split,
        "num_docs": args.num_docs, "paragraphs_per_doc": args.paragraphs_per_doc,
    })
    excluded = contaminated_ids(ct_path)

    # Collect audit items: (unit_id, dataset, triplet_id) with known source text
    items: list[dict] = []
    n_excluded = n_no_text = 0
    with open(ex_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["unit_id"] not in unit_texts:
                n_no_text += int(row["n_triplets"] or 0)
                continue
            for tid in filter(None, row["triplet_ids"].split(";")):
                if tid in excluded:
                    n_excluded += 1
                    continue
                items.append({"unit_id": row["unit_id"], "dataset": row["dataset"],
                              "triplet_id": tid})

    logger.info(f"{len(items)} extraction-written triplets to audit "
                f"({n_excluded} gt-contaminated excluded, {n_no_text} without unit text)")
    if args.limit and args.limit < len(items):
        items = random.Random(args.random_seed).sample(items, args.limit)
        logger.info(f"Sampled {len(items)} (seed {args.random_seed})")

    judge = get_client(ModelRole.ORCHESTRATION)
    counts: dict[str, int] = {lb: 0 for lb in (*LABELS, "PARSE_FAILURE")}
    rows_out: list[dict] = []
    n_missing = n_error_flagged = 0

    with Neo4jClient() as client:
        for i, item in enumerate(items, 1):
            t = client.get_triplet(item["triplet_id"])
            if t is None:
                n_missing += 1
                continue
            if t.get("error_type"):  # belt-and-suspenders vs manifest exclusion
                n_error_flagged += 1
                continue

            prompt = JUDGE_PROMPT.format(
                text=unit_texts[item["unit_id"]],
                subject=t.get("subject", ""), predicate=t.get("predicate", ""),
                object=t.get("object", ""),
            )
            resp = judge.chat(prompt, system=JUDGE_SYSTEM)
            label, reason = parse_judgement(resp.content)
            counts[label] += 1
            rows_out.append({
                "triplet_id": item["triplet_id"], "unit_id": item["unit_id"],
                "dataset": item["dataset"], "subject": t.get("subject", ""),
                "predicate": t.get("predicate", ""), "object": t.get("object", ""),
                "confidence": t.get("confidence", ""), "label": label, "reason": reason,
            })
            if i % 25 == 0 or i == len(items):
                logger.info(f"[{i}/{len(items)}] {dict(counts)}")
            if args.sleep > 0 and i < len(items):
                time.sleep(args.sleep)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"natural_audit_{ts}.csv"
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows_out[0].keys())
        writer.writeheader()
        writer.writerows(rows_out)

    n_judged = sum(counts[lb] for lb in LABELS)
    n_errors = n_judged - counts["SUPPORTED"]
    summary = {
        "audited": n_judged,
        "natural_error_rate": round(n_errors / n_judged, 4) if n_judged else None,
        **{lb.lower(): counts[lb] for lb in LABELS},
        "parse_failures": counts["PARSE_FAILURE"],
        "gt_contaminated_excluded": n_excluded + n_error_flagged,
        "missing_in_kg": n_missing,
        "output": str(out_path),
    }
    logger.success(f"Natural audit complete: {summary}")

    with open(RESULTS_DIR / f"natural_audit_{ts}_summary.json", "w", encoding="utf-8") as f:
        json.dump({"config": vars(args), "extraction_manifest": str(ex_path),
                   "contamination_manifest_excluded": str(ct_path),
                   "summary": summary}, f, indent=2)


if __name__ == "__main__":
    main()
