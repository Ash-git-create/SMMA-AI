"""
Phase 2.4 — contamination-over-time experiment (the cascade measurement).

The first measurement sequence showed that static random injections are
task-invisible: 150 corrupted nodes in a 50K KG (0.3%) never intersected any
question's retrieval neighborhood, and post-injection metrics were
byte-identical to baseline. Contamination only matters through PROPAGATION.
This runner therefore implements the epidemiological protocol:

  Step 0 — seed index cases INSIDE the active retrieval subgraph: candidate
      triplets are those reachable from the entity keys agents actually
      retrieve for (read from the extraction manifest), not uniform-random.
  Steps 1..N — transmission cycles. Each cycle is one write-back pass of the
      two-agent pipeline over a sample of active entities:
        retrieve KG facts for the entity (possibly contaminated — beta:
        retrieval) → synthesis agent writes a short passage from those facts
        (beta: susceptibility — corruption transmits into text) → extraction
        agent extracts triplets from the passage with the same facts as
        context → written back with DERIVED_FROM edges to the parents.
      Optional validation audits between cycles provide gamma (0 in the
      unmitigated baseline; >0 for Phase 3 mitigated runs — the same runner
      serves both via config).
  After every cycle — measure: SIR state counts (detected), ground-truth
      contamination counts per error type (seeded + propagated), incidence,
      and periodically the task metrics (HotpotQA EM/F1, FEVER veracity) on
      a FIXED question sample (same seed each step, so the trajectory is a
      degradation curve over identical questions).

Ground-truth bookkeeping (experimenter, not agent — same status as the
ErrorInjector, see provenance_schema.py):
  - A new triplet is EXPOSED if any of its lineage parents carries a
    contamination payload (seeded or propagated).
  - It is INFECTED if its content reproduces the corrupted after-value of an
    ancestor payload and does not reproduce the original value (word-boundary
    match on normalized text — a heuristic; borderline cases are auditable
    from the manifest). Infected triplets get
    error_type = "propagated_<root_type>" and carry the payload onward, so
    second-generation transmission is tracked.
  - `state` and `confidence` are never touched here — detection is the
    agents' job (Detection AUROC compares their judgment to error_type).

Protocol (clean room — run these in order):
    python scripts/load_kg.py --clear                     # 50K pristine T-REx
    python scripts/run_extraction.py --config experiments/configs/extraction_baseline.yaml
    python scripts/run_contamination.py --config experiments/configs/contamination_baseline.yaml

The runner aborts if ground-truth-corrupted nodes already exist (stale
injections from a previous sequence would confound the counts); override
with --allow-dirty only if that is intentional.

Outputs (results/raw/):
    contamination_<tag>_<ts>_trajectory.csv   — one row per step (the curves)
    contamination_<tag>_<ts>_manifest.json    — config, seed records, transmission log
    contamination_eval_<dataset>_<tag>_step<k>_<ts>.csv — per-question eval rows
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
from types import SimpleNamespace

from loguru import logger

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src.agents.extraction_agent import ExtractionAgent
from src.agents.llm_client import ModelRole, get_client
from src.agents.validation_agent import ValidationAgent
from src.graph.neo4j_client import Neo4jClient
from src.injection.error_injector import ERROR_TYPES, ErrorInjector

from run_baseline_eval import eval_fever, eval_hotpotqa  # scripts/ on path

logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")

RESULTS_DIR = ROOT / "results" / "raw"

_SYNTH_SYSTEM = """\
You are a knowledge synthesis agent in a multi-agent pipeline. Write a short
factual paragraph (2-4 sentences) about the given entity using ONLY the
knowledge-graph facts provided.

Rules:
- Restate the facts plainly as prose. Every fact should appear in the paragraph.
- Do not add any information that is not in the facts.
- Do not correct, question, or omit facts — you are a summarizer, not a fact
  checker. Output only the paragraph, no preamble.
"""


# ---------------------------------------------------------------------------
# Ground-truth transmission bookkeeping
# ---------------------------------------------------------------------------

def _norm(s: str) -> str:
    """Lowercase, underscores → spaces, collapsed whitespace — so snake_case
    predicates match prose payloads."""
    return re.sub(r"\s+", " ", s.replace("_", " ").lower()).strip()


def check_transmission(
    record: dict, parent_ids: list[str], payloads: dict[str, dict]
) -> tuple[bool, dict | None]:
    """(exposed, payload-if-infected) for one newly written triplet.

    exposed  — at least one lineage parent carries a contamination payload.
    infected — the new triplet's text reproduces a payload's corrupted value
               (word-boundary match) without reproducing the original value.
    """
    exposed = False
    text = _norm(f"{record['subject']} {record['predicate']} {record['object']}")
    for pid in parent_ids:
        p = payloads.get(pid)
        if p is None:
            continue
        exposed = True
        after, before = _norm(p["after"]), _norm(p["before"])
        if after and re.search(rf"\b{re.escape(after)}\b", text) and (
            not before or before not in text
        ):
            return True, p
    return exposed, None


# ---------------------------------------------------------------------------
# Experiment stages
# ---------------------------------------------------------------------------

def load_active_keys(manifest_path: Path) -> list[str]:
    """Entity keys the extraction pipeline actually retrieved for — this
    defines the active subgraph."""
    with open(manifest_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    keys, seen = [], set()
    for row in rows:
        key = (row.get("key") or "").strip()
        if key and key not in seen:
            seen.add(key)
            keys.append(key)
    return keys


def build_active_pool(client: Neo4jClient, keys: list[str], per_key: int) -> list[dict]:
    """Union of the retrieval neighborhoods of the active entity keys —
    the candidate pool for index-case seeding."""
    pool, seen = [], set()
    for key in keys:
        for t in client.get_related_triplets(
            subject=key, obj=key, exclude_id="", limit=per_key
        ):
            if t["id"] not in seen:
                seen.add(t["id"])
                pool.append(t)
    return pool


def seed_index_cases(
    client: Neo4jClient, keys: list[str], args
) -> tuple[list[dict], dict[str, dict]]:
    """Inject index cases into the active subgraph. Returns the injection
    records and the initial payload map {triplet_id: {root_type, before, after}}."""
    pool = build_active_pool(client, keys, args.pool_per_key)
    logger.info(f"Active subgraph pool: {len(pool)} triplets "
                f"from {len(keys)} entity keys")

    injector = ErrorInjector(neo4j_client=client, random_seed=args.random_seed)
    records = []
    for et in ERROR_TYPES:
        records += injector.inject(et, args.injections_per_type, pool=list(pool))

    payloads = {
        r["triplet_id"]: {
            "root_type": r["error_type"],
            "before":    str(r["before"]),
            "after":     str(r["after"]),
        }
        for r in records
    }
    logger.success(f"Seeded {len(records)} index cases inside the active subgraph")
    return records, payloads


def transmission_cycle(
    client: Neo4jClient,
    agent: ExtractionAgent,
    synth_llm,
    keys: list[str],
    payloads: dict[str, dict],
    step: int,
    args,
    rng: random.Random,
) -> dict:
    """One write-back pass over a sample of active entities."""
    sample = rng.sample(keys, min(args.entities_per_step, len(keys)))
    new_triplets = new_edges = new_exposed = new_infected = synth_units = 0
    transmissions = []

    for key in sample:
        facts = client.get_related_triplets(
            subject=key, obj=key, exclude_id="",
            min_confidence=args.retrieval_threshold, limit=args.context_limit,
        )
        if not facts:
            continue

        fact_lines = "\n".join(
            f"  - ({f['subject']}) --[{f['predicate']}]--> ({f['object']})"
            for f in facts
        )
        prompt = (f"Facts about {key}:\n{fact_lines}\n\n"
                  f"Write the paragraph about {key}.")
        try:
            paragraph = synth_llm.chat(prompt=prompt, system=_SYNTH_SYSTEM).content.strip()
        except Exception as exc:
            logger.warning(f"[step {step}] synthesis failed for '{key}': {exc}")
            continue
        if not paragraph:
            continue
        synth_units += 1
        if args.sleep > 0:
            time.sleep(args.sleep)

        records = agent.extract_and_store(
            text=paragraph,
            source_label=f"contamination_step_{step}",
            context_facts=facts,
        )
        parent_ids = [f["id"] for f in facts]
        new_triplets += len(records)
        new_edges += len(records) * len(parent_ids)

        for r in records:
            exposed, payload = check_transmission(r, parent_ids, payloads)
            if exposed:
                new_exposed += 1
            if payload is not None:
                client.update_triplet_fields(
                    r["id"], error_type=f"propagated_{payload['root_type']}"
                )
                payloads[r["id"]] = payload  # carries onward: 2nd generation
                new_infected += 1
                transmissions.append({
                    "step":    step,
                    "id":      r["id"],
                    "subject": r["subject"],
                    "predicate": r["predicate"],
                    "object":  r["object"],
                    "root_type": payload["root_type"],
                    "payload":  payload["after"],
                })
        if args.sleep > 0:
            time.sleep(args.sleep)

    logger.info(
        f"[step {step}] cycle: {synth_units} passages, {new_triplets} new triplets, "
        f"{new_exposed} exposed, {new_infected} INFECTED"
    )
    return {
        "synth_units":  synth_units,
        "new_triplets": new_triplets,
        "new_edges":    new_edges,
        "new_exposed":  new_exposed,
        "new_infected": new_infected,
        "transmissions": transmissions,
    }


def measure(client: Neo4jClient, step: int) -> dict:
    """SIR state counts (detected) + ground-truth contamination counts."""
    sir = client.count_by_state()
    gt = client.count_by_error_type()
    row = {
        "S": sir.get("S", 0), "I": sir.get("I", 0), "R": sir.get("R", 0),
    }
    for et in ERROR_TYPES:
        row[f"gt_seed_{et}"] = gt.get(et, 0)
        row[f"gt_prop_{et}"] = gt.get(f"propagated_{et}", 0)
    row["gt_total"] = sum(gt.values())
    logger.info(f"[step {step}] SIR={sir} | ground truth={gt}")
    return row


def run_task_eval(client: Neo4jClient, eval_llm, step: int, ts: str, args) -> dict:
    """Task metrics on the FIXED question sample (fresh RNG with the same
    seed each call → identical questions every step; unchanged retrieval
    neighborhoods replay from the LLM cache for free)."""
    ns = SimpleNamespace(num_questions=args.eval_questions,
                         facts_per_key=5, sleep=args.sleep)
    out = {}
    for name, fn in (("hotpotqa", eval_hotpotqa), ("fever", eval_fever)):
        res = fn(client, eval_llm, ns, random.Random(args.random_seed))
        rows = res.pop("rows")
        rows_path = (RESULTS_DIR /
                     f"contamination_eval_{name}_{args.tag}_step{step}_{ts}.csv")
        with open(rows_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        if name == "hotpotqa":
            out.update({"hotpot_em": res["exact_match"], "hotpot_f1": res["f1"],
                        "hotpot_avg_facts": res["avg_facts"]})
        else:
            out.update({"fever_accuracy": round(res["accuracy"], 4),
                        "fever_avg_facts": res["avg_facts"]})
    logger.success(f"[step {step}] task eval: {out}")
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def latest_extraction_manifest() -> Path:
    candidates = list(RESULTS_DIR.glob("extraction_*.csv"))
    if not candidates:
        raise FileNotFoundError(
            "No extraction manifest in results/raw — run "
            "scripts/run_extraction.py first (it defines the active subgraph)."
        )
    # newest by mtime — filename sort would rank datasets alphabetically
    return max(candidates, key=lambda p: p.stat().st_mtime)


def run_experiment(args) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    rng = random.Random(args.random_seed)

    manifest_path = (Path(args.extraction_manifest)
                     if args.extraction_manifest else latest_extraction_manifest())
    keys = load_active_keys(manifest_path)
    logger.info(f"=== Phase 2.4 Contamination Experiment === "
                f"(tag={args.tag}, seed={args.random_seed}, steps={args.steps})")
    logger.info(f"Active subgraph: {len(keys)} entity keys from {manifest_path.name}")

    trajectory: list[dict] = []
    all_transmissions: list[dict] = []

    with Neo4jClient() as client:
        preexisting = client.count_by_error_type()
        if preexisting and not args.allow_dirty:
            raise SystemExit(
                f"ABORT: KG already contains ground-truth-corrupted nodes "
                f"{preexisting} — stale injections would confound the counts. "
                f"Reload the KG (see protocol in the module docstring) or pass "
                f"--allow-dirty if this is intentional."
            )

        agent = ExtractionAgent(agent_id="contamination_pipeline",
                                neo4j_client=client)
        synth_llm = get_client(ModelRole.EXTRACTION)   # Mistral Nemo: extraction & synthesis
        eval_llm = get_client(ModelRole.ORCHESTRATION)
        validator = (ValidationAgent(neo4j_client=client)
                     if args.audits_per_step > 0 else None)

        # ---- Step 0: seed index cases + baseline measurement ----
        seed_records, payloads = seed_index_cases(client, keys, args)
        row = {"step": 0, "synth_units": 0, "new_triplets": 0, "new_edges": 0,
               "new_exposed": 0, "new_infected": 0, "cum_exposed": 0,
               "audited": 0, "quarantined": 0, "cascaded": 0}
        row.update(measure(client, 0))
        row.update(run_task_eval(client, eval_llm, 0, ts, args))
        trajectory.append(row)

        # ---- Transmission cycles ----
        cum_exposed = 0
        for step in range(1, args.steps + 1):
            cycle = transmission_cycle(client, agent, synth_llm, keys,
                                       payloads, step, args, rng)
            all_transmissions += cycle.pop("transmissions")
            cum_exposed += cycle["new_exposed"]

            audit = {"audited": 0, "quarantined": 0, "cascaded": 0}
            if validator is not None:
                for _ in range(args.audits_per_step):
                    rep = validator.run_audit_pass(sample_size=args.audit_sample)
                    audit["audited"] += rep["audited"]
                    audit["quarantined"] += rep["quarantined"]
                    audit["cascaded"] += rep["cascaded"]

            row = {"step": step, "cum_exposed": cum_exposed, **cycle, **audit}
            row.update(measure(client, step))
            is_eval_step = (step == args.steps or
                            (args.eval_every > 0 and step % args.eval_every == 0))
            if is_eval_step:
                row.update(run_task_eval(client, eval_llm, step, ts, args))
            trajectory.append(row)

    # ---- Persist ----
    fieldnames = list(trajectory[-1].keys())
    for r in trajectory:  # eval columns exist only on eval steps
        for k in fieldnames:
            r.setdefault(k, "")
    traj_path = RESULTS_DIR / f"contamination_{args.tag}_{ts}_trajectory.csv"
    with open(traj_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(trajectory)

    manifest = {
        "config":         {k: v for k, v in vars(args).items() if k != "config"},
        "timestamp":      ts,
        "extraction_manifest": str(manifest_path),
        "n_active_keys":  len(keys),
        "seed_records":   seed_records,
        "transmissions":  all_transmissions,
        "trajectory_csv": str(traj_path),
    }
    manifest_path_out = RESULTS_DIR / f"contamination_{args.tag}_{ts}_manifest.json"
    manifest_path_out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    logger.success(f"Trajectory → {traj_path.name}")
    logger.success(f"Manifest   → {manifest_path_out.name}")
    final = trajectory[-1]
    n_propagated = sum(final.get(f"gt_prop_{et}", 0) or 0 for et in ERROR_TYPES)
    logger.success(
        f"Final: gt_total={final['gt_total']} "
        f"(seeded this run: {len(seed_records)}, propagated: {n_propagated}), "
        f"cum_exposed={final['cum_exposed']}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 2.4 contamination experiment")
    parser.add_argument("--config",              type=str,   default=None, help="YAML config; CLI flags override")
    parser.add_argument("--steps",               type=int,   default=10,   help="Transmission cycles")
    parser.add_argument("--entities-per-step",   type=int,   default=12,   help="Active entities sampled per cycle")
    parser.add_argument("--injections-per-type", type=int,   default=15,   help="Index cases per error type (step 0)")
    parser.add_argument("--pool-per-key",        type=int,   default=50,   help="Neighborhood size per key for the seeding pool")
    parser.add_argument("--context-limit",       type=int,   default=5,    help="KG facts retrieved per synthesis/extraction unit")
    parser.add_argument("--retrieval-threshold", type=float, default=0.0,  help="Confidence floor on retrieval (0 = unmitigated)")
    parser.add_argument("--audits-per-step",     type=int,   default=0,    help="Validation audit passes per cycle (gamma; 0 = unmitigated)")
    parser.add_argument("--audit-sample",        type=int,   default=50,   help="Triplets per audit pass")
    parser.add_argument("--eval-every",          type=int,   default=5,    help="Task eval every k steps (0 = only step 0 and final)")
    parser.add_argument("--eval-questions",      type=int,   default=50,   help="Questions per dataset per eval (match baseline for comparability)")
    parser.add_argument("--extraction-manifest", type=str,   default=None, help="Path to extraction manifest CSV (default: latest)")
    parser.add_argument("--random-seed",         type=int,   default=42)
    parser.add_argument("--sleep",               type=float, default=1.0,  help="Seconds between LLM calls (rate limiting)")
    parser.add_argument("--tag",                 type=str,   default="baseline", help="Run label in output filenames")
    parser.add_argument("--allow-dirty",         action="store_true",      help="Run even if corrupted nodes pre-exist in the KG")

    pre_args, _ = parser.parse_known_args()
    if pre_args.config:
        from src.config import load_config
        cfg = load_config(pre_args.config)
        known = {a.dest for a in parser._actions}
        parser.set_defaults(**{k: v for k, v in cfg.items() if k in known})
    args = parser.parse_args()

    run_experiment(args)


if __name__ == "__main__":
    main()
