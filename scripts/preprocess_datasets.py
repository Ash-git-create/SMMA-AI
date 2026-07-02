"""
Normalize raw datasets into unified JSONL schemas used throughout the pipeline.

Run from project root with venv active (after download_datasets.py):
    python scripts/preprocess_datasets.py

Output schemas
--------------
T-REx triplet (data/processed/trex_triplets.jsonl):
    {
        "id": str,
        "subject": str,          # entity label
        "predicate": str,        # Wikidata property label (e.g. "place_of_birth")
        "object": str,           # entity label
        "predicate_id": str,     # Wikidata PID (e.g. "P19")
        "subject_uri": str,      # Wikidata QID for subject
        "object_uri": str,       # Wikidata QID for object (if available)
        "source_text": str,      # Wikipedia sentence this triple was extracted from
        "source": "t-rex"
    }

HotpotQA example (data/processed/hotpotqa.jsonl):
    {
        "id": str,
        "question": str,
        "answer": str,
        "supporting_facts": [{"title": str, "sent_idx": int}],
        "context": [{"title": str, "sentences": [str]}],
        "type": str,             # "comparison" or "bridge"
        "level": str,            # "easy", "medium", or "hard"
        "split": str             # "train" or "validation"
    }

FEVER example (data/processed/fever.jsonl):
    {
        "id": int,
        "claim": str,
        "label": str,            # "SUPPORTS", "REFUTES", "NOT ENOUGH INFO"
        "evidence": [
            {"page": str, "sent_id": int}
        ],
        "split": str             # "train" or "dev"
    }
"""

import json
import sys
from pathlib import Path
from typing import Any

from loguru import logger

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.graph.wikidata_labels import label_for
RAW_DIR = ROOT / "data" / "raw"
PROC_DIR = ROOT / "data" / "processed"
PROC_DIR.mkdir(parents=True, exist_ok=True)

logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")


def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def save_jsonl(records: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# T-REx preprocessing
# relbert/t_rex raw record fields:
#   head, tail, relation, title, text
# relation is a template string e.g. "[X] was developed by [Y]"
# ---------------------------------------------------------------------------
def preprocess_trex() -> None:
    raw_path = RAW_DIR / "trex.jsonl"
    out_path = PROC_DIR / "trex_triplets.jsonl"

    if not raw_path.exists():
        logger.warning(f"T-REx raw file not found: {raw_path}. Skipping.")
        return

    if out_path.exists():
        logger.info(f"T-REx already preprocessed ({out_path}). Skipping.")
        return

    logger.info("Preprocessing T-REx...")
    raw = load_jsonl(raw_path)
    processed = []
    skipped = 0

    for i, rec in enumerate(raw):
        subject = (rec.get("head") or "").strip()
        obj = (rec.get("tail") or "").strip()
        relation = (rec.get("relation") or "").strip()
        # Most relbert/t_rex relations are bare Wikidata PIDs (P17, P54, ...),
        # which are opaque to LLM agents — map them to English labels.
        predicate_label = label_for(_template_to_predicate_label(relation))

        if not subject or not obj or not relation:
            skipped += 1
            continue

        processed.append({
            "id": f"trex_{i}",
            "subject": subject,
            "predicate": predicate_label,
            "object": obj,
            "predicate_id": relation if relation != predicate_label else "",
            "subject_uri": "",
            "object_uri": "",
            "source_text": (rec.get("text") or "")[:500],
            "source": "t-rex",
        })

    save_jsonl(processed, out_path)
    logger.success(
        f"T-REx: {len(processed):,} triplets saved → {out_path}  ({skipped} skipped)"
    )


def _template_to_predicate_label(template: str) -> str:
    """Clean a relation template like '[X] was born in [Y]' into 'was born in'."""
    label = template.replace("[X]", "").replace("[Y]", "")
    label = label.replace("[Artifact]", "").replace("[Type]", "")
    label = label.strip(" .")
    return " ".join(label.split()) or template


# ---------------------------------------------------------------------------
# HotpotQA preprocessing
# ---------------------------------------------------------------------------
def preprocess_hotpotqa() -> None:
    splits = {
        "train": RAW_DIR / "hotpotqa_train.jsonl",
        "validation": RAW_DIR / "hotpotqa_validation.jsonl",
    }
    out_path = PROC_DIR / "hotpotqa.jsonl"

    if out_path.exists():
        logger.info(f"HotpotQA already preprocessed ({out_path}). Skipping.")
        return

    missing = [s for s, p in splits.items() if not p.exists()]
    if missing:
        logger.warning(f"HotpotQA raw files missing for splits: {missing}. Skipping.")
        return

    logger.info("Preprocessing HotpotQA...")
    processed = []

    for split_name, raw_path in splits.items():
        raw = load_jsonl(raw_path)
        for rec in raw:
            # Normalize supporting_facts: list of [title, sent_idx] → list of dicts
            sf = rec.get("supporting_facts", {})
            if isinstance(sf, dict):
                titles = sf.get("title", [])
                sent_ids = sf.get("sent_id", [])
                supporting_facts = [
                    {"title": t, "sent_idx": s} for t, s in zip(titles, sent_ids)
                ]
            else:
                supporting_facts = [
                    {"title": item[0], "sent_idx": item[1]} for item in sf
                ]

            # Normalize context: list of [title, [sentences]] → list of dicts
            ctx = rec.get("context", {})
            if isinstance(ctx, dict):
                titles = ctx.get("title", [])
                sents = ctx.get("sentences", [])
                context = [
                    {"title": t, "sentences": s} for t, s in zip(titles, sents)
                ]
            else:
                context = [
                    {"title": item[0], "sentences": item[1]} for item in ctx
                ]

            processed.append({
                "id": rec.get("id", f"hotpot_{len(processed)}"),
                "question": rec.get("question", ""),
                "answer": rec.get("answer", ""),
                "supporting_facts": supporting_facts,
                "context": context,
                "type": rec.get("type", ""),
                "level": rec.get("level", ""),
                "split": split_name,
            })

    save_jsonl(processed, out_path)
    logger.success(f"HotpotQA: {len(processed):,} examples saved → {out_path}")


# ---------------------------------------------------------------------------
# FEVER preprocessing
# copenlu/fever_gold_evidence raw record fields:
#   id, claim, label, evidence (list of dicts with page/sent references),
#   verifiable, original_id
# ---------------------------------------------------------------------------
def preprocess_fever() -> None:
    splits = {
        "train": RAW_DIR / "fever_train.jsonl",
        "dev": RAW_DIR / "fever_dev.jsonl",
    }
    out_path = PROC_DIR / "fever.jsonl"

    if out_path.exists():
        logger.info(f"FEVER already preprocessed ({out_path}). Skipping.")
        return

    missing = [s for s, p in splits.items() if not p.exists()]
    if missing:
        logger.warning(f"FEVER raw files missing for splits: {missing}. Skipping.")
        return

    logger.info("Preprocessing FEVER...")
    processed = []

    label_map = {
        "SUPPORTS": "SUPPORTS",
        "REFUTES": "REFUTES",
        "NOT ENOUGH INFO": "NOT ENOUGH INFO",
        "NOT_ENOUGH_INFO": "NOT ENOUGH INFO",
        "REFUTED": "REFUTES",
    }

    for split_name, raw_path in splits.items():
        raw = load_jsonl(raw_path)
        for rec in raw:
            raw_label = rec.get("label", "NOT ENOUGH INFO")
            label = label_map.get(raw_label.upper(), "NOT ENOUGH INFO")

            # copenlu/fever_gold_evidence evidence field is a list of dicts or
            # a flat list — normalise to [{page, sent_id}] regardless
            evidence_raw = rec.get("evidence", [])
            evidence = _normalise_fever_evidence(evidence_raw)

            processed.append({
                "id": rec.get("original_id", rec.get("id", len(processed))),
                "claim": rec.get("claim", ""),
                "label": label,
                "evidence": evidence,
                "split": split_name,
            })

    save_jsonl(processed, out_path)
    logger.success(f"FEVER: {len(processed):,} examples saved → {out_path}")


def _normalise_fever_evidence(evidence_raw: Any) -> list[dict]:
    """Convert any evidence structure into [{page, sent_id}] list."""
    result = []
    if not evidence_raw:
        return result
    for item in evidence_raw:
        if isinstance(item, dict):
            page = item.get("page") or item.get("wiki_url") or item.get("evidence_wiki_url", "")
            sent_id = item.get("sent_id") or item.get("sentence_id") or item.get("evidence_sentence_id", 0)
            if page:
                result.append({"page": str(page), "sent_id": int(sent_id or 0)})
        elif isinstance(item, (list, tuple)) and len(item) >= 4 and item[2] is not None:
            result.append({"page": str(item[2]), "sent_id": int(item[3] or 0)})
    return result


def print_summary() -> None:
    logger.info("\n--- Processed Dataset Summary ---")
    for fname in sorted(PROC_DIR.glob("*.jsonl")):
        n = sum(1 for _ in open(fname, encoding="utf-8"))
        size_mb = fname.stat().st_size / 1e6
        logger.info(f"  {fname.name:<35} {n:>8,} records   {size_mb:>6.1f} MB")


if __name__ == "__main__":
    logger.info(f"Saving processed datasets to: {PROC_DIR}")
    preprocess_trex()
    preprocess_hotpotqa()
    preprocess_fever()
    print_summary()
    logger.success("Done. Ready for Phase 1.3 — Neo4j loading.")
