"""
Task #20 — offline validator-prompt tuning on the 40 human-calibrated labels.

The judge calibration (task #17) measured the Llama-8B fidelity judge at 10%
flag precision (2/20), and the same-grade ValidationAgent quarantines at
2-10% precision across the mitigated multi-seed (task #14). The oracle arm
(task #18) showed the Trio architecture contains the cascade (R0 = 0.79)
when judgement is perfect — validator precision is the RQ4 bottleneck.

This script measures whether prompt engineering alone (same model,
llama-3.1-8b-instant — the model is held fixed for comparability) moves
judge precision, using the 40 human-labeled rows from
results/summaries/phase34_judge_calibration_blind_v2.csv as the benchmark.

Prompt variants target the three failure modes documented in task #17:
  1. Specificity mismatch: triplets LESS specific than the passage flagged
     as UNSUPPORTED ("born_in 1977" vs "July 1977" in the passage).
  2. World-knowledge leakage: faithful extractions of world-false FEVER
     claims flagged (6/6 FEVER flags were this).
  3. Flag-happy default: ENTITY flags at 0/10 precision.

Variants:
  v0_original      — the exact audit_natural.py judge (anchor; replays from
                     the LLM cache at zero cost).
  v1_quote_gate    — error labels require quoting the contradicting passage
                     text; specificity + world-knowledge rules added.
  v2_quote_first   — v1 rules, but the JSON schema forces a passage_quote
                     field BEFORE the label (evidence-then-verdict ordering).
  v3_prior         — v2 plus an explicit base-rate prior (most triplets are
                     faithful; a false alarm costs as much as a miss).

Caveats recorded up front: n=40 with only 2 human-labeled errors, so recall
is measured on n=2 and precision estimates are coarse; all 40 rows are used
for selection (no held-out split at this n) — the confirmatory test is a
mitigated-arm rerun with the winning prompt, not this benchmark.

Usage:
    python scripts/tune_validator.py            # all variants
    python scripts/tune_validator.py --variants v1_quote_gate v3_prior
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

from loguru import logger

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from audit_natural import JUDGE_PROMPT, JUDGE_SYSTEM, LABELS  # noqa: E402

from src.agents.llm_client import ModelRole, get_client  # noqa: E402

logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

BLIND_V2 = ROOT / "results" / "summaries" / "phase34_judge_calibration_blind_v2.csv"
OUT_SUMMARY = ROOT / "results" / "summaries" / "phase39_validator_tuning.csv"
OUT_ROWS = ROOT / "results" / "raw" / "phase39_validator_tuning_rows.csv"

ERROR_LABELS = tuple(l for l in LABELS if l != "SUPPORTED")

# ---------------------------------------------------------------------------
# Prompt variants
# ---------------------------------------------------------------------------

_V1_SYSTEM = (
    "You audit knowledge-graph triplets extracted from text. Judge ONLY whether "
    "the triplet is faithful to the given passage — not whether it is true in "
    "the real world. If the passage itself asserts something false about the "
    "world and the triplet restates it, the triplet is SUPPORTED: you audit "
    "the extraction, not reality. Answer with a single JSON object and "
    "nothing else."
)

_V1_PROMPT = """Passage:
\"\"\"{text}\"\"\"

Extracted triplet:
  subject:   {subject}
  predicate: {predicate}
  object:    {object}

Classify the triplet against the passage with exactly one label:
- SUPPORTED: the passage states this fact. This INCLUDES triplets that are
  less specific than the passage (passage "July 1977", triplet "1977" —
  SUPPORTED), paraphrases, and predicates that reword the passage.
- QUALIFIER_LOSS: a temporal, spatial, or conditional qualifier in the
  passage was dropped AND its loss changes what the claim means.
- ENTITY_ERROR: the subject or object names a DIFFERENT entity than the
  passage supports (wrong person/place/work, two entities merged).
- RELATION_ERROR: the predicate misstates the relationship (weak association
  upgraded to strong/causal, reversed direction, wrong relation).
- UNSUPPORTED: the passage does not support this fact at all.

Rule: to use ANY label other than SUPPORTED you must be able to quote the
specific passage text the triplet contradicts or misrepresents, and put it
in "quote". If you cannot produce such a quote, the label is SUPPORTED.

Answer as JSON: {{"label": "<one of the five labels>", "quote": "<passage text, or empty for SUPPORTED>", "reason": "<one short sentence>"}}"""

_V2_SYSTEM = _V1_SYSTEM

_V2_PROMPT = """Passage:
\"\"\"{text}\"\"\"

Extracted triplet:
  subject:   {subject}
  predicate: {predicate}
  object:    {object}

Step 1 — find the passage text most relevant to this triplet and copy it
into "passage_quote" (verbatim, one clause or sentence).
Step 2 — compare the triplet with that quote only, and classify:
- SUPPORTED: the quote states the fact. Less-specific-but-consistent
  triplets are SUPPORTED (quote "July 1977", triplet "1977"). Paraphrase
  and reworded predicates are SUPPORTED.
- QUALIFIER_LOSS: the quote has a temporal/spatial/conditional qualifier
  the triplet dropped, and its loss changes the claim's meaning.
- ENTITY_ERROR: the triplet names a different entity than the quote.
- RELATION_ERROR: the triplet's predicate misstates the quote's relationship.
- UNSUPPORTED: no passage text relates to this triplet at all.

The triplet's real-world truth is irrelevant — a faithful extraction of a
false passage claim is SUPPORTED.

Answer as JSON, quote first:
{{"passage_quote": "<verbatim passage text>", "label": "<one of the five labels>", "reason": "<one short sentence>"}}"""

_V3_SYSTEM = _V1_SYSTEM

_V3_PROMPT = _V2_PROMPT.replace(
    "Answer as JSON, quote first:",
    """Calibration: in this audit more than 90% of triplets are faithful, and a
false alarm (flagging a faithful triplet) is exactly as costly as a miss.
When the comparison is ambiguous, answer SUPPORTED.

Answer as JSON, quote first:""",
)

VARIANTS: dict[str, tuple[str, str]] = {
    "v0_original":   (JUDGE_SYSTEM, JUDGE_PROMPT),
    "v1_quote_gate": (_V1_SYSTEM, _V1_PROMPT),
    "v2_quote_first": (_V2_SYSTEM, _V2_PROMPT),
    "v3_prior":      (_V3_SYSTEM, _V3_PROMPT),
}


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

def load_benchmark() -> list[dict]:
    # Excel re-saves this sheet as cp1252 (see thesis_log 2026-07-09).
    with open(BLIND_V2, encoding="cp1252") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        label = (r["human_label"] or "").strip().upper()
        if label not in LABELS:
            raise SystemExit(f"Unrecognised human label {label!r} for {r['triplet_id']}")
        r["human_label"] = label
    n_err = sum(r["human_label"] != "SUPPORTED" for r in rows)
    logger.info(f"Benchmark: {len(rows)} rows, {n_err} human-labeled errors")
    return rows


def parse_label(raw: str) -> str:
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).replace("```", "").strip()
    try:
        data = json.loads(cleaned)
        label = str(data.get("label", "")).strip().upper()
        if label in LABELS:
            return label
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    for label in LABELS:  # fallback: first label keyword present
        if label in cleaned.upper():
            return label
    return "PARSE_ERROR"


def score(rows: list[dict], preds: list[str]) -> dict:
    tp = fp = fn = tn = binary_agree = parse_errors = 0
    for r, pred in zip(rows, preds):
        human_err = r["human_label"] != "SUPPORTED"
        if pred == "PARSE_ERROR":
            parse_errors += 1
        pred_err = pred in ERROR_LABELS
        if pred_err and human_err:
            tp += 1
        elif pred_err:
            fp += 1
        elif human_err:
            fn += 1
        else:
            tn += 1
        binary_agree += pred_err == human_err
    flags = tp + fp
    return {
        "flags": flags, "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "flag_precision": round(tp / flags, 4) if flags else None,
        "recall_of_2": f"{tp}/{tp + fn}",
        "false_alarm_rate": round(fp / (fp + tn), 4) if (fp + tn) else None,
        "binary_agreement": round(binary_agree / len(rows), 4),
        "parse_errors": parse_errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline validator-prompt tuning (task #20)")
    parser.add_argument("--variants", nargs="*", default=list(VARIANTS),
                        help="Variant names to run (default: all)")
    parser.add_argument("--sleep", type=float, default=1.0)
    args = parser.parse_args()

    rows = load_benchmark()
    judge = get_client(ModelRole.ORCHESTRATION)

    all_rows_out: list[dict] = []
    summary: list[dict] = []

    for name in args.variants:
        system, template = VARIANTS[name]
        logger.info(f"=== variant {name} : {len(rows)} judgements ===")
        preds = []
        for r in rows:
            prompt = template.format(
                text=r["source_passage"], subject=r["subject"],
                predicate=r["predicate"], object=r["object"],
            )
            try:
                raw = judge.chat(prompt=prompt, system=system).content
            except Exception as exc:
                logger.warning(f"[{name}] LLM failure on {r['triplet_id']}: {exc}")
                raw = ""
            pred = parse_label(raw)
            preds.append(pred)
            all_rows_out.append({
                "variant": name, "triplet_id": r["triplet_id"],
                "dataset": r["dataset"], "human_label": r["human_label"],
                "pred_label": pred,
                "human_error": int(r["human_label"] != "SUPPORTED"),
                "pred_error": int(pred in ERROR_LABELS),
            })
            if args.sleep > 0:
                time.sleep(args.sleep)
        s = {"variant": name, **score(rows, preds)}
        summary.append(s)
        logger.success(f"{name}: {s}")

    with open(OUT_ROWS, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_rows_out[0].keys())
        writer.writeheader()
        writer.writerows(all_rows_out)
    with open(OUT_SUMMARY, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=summary[0].keys())
        writer.writeheader()
        writer.writerows(summary)

    logger.success(f"Rows    → {OUT_ROWS}")
    logger.success(f"Summary → {OUT_SUMMARY}")
    for s in summary:
        logger.info(f"  {s['variant']:>14}: precision={s['flag_precision']} "
                    f"flags={s['flags']} recall={s['recall_of_2']} "
                    f"false_alarms={s['fp']}/38 agree={s['binary_agreement']}")


if __name__ == "__main__":
    main()
