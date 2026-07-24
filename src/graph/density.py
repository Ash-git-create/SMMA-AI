"""
KG-level density manipulation — pure functions, no Neo4j dependency.

Why entity degree (not triplet count) is "density" here
---------------------------------------------------------
The contamination transmission channel is entity co-occurrence:
`Neo4jClient.get_related_triplets(subject=key, obj=key, ...)` (used by both
`run_contamination.build_active_pool` / `transmission_cycle` and by
`run_extraction`'s `--kg-context` retrieval) returns triplets where the
queried entity appears as subject OR object, ordered by confidence then id,
capped at a caller-supplied limit (`--context-limit`, `--pool-per-key`,
`--probe-facts`). The size of the UNCAPPED candidate set behind that cap is
exactly the entity's degree: the number of distinct triplets touching it.

`--context-limit` is a retrieval-time proxy for density — it changes how
much of a neighborhood an agent sees, but not the neighborhood itself. Two
KGs with identical context_limit=5 behave very differently in practice if
one entity has degree 6 (barely capped, high-confidence facts dominate) and
the other has degree 600 (heavily capped, tiny fraction of the neighborhood
is ever visible). Structural density — mean triplets per entity — is the
graph-level quantity that context_limit is a lossy window onto. This module
manipulates the underlying graph so density experiments are not confounded
with (and can be crossed with) the retrieval-cap axis.

Two operations, both operating on already-selected records (i.e. whatever
`load_kg.py` would otherwise load unmodified — after any `--limit` slicing)
and both refusing to fabricate data:

  density < 1.0  — SPARSIFICATION (`_sparsify`)
      Degree-aware subsampling: triplets touching high-degree entities are
      preferentially dropped. Entity coverage (n_entities) is preserved as
      much as possible — an entity is never reduced to zero remaining
      triplets by a drop if a lower-priority (lower-weight) candidate could
      be dropped instead.

  density > 1.0  — DENSIFICATION BY RESTRICTION (`_densify`)
      No new triplets are invented. Entities are ranked by original degree
      (descending) and added one at a time to a kept-entity set; each
      entity's full triplet set is folded into the kept-triplet set. This
      concentrates the *same* triplets onto *fewer* entities (raising mean
      degree) by exploiting the fact that in a hub-and-spoke graph like
      T-REx, most triplets touch at least one high-degree "hub" entity —
      so the union of a small number of hubs' neighborhoods already covers
      most of the triplet budget.

Both algorithms are deterministic given (records, factor, seed) and use
`--density-seed` only where randomness is involved (sparsification).
Densification is a pure ranking — no RNG needed, so `--density-seed` is
accepted but unused for factor > 1.0 (documented, not silently ignored).
"""

from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Optional

Record = dict


# ----------------------------------------------------------------------
# Degree / stats primitives
# ----------------------------------------------------------------------

def compute_entity_degree(records: list[Record], id_key: str = "id") -> dict[str, int]:
    """entity -> number of DISTINCT triplets touching it as subject or object.

    Matches the Cypher retrieval predicate exactly:
    `t.subject IN [$key] OR t.object IN [$key]` — a self-loop triplet
    (subject == object) is counted once, not twice, for that entity.
    """
    touching: dict[str, set] = defaultdict(set)
    for r in records:
        tid = r[id_key]
        touching[r["subject"]].add(tid)
        touching[r["object"]].add(tid)
    return {e: len(ids) for e, ids in touching.items()}


def _percentile(sorted_vals: list[float], p: float) -> float:
    """Linear-interpolation percentile (numpy 'linear' method), p in [0,100]."""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    return float(sorted_vals[int(f)] * (c - k) + sorted_vals[int(c)] * (k - f))


def compute_stats(records: list[Record], id_key: str = "id") -> dict:
    """n_triplets, n_entities, mean/median/p90 entity degree."""
    degree = compute_entity_degree(records, id_key)
    n_triplets = len(records)
    n_entities = len(degree)
    values = sorted(degree.values())
    mean_degree = round(sum(values) / n_entities, 4) if n_entities else 0.0
    median_degree = round(_percentile(values, 50), 4)
    p90_degree = round(_percentile(values, 90), 4)
    return {
        "n_triplets": n_triplets,
        "n_entities": n_entities,
        "mean_degree": mean_degree,
        "median_degree": median_degree,
        "p90_degree": p90_degree,
    }


# ----------------------------------------------------------------------
# Sparsification (density < 1.0)
# ----------------------------------------------------------------------

def _sparsify(
    records: list[Record], factor: float, seed: int, id_key: str = "id"
) -> tuple[list[Record], dict]:
    """Degree-aware subsampling.

    Algorithm
    ---------
    1. Compute original entity degree and a static per-triplet drop weight
       `w(t) = max(degree(subject), degree(object))` — triplets anchored to
       high-degree entities get high weight (they're "prime candidates" for
       removal: dropping them barely dents coverage). Weights are computed
       ONCE from the pre-drop graph, not recomputed after each removal
       (keeps the algorithm O(n log n) and its output reproducible from a
       single pass, at the cost of not perfectly re-optimizing weight after
       each drop — acceptable since the target is an approximate density
       factor, verified by the realized stats reported at the end).
    2. Deterministic weighted-random ranking via the Efraimidis-Spirakis
       scheme: for each triplet (visited in an id-sorted, seed-independent
       order so RNG draws are reproducible regardless of input list order),
       draw u ~ Uniform(0,1) from `random.Random(seed)` and compute
       key = u ** (1 / w(t)). Triplets are then ranked by key descending —
       higher weight biases a triplet toward the front of this ranking
       (more likely to be an early/strong drop candidate), while still
       leaving room for low-weight triplets to occasionally be picked
       (true weighted sampling, not a hard top-k truncation by weight).
    3. Target triplet count: `target_n = round(n_triplets * factor)`, i.e.
       coverage (n_entities) is assumed ~constant, so mean degree
       (~ 2*n_triplets/n_entities) scales ~linearly with n_triplets. This
       assumption is exactly what step 4's protection rule tries to hold.
    4. Walk the ranked drop-candidate list; commit a drop only if it does
       NOT reduce either endpoint's remaining degree to 0 (tracked via a
       running counter, seeded from original degree). This preserves
       entity coverage as much as possible. If coverage-preserving
       candidates run out before `target_n` is reached, sparsification
       stops early (best-effort) — the shortfall is visible in the
       realized stats (realized factor > requested factor).
    """
    orig_stats = compute_stats(records, id_key)
    degree0 = compute_entity_degree(records, id_key)
    n0 = len(records)
    target_n = max(0, round(n0 * factor))
    n_to_drop = max(0, n0 - target_n)

    weights = {
        r[id_key]: max(degree0[r["subject"]], degree0[r["object"]])
        for r in records
    }

    rng = random.Random(seed)
    ordered_ids = sorted(weights.keys())  # seed-independent draw order
    keys: dict[str, float] = {}
    for tid in ordered_ids:
        u = rng.random()
        w = max(weights[tid], 1e-9)
        keys[tid] = u ** (1.0 / w)

    drop_order = sorted(keys.keys(), key=lambda tid: (-keys[tid], tid))

    by_id = {r[id_key]: r for r in records}
    remaining_degree = dict(degree0)
    dropped: set = set()
    for tid in drop_order:
        if len(dropped) >= n_to_drop:
            break
        r = by_id[tid]
        subj, obj = r["subject"], r["object"]
        if subj == obj:
            if remaining_degree[subj] <= 1:
                continue  # would zero out this entity's only triplet
        else:
            if remaining_degree[subj] <= 1 or remaining_degree[obj] <= 1:
                continue
        # commit
        dropped.add(tid)
        remaining_degree[subj] -= 1
        if subj != obj:
            remaining_degree[obj] -= 1

    kept_records = [r for r in records if r[id_key] not in dropped]
    realized_stats = compute_stats(kept_records, id_key)
    realized_factor = (
        round(realized_stats["mean_degree"] / orig_stats["mean_degree"], 4)
        if orig_stats["mean_degree"] else 0.0
    )
    stats = {
        "algorithm": "sparsify_degree_weighted",
        "requested_factor": factor,
        "realized_factor": realized_factor,
        "seed": seed,
        "n_dropped": len(dropped),
        "n_drop_target": n_to_drop,
        "coverage_preserving_stop": len(dropped) < n_to_drop,
        "original": orig_stats,
        "realized": realized_stats,
    }
    return kept_records, stats


# ----------------------------------------------------------------------
# Densification (density > 1.0)
# ----------------------------------------------------------------------

def _densify(
    records: list[Record], factor: float, id_key: str = "id"
) -> tuple[list[Record], dict]:
    """Densification by restriction — never fabricates triplets.

    Algorithm
    ---------
    1. Compute original entity degree; rank entities descending by degree,
       tie-broken by entity id ascending (deterministic, no RNG).
    2. Walk the ranked entity list, adding each entity's full triplet set
       to a running kept-triplet set (union — a triplet already pulled in
       by an earlier, higher-degree entity is not double counted).
    3. After each entity is added, recompute the realized mean degree of
       the KEPT SUBGRAPH ONLY (entities restricted to those touched by a
       kept triplet). Stop as soon as realized mean degree >=
       `orig_mean_degree * factor` (target reached).
    4. Adding a *low*-degree entity can, once every high-degree hub is
       already included, DECREASE realized mean degree (a previously
       untouched entity contributes a full new denominator slot for as
       little as +1 to the numerator). Naively walking the whole ranked
       list to `target_mean` would then be forced past the actual optimum
       all the way to the full triplet budget, silently undoing the
       concentration this function exists to produce. So every prefix's
       realized mean is tracked, and if the walk finishes (or budget runs
       out) without ever reaching `target_mean`, the BEST prefix seen
       (highest realized mean, i.e. peak concentration achieved by
       restricting to *some* number of top-degree entities) is used
       instead of the final one — reported honestly via
       `realized_factor < requested factor`.
    5. Output preserves original record order (filtered), and touches only
       entities from the original entity set. No new subject/predicate/
       object combination is ever introduced.

    Running aggregates (entity_degree_kept, sum_degree_kept,
    n_entities_kept) are maintained incrementally so each step is O(edges
    added), not O(n) — overall O(n) rather than O(n_entities * n). The
    optional replay to the best prefix (step 4) is a second O(n) pass, only
    performed when the target was not reached.
    """
    orig_stats = compute_stats(records, id_key)
    degree0 = compute_entity_degree(records, id_key)
    n0 = len(records)
    target_mean = orig_stats["mean_degree"] * factor

    entity_to_triplets: dict[str, set] = defaultdict(set)
    for r in records:
        tid = r[id_key]
        entity_to_triplets[r["subject"]].add(tid)
        entity_to_triplets[r["object"]].add(tid)

    by_id = {r[id_key]: r for r in records}
    ranked_entities = sorted(degree0.items(), key=lambda kv: (-kv[1], kv[0]))

    def _replay(prefix_len: int) -> set:
        """Recompute kept_ids from scratch using only the first
        `prefix_len` ranked entities — used to roll back to the best
        prefix when the greedy walk overshoots the optimum (step 4)."""
        ids: set = set()
        for entity, _ in ranked_entities[:prefix_len]:
            ids |= entity_to_triplets[entity]
        return ids

    kept_ids: set = set()
    entity_degree_kept: dict[str, int] = defaultdict(int)
    n_entities_kept = 0
    sum_degree_kept = 0
    n_entities_added = 0
    hit_target = False
    best_mean = -1.0
    best_prefix_len = 0

    for entity, _ in ranked_entities:
        new_ids = entity_to_triplets[entity] - kept_ids
        n_entities_added += 1
        for tid in new_ids:
            r = by_id[tid]
            for e in (r["subject"], r["object"]) if r["subject"] != r["object"] else (r["subject"],):
                if entity_degree_kept[e] == 0:
                    n_entities_kept += 1
                entity_degree_kept[e] += 1
                sum_degree_kept += 1
        kept_ids |= new_ids

        realized_mean = sum_degree_kept / n_entities_kept if n_entities_kept else 0.0
        if realized_mean > best_mean:
            best_mean = realized_mean
            best_prefix_len = n_entities_added
        if realized_mean >= target_mean:
            hit_target = True
            break
        if len(kept_ids) >= n0:
            break

    if not hit_target and best_prefix_len < n_entities_added:
        kept_ids = _replay(best_prefix_len)

    kept_records = [r for r in records if r[id_key] in kept_ids]
    realized_stats = compute_stats(kept_records, id_key)
    realized_factor = (
        round(realized_stats["mean_degree"] / orig_stats["mean_degree"], 4)
        if orig_stats["mean_degree"] else 0.0
    )
    stats = {
        "algorithm": "densify_by_restriction",
        "requested_factor": factor,
        "realized_factor": realized_factor,
        "seed": None,
        "target_reached": hit_target,
        "n_entities_kept_of": (realized_stats["n_entities"], len(degree0)),
        "original": orig_stats,
        "realized": realized_stats,
    }
    return kept_records, stats


# ----------------------------------------------------------------------
# Public entry point
# ----------------------------------------------------------------------

def apply_density(
    records: list[Record],
    factor: float,
    seed: int = 42,
    id_key: str = "id",
) -> tuple[list[Record], dict]:
    """(kept_records, stats) for the requested density factor.

    factor == 1.0 is a no-op: returns `records` unchanged (same list
    contents and order — byte-identical to current/default loader
    behavior), with stats reflecting the unmodified graph.
    """
    if factor <= 0:
        raise ValueError(f"density factor must be > 0, got {factor}")

    if factor == 1.0:
        stats0 = compute_stats(records, id_key)
        return list(records), {
            "algorithm": "none",
            "requested_factor": 1.0,
            "realized_factor": 1.0,
            "seed": seed,
            "original": stats0,
            "realized": stats0,
        }
    elif factor < 1.0:
        return _sparsify(records, factor, seed, id_key)
    else:
        return _densify(records, factor, id_key)
