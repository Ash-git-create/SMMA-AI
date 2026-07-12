"""
Phase 2.2 — baseline task-performance measurement against the KG.

For each sampled task, facts are retrieved from the KG (entities mentioned in
the question/claim), and the orchestration LLM must answer USING ONLY those
facts. Task performance therefore reflects the state of the KG: as the KG
contaminates in later phases, these same measurements degrade — that
degradation curve is the headline task-performance result.

  HotpotQA (validation split) → Exact Match + token F1
  FEVER (dev split)           → Veracity Accuracy (SUPPORTS/REFUTES/NEI)

Read-only: never writes to the KG.

Run from project root with venv active:
    python scripts/run_baseline_eval.py --config experiments/configs/eval_baseline.yaml
    python scripts/run_baseline_eval.py --dataset fever --num-questions 10
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

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.agents.llm_client import ModelRole, get_client
from src.evaluation.metrics import (
    answer_traceable,
    exact_match,
    normalize_answer,
    token_f1,
    veracity_report,
)
from src.graph.neo4j_client import Neo4jClient

logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

PROC_DIR = ROOT / "data" / "processed"
RESULTS_DIR = ROOT / "results" / "raw"

_QA_SYSTEM = """\
You answer questions using ONLY the knowledge-graph facts provided.

Respond ONLY with a JSON object — no prose:
{"answer": "<short answer span, a few words at most>"}

Rules:
- Base the answer strictly on the provided facts. Do not use outside knowledge.
- Answer with the shortest span that answers the question (a name, date, place).
- If the facts do not contain the answer, respond {"answer": "unknown"}.
"""

_FEVER_SYSTEM = """\
You are a claim verifier. Judge the claim using ONLY the knowledge-graph facts
provided.

Respond ONLY with a JSON object — no prose:
{"label": "SUPPORTS" | "REFUTES" | "NOT ENOUGH INFO"}

Rules:
- SUPPORTS: the facts entail the claim.
- REFUTES: the facts contradict the claim.
- NOT ENOUGH INFO: the facts neither entail nor contradict it.
- Do not use outside knowledge — judge only against the provided facts.
"""

_STOP_STARTERS = {
    "What", "Which", "Who", "Whom", "Whose", "Where", "When", "Why", "How",
    "Is", "Are", "Was", "Were", "Did", "Do", "Does", "The", "A", "An", "In",
    "On", "It", "There", "This", "That", "Both",
}


def entity_keys(text: str, max_keys: int = 4) -> list[str]:
    """Capitalized token runs in the text — used as KG retrieval keys."""
    runs = re.findall(r"(?:[A-Z][\w'’\-\.]*)(?:\s+[A-Z][\w'’\-\.]*)*", text)
    keys = []
    for run in runs:
        run = run.strip(".")
        if run in _STOP_STARTERS or len(run) < 3:
            continue
        # drop a leading question/stop word from the run ("Which Arthur" → "Arthur")
        parts = run.split()
        if parts[0] in _STOP_STARTERS and len(parts) > 1:
            run = " ".join(parts[1:])
        if run and run not in keys:
            keys.append(run)
    return keys[:max_keys]


def retrieve_facts(client: Neo4jClient, keys: list[str], per_key: int,
                   cap: int = 15, min_confidence: float = 0.0) -> list[dict]:
    """min_confidence is the Trio retrieval floor — 0.0 in the unmitigated
    baseline; mitigated runs raise it so the evaluator (itself an agent
    reading the shared memory) honors the same floor as the pipeline."""
    facts, seen = [], set()
    for key in keys:
        for t in client.get_related_triplets(subject=key, obj=key,
                                             exclude_id="", limit=per_key,
                                             min_confidence=min_confidence):
            if t["id"] not in seen:
                seen.add(t["id"])
                facts.append(t)
    return facts[:cap]


def facts_block(facts: list[dict]) -> str:
    if not facts:
        return "  (no facts found)"
    return "\n".join(
        f"  - ({t['subject']}) --[{t['predicate']}]--> ({t['object']})" for t in facts
    )


def parse_json_response(content: str) -> dict | None:
    cleaned = re.sub(r"```(?:json)?\s*", "", content).replace("```", "").strip()
    try:
        data = json.loads(cleaned)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def load_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def eval_hotpotqa(client, llm, args, rng) -> dict:
    docs = [d for d in load_jsonl(PROC_DIR / "hotpotqa.jsonl") if d.get("split") == "validation"]
    docs = rng.sample(docs, min(args.num_questions, len(docs)))
    rows, parse_failures = [], 0

    for i, doc in enumerate(docs, 1):
        keys = entity_keys(doc["question"])
        facts = retrieve_facts(client, keys, args.facts_per_key,
                               min_confidence=getattr(args, "retrieval_threshold", 0.0))
        prompt = (f"Knowledge-graph facts:\n{facts_block(facts)}\n\n"
                  f"Question: {doc['question']}")
        try:
            resp = llm.chat(prompt=prompt, system=_QA_SYSTEM)
            parsed = parse_json_response(resp.content)
        except Exception as exc:
            logger.warning(f"LLM failure on {doc['id']}: {exc}")
            parsed = None
        if parsed is None or "answer" not in parsed:
            parse_failures += 1
            predicted = ""
        else:
            predicted = str(parsed["answer"])

        # USR (task #16): mechanical grounding of the answer span against the
        # facts actually retrieved for this question — no LLM, no extra calls.
        # None = non-groundable (abstention/boolean), excluded from the ratio.
        traceable = answer_traceable(predicted, facts)
        rows.append({
            "id":        doc["id"],
            "question":  doc["question"][:120],
            "gold":      doc["answer"],
            "predicted": predicted,
            "em":        exact_match(predicted, doc["answer"]),
            "f1":        round(token_f1(predicted, doc["answer"]), 4),
            "n_facts":   len(facts),
            "traceable": "" if traceable is None else int(traceable),
        })
        logger.info(f"[hotpot {i}/{len(docs)}] em={rows[-1]['em']} f1={rows[-1]['f1']:.2f} "
                    f"facts={len(facts)} | {doc['question'][:60]}")
        if args.sleep > 0:
            time.sleep(args.sleep)

    n = len(rows)
    groundable = [r for r in rows if r["traceable"] != ""]
    n_g = len(groundable)
    return {
        "dataset":        "hotpotqa",
        "n":              n,
        "exact_match":    round(sum(r["em"] for r in rows) / n, 4) if n else 0.0,
        "f1":             round(sum(r["f1"] for r in rows) / n, 4) if n else 0.0,
        "avg_facts":      round(sum(r["n_facts"] for r in rows) / n, 2) if n else 0.0,
        # usr = share of substantive answers NOT traceable to a retrieved
        # fact; usr_n is its denominator (answers minus abstentions/booleans).
        "usr":            round(sum(1 for r in groundable if not r["traceable"]) / n_g, 4) if n_g else None,
        "usr_n":          n_g,
        "abstain_rate":   round(sum(1 for r in rows if normalize_answer(r["predicted"]) in ("", "unknown")) / n, 4) if n else 0.0,
        "parse_failures": parse_failures,
        "rows":           rows,
    }


def eval_fever(client, llm, args, rng) -> dict:
    docs = [d for d in load_jsonl(PROC_DIR / "fever.jsonl") if d.get("split") == "dev"]
    if not docs:  # some FEVER exports only carry a train split
        docs = load_jsonl(PROC_DIR / "fever.jsonl")
    docs = rng.sample(docs, min(args.num_questions, len(docs)))
    rows, preds, golds, parse_failures = [], [], [], 0

    for i, doc in enumerate(docs, 1):
        keys = entity_keys(doc["claim"])
        facts = retrieve_facts(client, keys, args.facts_per_key,
                               min_confidence=getattr(args, "retrieval_threshold", 0.0))
        prompt = (f"Knowledge-graph facts:\n{facts_block(facts)}\n\n"
                  f"Claim: {doc['claim']}")
        try:
            resp = llm.chat(prompt=prompt, system=_FEVER_SYSTEM)
            parsed = parse_json_response(resp.content)
        except Exception as exc:
            logger.warning(f"LLM failure on {doc['id']}: {exc}")
            parsed = None
        if parsed is None or "label" not in parsed:
            parse_failures += 1
            label = "NOT ENOUGH INFO"
        else:
            label = str(parsed["label"]).upper().strip()

        preds.append(label)
        golds.append(doc["label"])
        rows.append({
            "id":        doc["id"],
            "claim":     doc["claim"][:120],
            "gold":      doc["label"],
            "predicted": label,
            "correct":   int(label == doc["label"]),
            "n_facts":   len(facts),
        })
        logger.info(f"[fever {i}/{len(docs)}] {label} vs {doc['label']} "
                    f"facts={len(facts)} | {doc['claim'][:60]}")
        if args.sleep > 0:
            time.sleep(args.sleep)

    report = veracity_report(preds, golds)
    report.update({
        "dataset":        "fever",
        "avg_facts":      round(sum(r["n_facts"] for r in rows) / len(rows), 2) if rows else 0.0,
        "parse_failures": parse_failures,
        "rows":           rows,
    })
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 2.2 baseline evaluation")
    parser.add_argument("--config",        type=str,   default=None)
    parser.add_argument("--dataset",       type=str,   default="both", choices=["hotpotqa", "fever", "both"])
    parser.add_argument("--num-questions", type=int,   default=50, help="Tasks sampled per dataset")
    parser.add_argument("--facts-per-key", type=int,   default=5,  help="KG facts retrieved per entity key")
    parser.add_argument("--random-seed",   type=int,   default=42)
    parser.add_argument("--sleep",         type=float, default=1.0)
    parser.add_argument("--tag",           type=str,   default="baseline", help="Run label in output filenames")

    pre_args, _ = parser.parse_known_args()
    if pre_args.config:
        from src.config import load_config
        cfg = load_config(pre_args.config)
        known = {a.dest for a in parser._actions}
        parser.set_defaults(**{k: v for k, v in cfg.items() if k in known})
    args = parser.parse_args()

    rng = random.Random(args.random_seed)
    llm = get_client(ModelRole.ORCHESTRATION)
    logger.info(f"=== Phase 2.2 Baseline Evaluation === (tag={args.tag}, seed={args.random_seed})")

    results = []
    with Neo4jClient() as client:
        if args.dataset in ("hotpotqa", "both"):
            results.append(eval_hotpotqa(client, llm, args, rng))
        if args.dataset in ("fever", "both"):
            results.append(eval_fever(client, llm, args, rng))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    for res in results:
        rows = res.pop("rows")
        rows_path = RESULTS_DIR / f"eval_{res['dataset']}_{args.tag}_{ts}.csv"
        with open(rows_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        summary_path = RESULTS_DIR / f"eval_{res['dataset']}_{args.tag}_{ts}_summary.json"
        summary_path.write_text(json.dumps(res, indent=2), encoding="utf-8")
        logger.success(f"{res['dataset']}: {json.dumps({k: v for k, v in res.items() if k != 'confusion'})}")
        logger.info(f"  rows → {rows_path.name}, summary → {summary_path.name}")


if __name__ == "__main__":
    main()
