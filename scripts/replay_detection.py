"""
Detection replay probe (task #33 / scale re-evaluation, 2026-07-24) — the
DETECTION half of the model-scale question, complementing replay_propagation.py.

RQ4 found the in-run 8B judge (llama-3.1-8b-instant) catches contaminated nodes
at ~6% recall, and argued the blindness is STRUCTURAL: replacement contamination
leaves no contradicting evidence in the KG for an evidence-gated judge to quote
(§5.4.3). A frontier judge adds a WORLD-KNOWLEDGE channel the 8B lacks — it may
know the corrupted fact is false independent of the KG. Does that recover recall?

This holds the judge INPUT fixed and varies only the judge model. The propagation
corpus (run_contamination.py --log-prompts) already contains, for every served
contaminated fact, its co-served KG neighbours — exactly the (target triplet +
related evidence) the validator's OrchestrationAgent.validate_triplet feeds its
judge. Each of the 154 unique contaminated triplets is replayed through the
IDENTICAL validator system prompt and candidate/evidence format (imported from
orchestration_agent, not paraphrased), and "caught" is scored the run's way:
verdict == UNSUPPORTED (equivalently confidence < the 0.4 quarantine threshold).

Recall = caught / total-contaminated. Baseline: run --provider groq
--model llama-3.1-8b-instant to reproduce the in-run judge on these same inputs;
then the Claude ladder. Reproduces the structural-blindness test at frontier
scale WITHOUT re-running Neo4j.

Usage:
    python scripts/replay_detection.py --model llama-3.1-8b-instant --provider groq --tag judge_llama8b
    python scripts/replay_detection.py --model claude-haiku-4-5 --provider anthropic --tag judge_haiku45
    python scripts/replay_detection.py --model claude-sonnet-5  --provider anthropic --tag judge_sonnet5
    python scripts/replay_detection.py --model claude-opus-4-8  --provider anthropic --tag judge_opus48
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import time
from loguru import logger

from scripts.replay_propagation import build_client, load_corpus
from src.agents.orchestration_agent import _SYSTEM_PROMPT   # the REAL validator prompt

SUMMARIES_DIR = ROOT / "results" / "summaries"
QUARANTINE_THRESHOLD = 0.4   # run default: conf < 0.4 => flagged/quarantined

logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")


def collect_targets(patterns: list[str], seed: int = 42) -> list[dict]:
    """Balanced detection set: every unique CONTAMINATED triplet plus a matched
    random sample of CLEAN triplets, each with its co-served neighbours as
    evidence (the validator's target + evidence). Recall is scored on the
    contaminated half, false-positive rate on the clean half — a judge that
    flags everything gets recall 1.0 but FPR 1.0, so both are needed to say it
    DETECTS rather than just distrusts. Deduped by triplet id."""
    import random
    recs = load_corpus(patterns)
    contam: dict[str, dict] = {}
    clean_pool: dict[str, dict] = {}
    for r in recs:
        cf_contam = [f for f in r["context_facts"] if f.get("error_type")]
        cf_clean = [f for f in r["context_facts"] if not f.get("error_type")]
        for cf in cf_contam:
            others = [x for x in r["context_facts"] if x["id"] != cf["id"]]
            tid = cf["id"]
            if tid not in contam or len(others) > len(contam[tid]["evidence"]):
                contam[tid] = {"target": cf, "evidence": others,
                               "error_type": cf["error_type"], "is_contam": 1}
        for cf in cf_clean:
            others = [x for x in r["context_facts"] if x["id"] != cf["id"]]
            tid = cf["id"]
            if tid not in clean_pool or len(others) > len(clean_pool[tid]["evidence"]):
                clean_pool[tid] = {"target": cf, "evidence": others,
                                   "error_type": "clean", "is_contam": 0}
    contam_list = list(contam.values())
    # match clean count to contaminated count (never exceed the pool)
    clean_candidates = [c for c in clean_pool.values() if c["target"]["id"] not in contam]
    random.Random(seed).shuffle(clean_candidates)
    clean_list = clean_candidates[:len(contam_list)]
    return contam_list + clean_list


def judge_prompt(target: dict, evidence: list[dict]) -> str:
    """Byte-identical to OrchestrationAgent._call_llm's user prompt."""
    ctx = "\n".join(
        f"  - ({t['subject']}) --[{t['predicate']}]--> ({t['object']})"
        for t in evidence[:20]
    )
    return (
        f"Candidate fact:\n"
        f"  ({target['subject']}) --[{target['predicate']}]--> ({target['object']})\n\n"
        f"Evidence from knowledge graph:\n{ctx or '  (none)'}\n\n"
        f"Is the candidate fact supported by this evidence?"
    )


def parse_verdict(content: str) -> tuple[str, float]:
    cleaned = re.sub(r"```(?:json)?\s*", "", content).replace("```", "").strip()
    try:
        d = json.loads(cleaned)
        v = d.get("verdict", "UNCERTAIN")
        if v not in ("SUPPORTED", "UNSUPPORTED", "UNCERTAIN"):
            v = "UNCERTAIN"
        c = max(0.0, min(1.0, float(d.get("confidence", 0.5))))
        return v, c
    except Exception:
        return "PARSE_ERROR", 0.5


def main() -> None:
    ap = argparse.ArgumentParser(description="Replay contaminated-triplet detection through a chosen judge model.")
    ap.add_argument("--corpus", nargs="*", default=["contamination_prompts_*.jsonl"])
    ap.add_argument("--model", required=True)
    ap.add_argument("--provider", required=True, choices=["groq", "mistral", "anthropic", "ollama"])
    ap.add_argument("--tag", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=0.5)
    ap.add_argument("--output", type=str, default=None)
    args = ap.parse_args()

    targets = collect_targets(args.corpus)
    if args.limit:
        targets = targets[:args.limit]
    if not targets:
        logger.error("No contaminated targets found — run the --log-prompts arms first.")
        sys.exit(1)
    logger.info(f"Detection replay: {len(targets)} unique contaminated triplets through "
                f"{args.provider}:{args.model} (verdict==UNSUPPORTED or conf<{QUARANTINE_THRESHOLD} = caught)")

    client = build_client(args.provider, args.model)
    out_path = Path(args.output) if args.output else (SUMMARIES_DIR / f"replay_detection_{args.tag}.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows, caught, n_fail = [], 0, 0
    for i, t in enumerate(targets):
        p = judge_prompt(t["target"], t["evidence"])
        try:
            content = client.chat(prompt=p, system=_SYSTEM_PROMPT).content
        except Exception as exc:
            logger.warning(f"[{i+1}/{len(targets)}] judge call failed: {exc}")
            n_fail += 1
            verdict, conf = "CALL_ERROR", 0.5
        else:
            verdict, conf = parse_verdict(content)
        is_caught = (verdict == "UNSUPPORTED") or (conf < QUARANTINE_THRESHOLD and verdict != "CALL_ERROR")
        rows.append({
            "triplet_id": t["target"]["id"], "is_contam": t["is_contam"],
            "error_type": t["error_type"],
            "subject": t["target"]["subject"], "predicate": t["target"]["predicate"],
            "object": t["target"]["object"], "n_evidence": len(t["evidence"]),
            "verdict": verdict, "confidence": round(conf, 3), "caught": int(is_caught),
        })
        if args.sleep > 0:
            time.sleep(args.sleep)
        if (i + 1) % 50 == 0:
            logger.info(f"  {i+1}/{len(targets)} done")

    scored = [r for r in rows if r["verdict"] != "CALL_ERROR"]
    contam = [r for r in scored if r["is_contam"] == 1]
    clean = [r for r in scored if r["is_contam"] == 0]
    recall = sum(r["caught"] for r in contam) / len(contam) if contam else float("nan")   # TP rate on contaminated
    fpr = sum(r["caught"] for r in clean) / len(clean) if clean else float("nan")          # flags on clean
    # recall by contamination type
    from collections import defaultdict
    bt = defaultdict(lambda: [0, 0])
    for r in contam:
        bt[r["error_type"]][0] += r["caught"]; bt[r["error_type"]][1] += 1

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    by = "  ".join(f"{k}={c}/{n}" for k, (c, n) in sorted(bt.items()))
    logger.success(
        f"{args.tag}: recall {recall:.3f} ({sum(r['caught'] for r in contam)}/{len(contam)}) | "
        f"clean false-flag rate {fpr:.3f} ({sum(r['caught'] for r in clean)}/{len(clean)}) | "
        f"discrimination (recall-FPR) {recall-fpr:+.3f} | {n_fail} calls failed -> {out_path.name}\n"
        f"  recall by type: {by}")


if __name__ == "__main__":
    main()
