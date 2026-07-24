"""
Propagation replay probe (task #33 / scale re-evaluation, 2026-07-24).

The external-validity question "would a bigger model also trust and reproduce a
contaminated fact retrieved from shared memory?" is confounded if answered by
swapping the synthesis model inside a live run (different model => different
prose, triplet volume, entity coverage; beta shifts through many channels).
The clean instrument holds the *input* fixed and varies only the model.

`run_contamination.py --log-prompts` archives, for every synthesis unit, the
verbatim (system, prompt, served context_facts, Nemo's paragraph, propagation
outcome). This probe replays the subset where a CONTAMINATED fact was in the
served context (n_contam > 0) through an arbitrary larger model and measures
whether that model reproduces the served corrupted value in its paragraph —
the identical string-containment measure applied to Nemo's own logged
paragraph, so the comparison is apples-to-apples with context held constant.

Reproduction measure (first-order, reproducible, conservative): a served
contaminated fact (subject, predicate, OBJECT) is "reproduced" if its object
string appears (case-insensitive) in the generated paragraph. This mirrors
what would then be extracted as a propagated triplet, without the confound of
the extraction step; a model that paraphrases the value away is scored as not
reproducing (conservative). The archived `propagated` field (Nemo's actual
post-extraction transmission) is carried through as a cross-check on the proxy.

Usage (from project root, venv active):
    python scripts/replay_propagation.py --model open-mistral-nemo   --provider mistral --tag nemo12b
    python scripts/replay_propagation.py --model llama-3.3-70b-versatile --provider groq --tag llama70b
    python scripts/replay_propagation.py --model mistral-large-latest --provider mistral --tag mistral-large
Then aggregate the per-model CSVs (reproduction_rate column) into the scale ladder.
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from loguru import logger

from src.agents.llm_client import _GroqClient, _MistralClient, _OllamaClient

RAW_DIR = ROOT / "results" / "raw"
SUMMARIES_DIR = ROOT / "results" / "summaries"

logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")


def build_client(provider: str, model: str):
    if provider == "groq":
        return _GroqClient(model)
    if provider == "mistral":
        return _MistralClient(model)
    if provider == "ollama":
        return _OllamaClient(model)
    raise ValueError(f"unknown provider {provider!r} (groq|mistral|ollama)")


def corrupted_values(record: dict) -> list[str]:
    """Objects of the served contaminated facts — the values whose reappearance
    in a paragraph constitutes reproducing the contaminated claim."""
    vals = []
    for f in record.get("context_facts", []):
        if f.get("error_type"):
            obj = str(f.get("object", "")).strip()
            if obj:
                vals.append(obj)
    return vals


def reproduced(paragraph: str, values: list[str]) -> bool:
    p = (paragraph or "").lower()
    return any(v.lower() in p for v in values)


def load_corpus(patterns: list[str]) -> list[dict]:
    paths: list[Path] = []
    for pat in patterns:
        p = Path(pat)
        paths.extend([p] if p.is_absolute() and p.exists()
                     else sorted(RAW_DIR.glob(pat)))
    records = []
    for path in paths:
        arm = path.stem.replace("contamination_prompts_", "")
        with open(path, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if r.get("n_contam", 0) > 0:   # only transmission-opportunity contexts
                    r["_arm"] = arm
                    records.append(r)
    return records


def main() -> None:
    ap = argparse.ArgumentParser(description="Replay contaminated-context synthesis through a chosen model.")
    ap.add_argument("--corpus", nargs="*", default=["contamination_prompts_*.jsonl"],
                    help="Glob(s) under results/raw for the prompt corpus.")
    ap.add_argument("--model", required=True, help="Model id to replay (e.g. llama-3.3-70b-versatile).")
    ap.add_argument("--provider", required=True, choices=["groq", "mistral", "ollama"])
    ap.add_argument("--tag", required=True, help="Short label for the output file + rows.")
    ap.add_argument("--limit", type=int, default=0, help="Max records (0 = all).")
    ap.add_argument("--sleep", type=float, default=1.0, help="Seconds between calls.")
    ap.add_argument("--output", type=str, default=None)
    args = ap.parse_args()

    records = load_corpus(args.corpus)
    if args.limit:
        records = records[:args.limit]
    if not records:
        logger.error("No contaminated-context (n_contam>0) records found. "
                     "Have the in-subgraph arms (wf/rd/density) finished with --log-prompts?")
        sys.exit(1)
    logger.info(f"Replaying {len(records)} contaminated-context records through "
                f"{args.provider}:{args.model}")

    client = build_client(args.provider, args.model)
    out_path = Path(args.output) if args.output else (
        SUMMARIES_DIR / f"replay_propagation_{args.tag}.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows, n_model_repro, n_nemo_repro, n_fail = [], 0, 0, 0
    for i, r in enumerate(records):
        vals = corrupted_values(r)
        if not vals:
            continue
        nemo_repro = reproduced(r.get("paragraph", ""), vals)
        try:
            para_x = client.chat(prompt=r["prompt"], system=r["system"]).content
        except Exception as exc:            # rate limit / transient — record, keep going
            logger.warning(f"[{i+1}/{len(records)}] replay failed: {exc}")
            n_fail += 1
            para_x = ""
            model_repro = None
        else:
            model_repro = reproduced(para_x, vals)
            if model_repro:
                n_model_repro += 1
        if nemo_repro:
            n_nemo_repro += 1
        rows.append({
            "arm": r["_arm"], "step": r["step"], "key": r["key"],
            "n_contam": r["n_contam"],
            "corrupted_values": " | ".join(vals),
            "nemo_reproduced": int(nemo_repro),
            "nemo_propagated": r.get("propagated", 0),
            "model_reproduced": "" if model_repro is None else int(model_repro),
            "model_paragraph": (para_x or "").replace("\n", " ")[:500],
        })
        if args.sleep > 0:
            time.sleep(args.sleep)
        if (i + 1) % 20 == 0:
            logger.info(f"  {i+1}/{len(records)} done")

    scored = [r for r in rows if r["model_reproduced"] != ""]
    model_rate = (sum(int(r["model_reproduced"]) for r in scored) / len(scored)) if scored else float("nan")
    nemo_rate = (n_nemo_repro / len(rows)) if rows else float("nan")

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    logger.success(
        f"{args.tag}: model reproduction {model_rate:.3f} ({len(scored)} scored) "
        f"vs Nemo {nemo_rate:.3f} on the same {len(rows)} contexts "
        f"({n_fail} calls failed). -> {out_path.name}")


if __name__ == "__main__":
    main()
