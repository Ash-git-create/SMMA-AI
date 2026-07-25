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
      serves both via config). --validate-every N (task: RQ3 validation-
      interval sweep) decouples audit FREQUENCY from audit COVERAGE: on
      skipped steps (step % N != 0, and step != the final step) the cycle's
      audit_candidates are queued onto a backlog instead of being audited or
      dropped; on a flush step (step % N == 0, or unconditionally the final
      step, so a sweep's step count can never let queued candidates escape
      auditing) the ENTIRE accumulated backlog is audited in one pass and
      the backlog is cleared. This is "pure delay, full coverage" — N=1
      (default) reduces exactly to the existing per-step behavior. Because
      the accumulated backlog can exceed --audit-sample (which was
      calibrated for one step's candidates), targeted oracle audits
      (--oracle-validation --audit-targeted) uncap sample_size to the
      backlog's own length on flush so coarse intervals don't silently
      truncate coverage — oracle audits make zero LLM calls, so this costs
      nothing; non-oracle (judge) audits keep --audit-sample as configured.
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
from src.evaluation.metrics import detection_auroc
from src.graph.neo4j_client import Neo4jClient
from src.injection.error_injector import ERROR_TYPES, ErrorInjector
from src.injection.khop_placement import khop_frontier

from run_baseline_eval import (  # scripts/ on path
    _QA_SYSTEM,
    eval_fever,
    eval_hotpotqa,
    facts_block,
    parse_json_response,
)

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
    infected — the new triplet reproduces a payload's corrupted value,
               matched by the payload's corrupted FIELD:
        object payloads (entity swaps, stripped qualifiers) must equal the
        derived subject or object exactly (normalized) — substring matching
        over-counted when the corrupted value was a fragment of a longer
        entity name ("New Orleans" inside "New Orleans Pelicans") or of a
        full date ("2006" inside "14 September 2006"); first-run audit put
        precision at 0.65, all false positives from those two classes.
        predicate payloads (strengthened relations) word-boundary match the
        derived predicate only — extraction re-phrases predicates
        ("lead actor" → lead_actor_in), so equality would miss real events.
    Conservative by construction: paraphrased reproductions are not counted,
    so infection counts are a lower bound.
    """
    exposed = False
    subj = _norm(record["subject"])
    pred = _norm(record["predicate"])
    obj = _norm(record["object"])
    for pid in parent_ids:
        p = payloads.get(pid)
        if p is None:
            continue
        exposed = True
        after, before = _norm(p["after"]), _norm(p["before"])
        if not after:
            continue
        if p["field"] == "object":
            if after in (subj, obj) and before not in (subj, obj):
                return True, p
        else:  # predicate payload
            if re.search(rf"\b{re.escape(after)}\b", pred) and before not in pred:
                return True, p
    return exposed, None


# ---------------------------------------------------------------------------
# Validation-interval sweep (--validate-every) — pure, Neo4j-free helpers
# ---------------------------------------------------------------------------

def accumulate_candidates(pending: list[str], new_ids: list[str]) -> None:
    """Append new_ids onto the pending audit backlog in place, order-
    preserving, skipping ids already queued. The backlog behind
    --validate-every N: candidates from skipped steps roll forward instead
    of being audited or lost."""
    seen = set(pending)
    for tid in new_ids:
        if tid not in seen:
            seen.add(tid)
            pending.append(tid)


def is_validate_step(step: int, total_steps: int, validate_every: int) -> bool:
    """True on flush steps for --validate-every N: every Nth step, and
    unconditionally the final step (so queued backlog can never escape
    auditing solely because the sweep ended). N<=1 flushes every step —
    identical to pre-sweep behavior."""
    validate_every = max(1, validate_every)
    return step % validate_every == 0 or step == total_steps


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


def build_khop_pool(
    client: Neo4jClient, active_keys: list[str], k: int, pool_size: int,
    pool_per_key: int = 50,
) -> tuple[list[dict], dict[str, int]]:
    """Pool builder for --seed-khop: Susceptible triplets at exact
    bipartite-graph distance k from the active retrieval subgraph (the
    union of active_keys' retrieval neighborhoods — build_active_pool IS
    the k=0 pool). Hop-by-hop set-wise expansion (the part that needs
    unit-test coverage without Neo4j) lives in
    src/injection/khop_placement.khop_frontier; this wrapper just supplies
    the k=0 seed the same way the existing 'active' placement does, so the
    two stay in lockstep by construction. Returns (pool, hop_map) — the
    hop_map audits the realized distance of every returned triplet (== k,
    or fewer entries than pool_size if the local subgraph runs out before
    reaching k — see khop_frontier's exhaustion handling)."""
    active_pool = build_active_pool(client, active_keys, pool_per_key)
    return khop_frontier(client, active_pool, k, pool_size)


def seed_index_cases(
    client: Neo4jClient, keys: list[str], args
) -> tuple[list[dict], dict[str, dict]]:
    """Inject index cases. Placement is the RQ1/RQ3 lever:
      'active' seeds inside the union of active retrieval neighborhoods
          (errors agents will actually encounter);
      'random' seeds uniformly across all Susceptible triplets (the
          control arm — spread differences vs 'active' isolate how much
          contamination depends on landing in retrieval-reachable
          positions);
      --seed-khop (overrides --seed-placement when set) grades the above
          binary into a distance gradient: index cases at exact
          bipartite-graph hop distance k from the active subgraph (k=0 is
          identical in content to 'active'; see khop_placement.py).
    Returns the injection records — each with a 'khop' field (the realized
    hop distance, or None when --seed-khop was not used) — and the initial
    payload map {triplet_id: {root_type, before, after}}."""
    khop_map: dict[str, int] = {}
    seed_khop = getattr(args, "seed_khop", None)
    if seed_khop is not None:
        # pool_size ceiling: generous relative to injections_per_type*3 (the
        # actual demand) so hop pools aren't artificially starved relative
        # to the 'active' pool's typical size; khop_frontier truncates to
        # whatever the local subgraph actually has at that exact distance.
        pool, khop_map = build_khop_pool(
            client, keys, seed_khop,
            pool_size=args.pool_per_key * 20, pool_per_key=args.pool_per_key,
        )
        logger.info(f"K-hop pool (k={seed_khop}): {len(pool)} triplets")
    elif args.seed_placement == "active":
        pool = build_active_pool(client, keys, args.pool_per_key)
        logger.info(f"Active subgraph pool: {len(pool)} triplets "
                    f"from {len(keys)} entity keys")
    else:
        pool = None
        logger.info("Seed placement 'random': uniform across Susceptible KG")

    injector = ErrorInjector(neo4j_client=client, random_seed=args.random_seed)
    records = []
    for et in ERROR_TYPES:
        records += injector.inject(et, args.injections_per_type,
                                   pool=list(pool) if pool is not None else None)
    for r in records:
        r["khop"] = khop_map.get(r["triplet_id"])

    payloads = {
        r["triplet_id"]: {
            "root_type": r["error_type"],
            "field":     r["field"],
            "before":    str(r["before"]),
            "after":     str(r["after"]),
        }
        for r in records
    }
    placement_label = f"khop={seed_khop}" if seed_khop is not None else args.seed_placement
    logger.success(f"Seeded {len(records)} index cases "
                   f"(placement: {placement_label})")
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
    """One write-back pass over a sample of active entities.

    Also instruments the beta decomposition: how many retrieval contexts
    contained >=1 contaminated fact (retrieval component) and how many
    contaminated facts were served in total. Together with exposed/infected
    this lets beta = P(retrieve contaminated) x P(reproduce | exposed) be
    estimated from the run itself instead of assumed.
    """
    sample = rng.sample(keys, min(args.entities_per_step, len(keys)))
    new_triplets = new_edges = new_exposed = new_infected = synth_units = 0
    n_contexts = n_contexts_contam = n_facts_served = n_contam_facts_served = 0
    transmissions = []
    audit_candidates: list[str] = []  # what this cycle read + wrote (targeted validation)

    for key in sample:
        facts = client.get_related_triplets(
            subject=key, obj=key, exclude_id="",
            min_confidence=args.retrieval_threshold, limit=args.context_limit,
        )
        if not facts:
            continue
        n_contexts += 1
        n_facts_served += len(facts)
        n_contam = sum(1 for f in facts if f.get("error_type"))
        n_contam_facts_served += n_contam
        if n_contam:
            n_contexts_contam += 1

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
        for tid in parent_ids + [r["id"] for r in records]:
            if tid not in audit_candidates:
                audit_candidates.append(tid)

        unit_tx = []
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
                tx = {
                    "step":    step,
                    "id":      r["id"],
                    "subject": r["subject"],
                    "predicate": r["predicate"],
                    "object":  r["object"],
                    "root_type": payload["root_type"],
                    "payload":  payload["after"],
                }
                transmissions.append(tx)
                unit_tx.append(tx)

        # Replay corpus (--log-prompts): the identical (context, prompt) this
        # unit ran, plus Nemo's paragraph and whether it propagated, so a
        # larger model can be replayed on the same input offline.
        if getattr(args, "_prompt_log", None):
            with open(args._prompt_log, "a", encoding="utf-8") as _pl:
                _pl.write(json.dumps({
                    "step": step,
                    "key": key,
                    "n_facts": len(facts),
                    "n_contam": n_contam,
                    "context_facts": [
                        {"subject": f["subject"], "predicate": f["predicate"],
                         "object": f["object"], "error_type": f.get("error_type"),
                         "id": f["id"]}
                        for f in facts
                    ],
                    "system": _SYNTH_SYSTEM,
                    "prompt": prompt,
                    "paragraph": paragraph,
                    "propagated": len(unit_tx),
                    "transmissions": unit_tx,
                }, ensure_ascii=False) + "\n")

        if args.sleep > 0:
            time.sleep(args.sleep)

    logger.info(
        f"[step {step}] cycle: {synth_units} passages, {new_triplets} new triplets, "
        f"{new_exposed} exposed, {new_infected} INFECTED | "
        f"contexts {n_contexts_contam}/{n_contexts} contaminated "
        f"({n_contam_facts_served}/{n_facts_served} facts)"
    )
    return {
        "synth_units":            synth_units,
        "new_triplets":           new_triplets,
        "new_edges":              new_edges,
        "new_exposed":            new_exposed,
        "new_infected":           new_infected,
        "n_contexts":             n_contexts,
        "n_contexts_contam":      n_contexts_contam,
        "n_facts_served":         n_facts_served,
        "n_contam_facts_served":  n_contam_facts_served,
        "transmissions":          transmissions,
        "audit_candidates":       audit_candidates,
    }


def measure(client: Neo4jClient, step: int) -> dict:
    """SIR state counts (detected) + ground-truth contamination counts +
    detection confusion (state vs error_type — quarantine precision and
    mitigation collateral damage)."""
    sir = client.count_by_state()
    gt = client.count_by_error_type()
    confusion = client.detection_confusion()
    row = {
        "S": sir.get("S", 0), "I": sir.get("I", 0), "R": sir.get("R", 0),
    }
    for et in ERROR_TYPES:
        row[f"gt_seed_{et}"] = gt.get(et, 0)
        row[f"gt_prop_{et}"] = gt.get(f"propagated_{et}", 0)
    row["gt_total"] = sum(gt.values())
    # R_contam = true quarantines; R_clean = collateral damage (clean facts
    # lost to quarantine/cascade); I_* analogous for infected-marks.
    for k in ("R_contam", "R_clean", "I_contam", "I_clean"):
        row[f"det_{k}"] = confusion.get(k, 0)
    logger.info(f"[step {step}] SIR={sir} | ground truth={gt} | detection={confusion}")
    return row


def run_task_eval(client: Neo4jClient, eval_llm, step: int, ts: str, args) -> dict:
    """Task metrics on the FIXED question sample (fresh RNG with the same
    seed each call → identical questions every step; unchanged retrieval
    neighborhoods replay from the LLM cache for free)."""
    ns = SimpleNamespace(num_questions=args.eval_questions,
                         facts_per_key=5, sleep=args.sleep,
                         retrieval_threshold=args.retrieval_threshold)
    out = {}
    for name, fn in (("hotpotqa", eval_hotpotqa), ("fever", eval_fever)):
        res = fn(client, eval_llm, ns, random.Random(args.eval_seed))
        rows = res.pop("rows")
        rows_path = (RESULTS_DIR /
                     f"contamination_eval_{name}_{args.tag}_step{step}_{ts}.csv")
        with open(rows_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        if name == "hotpotqa":
            out.update({"hotpot_em": res["exact_match"], "hotpot_f1": res["f1"],
                        "hotpot_avg_facts": res["avg_facts"],
                        "hotpot_usr": res["usr"], "hotpot_usr_n": res["usr_n"],
                        "hotpot_abstain": res["abstain_rate"]})
        else:
            out.update({"fever_accuracy": round(res["accuracy"], 4),
                        "fever_avg_facts": res["avg_facts"]})
    logger.success(f"[step {step}] task eval: {out}")
    return out


def run_probe_eval(
    client: Neo4jClient, eval_llm, payloads: dict[str, dict],
    step: int, ts: str, args,
) -> dict:
    """Probe questions generated FROM the corrupted nodes — the harm metric.

    The fixed task sample measures whether contamination *reaches* generic
    queries (an epidemiological quantity, ~0 at low prevalence). Probes ask
    directly about the corrupted facts, measuring whether the KG-grounded
    system *returns corrupted answers when contamination is in scope*:
      contaminated — answer reproduces the corrupted value
      original     — answer gives the pre-corruption value (only meaningful
                     for seeded nodes, whose original value is known; a
                     propagated node's subject may never have had a true
                     value in the KG at all)
      other        — anything else, incl. "unknown" / no facts retrieved

    Probe set = all ground-truth corrupted nodes (seeded + propagated so
    far), capped at probe_limit in sorted-id order for determinism. The set
    grows over steps as infections accumulate — probe_n is reported with it.
    """
    node_ids = sorted(payloads)[: args.probe_limit]
    rows = []
    counts = {"contaminated": 0, "original": 0, "other": 0}

    for nid in node_ids:
        node = client.get_triplet(nid)
        if node is None:
            continue
        p = payloads[nid]
        subj, pred, obj = node["subject"], node["predicate"], node["object"]
        if p["field"] == "object":
            question = f"What is the '{pred.replace('_', ' ')}' of {subj}?"
        else:
            question = f"What is the relationship between {subj} and {obj}?"

        facts = client.get_related_triplets(
            subject=subj, obj=subj, exclude_id="",
            min_confidence=args.retrieval_threshold, limit=args.probe_facts,
        )
        prompt = (f"Knowledge-graph facts:\n{facts_block(facts)}\n\n"
                  f"Question: {question}")
        try:
            parsed = parse_json_response(
                eval_llm.chat(prompt=prompt, system=_QA_SYSTEM).content
            )
            answer = str(parsed["answer"]) if parsed and "answer" in parsed else ""
        except Exception as exc:
            logger.warning(f"[probe] LLM failure on {nid}: {exc}")
            answer = ""

        ans = _norm(answer)
        after, before = _norm(p["after"]), _norm(p["before"])
        hit_after = bool(after) and re.search(rf"\b{re.escape(after)}\b", ans)
        hit_before = bool(before) and re.search(rf"\b{re.escape(before)}\b", ans)
        if hit_after and not hit_before:
            verdict = "contaminated"
        elif hit_before and not hit_after:
            verdict = "original"
        else:
            verdict = "other"
        counts[verdict] += 1

        rows.append({
            "node_id":   nid,
            "seeded":    int(not node.get("error_type", "").startswith("propagated_")),
            "root_type": p["root_type"],
            "question":  question[:120],
            "corrupted_value": p["after"],
            "original_value":  p["before"],
            "answer":    answer[:120],
            "verdict":   verdict,
            "n_facts":   len(facts),
        })
        if args.sleep > 0:
            time.sleep(args.sleep)

    if rows:
        probe_path = RESULTS_DIR / f"contamination_probe_{args.tag}_step{step}_{ts}.csv"
        with open(probe_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

    n = len(rows)
    out = {
        "probe_n":            n,
        "probe_contaminated": counts["contaminated"],
        "probe_original":     counts["original"],
        "probe_other":        counts["other"],
        "probe_contam_rate":  round(counts["contaminated"] / n, 4) if n else 0.0,
    }
    logger.success(f"[step {step}] probes: {out}")
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

    # Verbatim synthesis-prompt corpus for the offline model-scale replay
    # probes (propagation replay): each record pairs the exact facts served +
    # prompt with Nemo's paragraph and the ground-truth propagation outcome,
    # so a larger model can be fed the identical context and its reproduction
    # rate compared with context held constant. Off by default (adds one
    # JSONL append per synthesis unit; no LLM cost).
    args._prompt_log = (
        str(RESULTS_DIR / f"contamination_prompts_{args.tag}_{ts}.jsonl")
        if getattr(args, "log_prompts", False) else None
    )

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
                                neo4j_client=client,
                                propagate_confidence=args.trio_confidence)
        synth_llm = get_client(ModelRole.EXTRACTION)   # Mistral Nemo: extraction & synthesis
        eval_llm = get_client(ModelRole.ORCHESTRATION)
        validator = (ValidationAgent(neo4j_client=client,
                                     quarantine_threshold=args.quarantine_threshold,
                                     oracle=args.oracle_validation,
                                     oracle_sensitivity=args.oracle_sensitivity,
                                     oracle_false_alarm=args.oracle_false_alarm,
                                     oracle_seed=args.oracle_seed,
                                     validator_prompt=args.validator_prompt)
                     if args.audits_per_step > 0 else None)

        # ---- Step 0: seed index cases + baseline measurement ----
        seed_records, payloads = seed_index_cases(client, keys, args)
        row = {"step": 0, "synth_units": 0, "new_triplets": 0, "new_edges": 0,
               "new_exposed": 0, "new_infected": 0, "cum_exposed": 0,
               "n_contexts": 0, "n_contexts_contam": 0,
               "n_facts_served": 0, "n_contam_facts_served": 0,
               "audited": 0, "quarantined": 0, "cascaded": 0}
        row.update(measure(client, 0))
        if not getattr(args, "no_eval", False):
            row.update(run_task_eval(client, eval_llm, 0, ts, args))
            row.update(run_probe_eval(client, eval_llm, payloads, 0, ts, args))
        trajectory.append(row)

        # ---- Transmission cycles ----
        cum_exposed = 0
        validate_every = max(1, getattr(args, "validate_every", 1))
        pending_audit_ids: list[str] = []  # --validate-every backlog
        for step in range(1, args.steps + 1):
            cycle = transmission_cycle(client, agent, synth_llm, keys,
                                       payloads, step, args, rng)
            all_transmissions += cycle.pop("transmissions")
            audit_ids = cycle.pop("audit_candidates")
            cum_exposed += cycle["new_exposed"]
            accumulate_candidates(pending_audit_ids, audit_ids)

            audit = {"audited": 0, "quarantined": 0, "cascaded": 0}
            flush = is_validate_step(step, args.steps, validate_every)
            if validator is not None and flush:
                flush_ids = pending_audit_ids
                sample_size = args.audit_sample
                if args.audit_targeted and args.oracle_validation and validate_every > 1:
                    # Backlog can exceed audit_sample (calibrated for one
                    # step); oracle audits are LLM-free, so uncap on flush
                    # to guarantee full coverage of the accumulated backlog.
                    sample_size = max(args.audit_sample, len(flush_ids))
                for _ in range(args.audits_per_step):
                    rep = validator.run_audit_pass(
                        sample_size=sample_size,
                        candidates=flush_ids if args.audit_targeted else None,
                    )
                    audit["audited"] += rep["audited"]
                    audit["quarantined"] += rep["quarantined"]
                    audit["cascaded"] += rep["cascaded"]
                pending_audit_ids = []

            row = {"step": step, "cum_exposed": cum_exposed, **cycle, **audit}
            row.update(measure(client, step))
            is_eval_step = (not getattr(args, "no_eval", False) and
                            (step == args.steps or
                             (args.eval_every > 0 and step % args.eval_every == 0)))
            if is_eval_step:
                row.update(run_task_eval(client, eval_llm, step, ts, args))
                row.update(run_probe_eval(client, eval_llm, payloads, step, ts, args))
            trajectory.append(row)

        # Detection AUROC over final confidences: can the system's own scores
        # separate contaminated from clean nodes? 0.5 = no signal (expected
        # in the unmitigated arm — nothing ever re-scores confidence there).
        contam_conf, clean_conf = client.get_contamination_confidences()
        scores = [1.0 - c for c in contam_conf + clean_conf]
        labels = [1] * len(contam_conf) + [0] * len(clean_conf)
        trajectory[-1]["detection_auroc"] = round(detection_auroc(labels, scores), 4)
        logger.success(f"Detection AUROC (final): {trajectory[-1]['detection_auroc']} "
                       f"({len(contam_conf)} contaminated vs {len(clean_conf)} clean)")

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
    parser.add_argument("--seed-placement",      type=str,   default="active", choices=["active", "random"],
                        help="Index-case placement: 'active' = inside active retrieval subgraph "
                             "(default, all Phase 2.4/3.2 runs); 'random' = uniform across "
                             "Susceptible KG (RQ1 control arm)")
    parser.add_argument("--seed-khop",           type=int,   default=None, choices=[0, 1, 2, 3],
                        help="Index-case placement at exact bipartite-graph hop distance k from "
                             "the active retrieval subgraph (k=0 = active pool itself, identical "
                             "to --seed-placement active). Overrides --seed-placement when set. "
                             "RQ1/RQ3 bridge: contamination reach as a function of "
                             "distance-to-workload. Default None = existing behavior unchanged "
                             "(--seed-placement governs).")
    parser.add_argument("--context-limit",       type=int,   default=5,    help="KG facts retrieved per synthesis/extraction unit")
    parser.add_argument("--retrieval-threshold", type=float, default=0.0,  help="Confidence floor on retrieval (0 = unmitigated)")
    parser.add_argument("--audits-per-step",     type=int,   default=0,    help="Validation audit passes per cycle (gamma; 0 = unmitigated)")
    parser.add_argument("--audit-sample",        type=int,   default=50,   help="Triplets per audit pass")
    parser.add_argument("--audit-targeted",      action="store_true",      help="Audit this cycle's read/written nodes instead of uniform random")
    parser.add_argument("--validate-every",      type=int,   default=1,
                        help="RQ3 validation-interval sweep: audit every Nth step "
                             "(default 1 = current per-step behavior). Skipped steps' "
                             "audit_candidates accumulate onto a backlog instead of being "
                             "dropped; the flush step (step %% N == 0, or unconditionally "
                             "the final step) audits the FULL backlog, not just that step's "
                             "candidates — pure delay, full coverage. Does not scale "
                             "audits_per_step or audit_sample (see module docstring).")
    parser.add_argument("--quarantine-threshold", type=float, default=0.4, help="Validator quarantines below this confidence")
    parser.add_argument("--oracle-validation",   action="store_true",
                        help="Validator quarantines from ground truth (error_type) instead "
                             "of the LLM judge — RQ4 upper-bound arm isolating judge "
                             "precision from the Trio architecture; zero audit LLM calls")
    parser.add_argument("--oracle-sensitivity",  type=float, default=1.0,
                        help="Task #23 noisy-oracle: P(flag | contaminated). 1.0 = perfect "
                             "recall (default oracle behaviour). Ignored unless --oracle-validation.")
    parser.add_argument("--oracle-false-alarm",  type=float, default=0.0,
                        help="Task #23 noisy-oracle: P(flag | clean). 0.0 = no false alarms "
                             "(default oracle behaviour). Ignored unless --oracle-validation.")
    parser.add_argument("--oracle-seed",         type=int,   default=42,
                        help="RNG seed for noisy-oracle flag draws (separate from --random-seed).")
    parser.add_argument("--validator-prompt",    type=str,   default="default", choices=["default", "tuned"],
                        help="Judge prompt for the ValidationAgent: 'tuned' = the task #20 "
                             "quote-first prompt (evidence-then-verdict, absence-of-evidence "
                             "is not contradiction); same model and JSON contract")
    parser.add_argument("--trio-confidence",     action="store_true",      help="Trio confidence propagation at write time (derived conf = f(parents))")
    parser.add_argument("--eval-every",          type=int,   default=5,    help="Task eval every k steps (0 = only step 0 and final)")
    parser.add_argument("--eval-questions",      type=int,   default=50,   help="Questions per dataset per eval (match baseline for comparability)")
    parser.add_argument("--probe-limit",         type=int,   default=60,   help="Max corrupted-node probe questions per eval step")
    parser.add_argument("--log-prompts",         action="store_true",      help="Archive verbatim synthesis (context, prompt, paragraph, propagation) as JSONL for offline model-scale replay probes")
    parser.add_argument("--no-eval",             action="store_true",      help="Skip task-eval + probe (the only Groq consumers). SIR/reach/AUROC metrics are unaffected; probe/task columns are omitted. For Groq-free RQ3 seed replication.")
    parser.add_argument("--probe-facts",         type=int,   default=8,    help="KG facts retrieved per probe question")
    parser.add_argument("--extraction-manifest", type=str,   default=None, help="Path to extraction manifest CSV (default: latest)")
    parser.add_argument("--random-seed",         type=int,   default=42)
    parser.add_argument("--eval-seed",           type=int,   default=42,
                        help="Task-eval question sampling seed — fixed across runs so "
                             "cross-run task metrics compare the same questions (probes "
                             "stay on --random-seed; they are inherently run-specific)")
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
