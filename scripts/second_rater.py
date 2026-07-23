"""
Task #25 - independent second-rater agreement study for the judge-calibration
labels (thesis Sec.5.6).

Second rater: open-mistral-nemo via the Mistral API (src.agents.llm_client,
ModelRole.EXTRACTION -> EXTRACTION_PROVIDER=mistral in .env). This is a
model family independent of both raters already in the record: the human
(task #17, Ashwin, blind) and the original judge being calibrated
(llama-3.1-8b-instant via Groq, ModelRole.ORCHESTRATION).

Rubric: reuses JUDGE_SYSTEM / JUDGE_PROMPT / LABELS imported verbatim from
audit_natural.py -- the exact 5-label fidelity rubric (SUPPORTED,
QUALIFIER_LOSS, ENTITY_ERROR, RELATION_ERROR, UNSUPPORTED) that produced
both the original judge verdicts and the human blind labels Ashwin scored
against (see scripts/tune_validator.py's "v0_original" variant, which
replays this same prompt as the calibration anchor). The second rater is
shown exactly what the human blind task showed: source_passage + subject /
predicate / object, nothing else (no human label, no judge label, no
reasoning from either prior rater).

File mapping (established by inspection 2026-07-23, see task #25 report):
  - results/summaries/phase34_judge_calibration_blind_v2.csv (cp1252 --
    Excel re-save changed the byte encoding of the passages; cp1252 decodes
    it correctly, verified byte-for-byte against a known char e.g. 0xE9 in
    "Jimenez"). This is the exact blind-task sheet: source_passage +
    subject/predicate/object (what the human rater was shown) + human_label
    (Ashwin's resolved blind labels, filled in after relabeling task #17).
    v1 (phase34_judge_calibration_blind.csv) lacked passages and was
    superseded -- not used here.
  - results/summaries/phase34_judge_calibration_results.csv (utf-8) --
    the scored join of judge_label (the original Llama-3.1-8b-instant judge
    verdict, identical to phase34_judge_calibration_key.csv's `label`
    column) against human_label, keyed by triplet_id. triplet_id sets in
    both files were verified identical (n=40) before writing this script.

Usage:
    python scripts/second_rater.py --smoke     # first 2 rows, no cache reuse
    python scripts/second_rater.py             # all 40 rows, writes outputs
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from datetime import date
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
JUDGE_RESULTS = ROOT / "results" / "summaries" / "phase34_judge_calibration_results.csv"
OUT_ROWS = ROOT / "results" / "raw" / "phase39_second_rater_rows.csv"
OUT_SUMMARY = ROOT / "results" / "summaries" / "phase39_second_rater.csv"

# Reminder appended on retry: makes the retry prompt bytes differ from the
# first attempt (so a temperature-0 response cache, if enabled, cannot just
# replay the same unparsable output) and nudges the model toward clean JSON.
_RETRY_SUFFIX = (
    " Respond with ONLY the JSON object on a single line -- no markdown "
    "fences, no prose before or after it."
)


def load_rows() -> list[dict]:
    """Join the blind-task sheet (passages + human labels) with the
    original judge verdicts, keyed by triplet_id."""
    with open(BLIND_V2, encoding="cp1252") as f:
        blind_rows = list(csv.DictReader(f))
    with open(JUDGE_RESULTS, encoding="utf-8") as f:
        judge_rows = {r["triplet_id"]: r["judge_label"] for r in csv.DictReader(f)}

    missing = [r["triplet_id"] for r in blind_rows if r["triplet_id"] not in judge_rows]
    if missing:
        raise SystemExit(f"{len(missing)} triplet_ids in blind_v2 have no judge verdict: {missing}")

    rows = []
    for r in blind_rows:
        human_label = (r["human_label"] or "").strip().upper()
        if human_label not in LABELS:
            raise SystemExit(f"Unrecognised human label {human_label!r} for {r['triplet_id']}")
        rows.append({
            "triplet_id": r["triplet_id"],
            "dataset": r["dataset"],
            "source_passage": r["source_passage"],
            "subject": r["subject"],
            "predicate": r["predicate"],
            "object": r["object"],
            "human_label": human_label,
            "judge_label": judge_rows[r["triplet_id"]].strip().upper(),
        })
    logger.info(f"Loaded {len(rows)} rows (blind_v2 x judge_results, joined on triplet_id)")
    return rows


def parse_response(raw: str) -> tuple[str, str]:
    """Extract (label, reason) from a JSON-ish model response. Falls back
    to a keyword scan; returns ('PARSE_ERROR', <raw excerpt>) if nothing
    recognisable is found."""
    cleaned = re.sub(r"```(?:json)?\s*", "", raw or "").replace("```", "").strip()
    try:
        data = json.loads(cleaned)
        label = str(data.get("label", "")).strip().upper()
        reason = str(data.get("reason", "")).strip()
        if label in LABELS:
            return label, reason
    except (json.JSONDecodeError, ValueError, TypeError, AttributeError):
        pass
    upper = cleaned.upper()
    for label in LABELS:  # fallback: first label keyword present in the raw text
        if label in upper:
            return label, ""
    return "PARSE_ERROR", (raw or "")[:200]


def rate_row(client, r: dict) -> dict:
    """Call the second-rater LLM on one row, with a retry-once fallback on
    unparsable output."""
    prompt = JUDGE_PROMPT.format(
        text=r["source_passage"], subject=r["subject"],
        predicate=r["predicate"], object=r["object"],
    )
    attempts = 1
    try:
        raw = client.chat(prompt=prompt, system=JUDGE_SYSTEM).content
    except Exception as exc:
        logger.warning(f"[second_rater] LLM call failed on {r['triplet_id']}: {exc}")
        raw = ""
    label, reason = parse_response(raw)

    if label == "PARSE_ERROR":
        attempts = 2
        logger.warning(f"[second_rater] unparsable response for {r['triplet_id']}, retrying once")
        try:
            raw2 = client.chat(prompt=prompt, system=JUDGE_SYSTEM + _RETRY_SUFFIX).content
        except Exception as exc:
            logger.warning(f"[second_rater] retry LLM call failed on {r['triplet_id']}: {exc}")
            raw2 = ""
        label2, reason2 = parse_response(raw2)
        if label2 != "PARSE_ERROR":
            raw, label, reason = raw2, label2, reason2
        else:
            raw = raw2 or raw  # keep the most recent (still-broken) output for audit

    return {
        "triplet_id": r["triplet_id"],
        "dataset": r["dataset"],
        "subject": r["subject"],
        "predicate": r["predicate"],
        "object": r["object"],
        "human_label": r["human_label"],
        "judge_label": r["judge_label"],
        "second_rater_label": label,
        "second_rater_reason": reason,
        "parse_error": int(label == "PARSE_ERROR"),
        "attempts": attempts,
        "agree_with_human": int(label == r["human_label"]),
        "agree_with_judge": int(label == r["judge_label"]),
        "raw_response_excerpt": (raw or "")[:300],
    }


# ---------------------------------------------------------------------------
# Cohen's kappa (implemented directly -- no sklearn dependency)
# ---------------------------------------------------------------------------

def cohen_kappa(labels_a: list[str], labels_b: list[str]) -> dict:
    """Cohen's kappa between two label sequences of equal length, plus raw
    observed/expected agreement. Categories = union of labels seen."""
    assert len(labels_a) == len(labels_b), "label sequences must be equal length"
    n = len(labels_a)
    categories = sorted(set(labels_a) | set(labels_b))
    idx = {c: i for i, c in enumerate(categories)}
    k = len(categories)
    mat = [[0] * k for _ in range(k)]
    for a, b in zip(labels_a, labels_b):
        mat[idx[a]][idx[b]] += 1

    po = sum(mat[i][i] for i in range(k)) / n
    row_totals = [sum(mat[i][j] for j in range(k)) for i in range(k)]
    col_totals = [sum(mat[i][j] for i in range(k)) for j in range(k)]
    pe = sum(row_totals[i] * col_totals[i] for i in range(k)) / (n * n)

    if pe >= 1.0:
        kappa = 1.0 if po >= 1.0 else 0.0  # degenerate: only one category seen everywhere
    else:
        kappa = (po - pe) / (1 - pe)

    return {
        "n": n,
        "kappa": round(kappa, 4),
        "percent_agreement": round(po, 4),
        "expected_agreement": round(pe, 4),
        "categories": ",".join(categories),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Second-rater (open-mistral-nemo) agreement study (task #25)")
    parser.add_argument("--smoke", action="store_true", help="Only rate the first 2 rows; do not overwrite final outputs.")
    parser.add_argument("--sleep", type=float, default=1.0)
    args = parser.parse_args()

    rows = load_rows()
    if args.smoke:
        rows = rows[:2]
        logger.info(f"SMOKE TEST: rating {len(rows)} rows only")

    client = get_client(ModelRole.EXTRACTION)
    logger.info(f"Second rater: provider={client.provider} model={client.model}")

    out_rows = []
    for i, r in enumerate(rows, 1):
        result = rate_row(client, r)
        out_rows.append(result)
        logger.info(
            f"[{i}/{len(rows)}] {r['triplet_id'][:8]} human={result['human_label']:<15} "
            f"judge={result['judge_label']:<15} second={result['second_rater_label']:<15} "
            f"parse_error={result['parse_error']} attempts={result['attempts']}"
        )
        if args.sleep > 0 and i < len(rows):
            time.sleep(args.sleep)

    valid = [r for r in out_rows if not r["parse_error"]]
    parse_errors = len(out_rows) - len(valid)
    logger.info(f"Done: {len(out_rows)} rows, {parse_errors} parse errors, {len(valid)} usable for kappa")

    vs_human = cohen_kappa([r["human_label"] for r in valid], [r["second_rater_label"] for r in valid]) if valid else None
    vs_judge = cohen_kappa([r["judge_label"] for r in valid], [r["second_rater_label"] for r in valid]) if valid else None

    if vs_human:
        logger.success(f"second_rater vs human : kappa={vs_human['kappa']} agreement={vs_human['percent_agreement']} n={vs_human['n']}")
    if vs_judge:
        logger.success(f"second_rater vs judge : kappa={vs_judge['kappa']} agreement={vs_judge['percent_agreement']} n={vs_judge['n']}")

    row_suffix = "_smoke" if args.smoke else ""
    out_rows_path = OUT_ROWS.with_name(OUT_ROWS.stem + row_suffix + OUT_ROWS.suffix)
    out_summary_path = OUT_SUMMARY.with_name(OUT_SUMMARY.stem + row_suffix + OUT_SUMMARY.suffix)

    with open(out_rows_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_rows[0].keys())
        writer.writeheader()
        writer.writerows(out_rows)

    summary_records = []
    today = date.today().isoformat()
    for comparison, res in (("second_rater_vs_human", vs_human), ("second_rater_vs_judge", vs_judge)):
        if res is None:
            continue
        summary_records.append({
            "comparison": comparison,
            "kappa": res["kappa"],
            "percent_agreement": res["percent_agreement"],
            "expected_agreement": res["expected_agreement"],
            "n_total_rows": len(out_rows),
            "n_used_for_kappa": res["n"],
            "parse_errors": parse_errors,
            "categories": res["categories"],
            "second_rater_provider": client.provider,
            "second_rater_model": client.model,
            "original_judge_model": "llama-3.1-8b-instant (Groq, ModelRole.ORCHESTRATION)",
            "human_rater": "Ashwin Jayan (thesis author, blind, task #17)",
            "rubric_source": "audit_natural.JUDGE_SYSTEM / JUDGE_PROMPT (5-label fidelity taxonomy)",
            "date": today,
        })

    if summary_records:
        with open(out_summary_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=summary_records[0].keys())
            writer.writeheader()
            writer.writerows(summary_records)

    logger.success(f"Rows    -> {out_rows_path}")
    logger.success(f"Summary -> {out_summary_path}")


if __name__ == "__main__":
    main()
