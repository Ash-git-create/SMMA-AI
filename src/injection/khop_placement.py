"""
K-hop graded seed placement — the RQ1/RQ3 bridge.

--seed-placement in run_contamination.py is a binary contrast: 'active'
(index cases inside the active retrieval subgraph) vs 'random' (uniform
over the whole KG). That answers "does retrieval-reachability matter at
all" but not "how does reach/harm fall off with graph distance from the
workload" — the RQ3 question (graph density / distance effects on
contamination velocity). This module fills the gradient in between.

Distance is defined over the Entity-Triplet bipartite graph (see
src/graph/neo4j_client.py docstring for the schema):
    (:Entity)-[:SUBJECT_OF]->(:Triplet)-[:HAS_OBJECT]->(:Entity)
Two triplets are 1 hop apart if they share an Entity node — as subject or
object, in either triplet. Distance from the ACTIVE SET (the union of the
active entity keys' retrieval neighborhoods, i.e. the existing
build_active_pool() in run_contamination.py) is the minimum number of such
hops from any triplet already in that set:
    k=0 — the active pool itself (identical to --seed-placement active).
    k=1 — shares an entity with the active neighborhood but is not in it.
    k=2 — one hop further out, excluding everything seen at k=0/1.
    k=3 — one hop further still. This is the audited cap (MAX_K); the KG's
          entity-degree distribution means most of a ~50K-triplet KG is
          reachable within a handful of hops from any sizeable active set,
          so k>3 frontiers tend to blur into "most of the graph" — i.e.
          the qualitative equivalent of --seed-placement random, which
          already exists as its own arm and needs no k-hop machinery.

Expansion is set-wise via Neo4jClient.get_adjacent_triplets (one Cypher
query per hop per frontier batch), never a per-triplet loop.
"""

from __future__ import annotations

from typing import Optional, Protocol

from loguru import logger

from src.graph.provenance_schema import STATE_SUSCEPTIBLE

MAX_K = 3


class AdjacencyClient(Protocol):
    """The slice of Neo4jClient this module depends on — lets the hop
    logic be unit-tested with a plain stub, no live Neo4j required."""

    def get_adjacent_triplets(
        self,
        frontier_ids: list[str],
        exclude_ids: set,
        state: Optional[str] = None,
        limit: int = 5000,
    ) -> list[dict]: ...


def khop_frontier(
    client: AdjacencyClient,
    active_pool: list[dict],
    k: int,
    pool_size: int,
    frontier_cap: int = 5000,
) -> tuple[list[dict], dict[str, int]]:
    """
    Walk outward from `active_pool` (the k=0 active-subgraph pool, already
    built by run_contamination.build_active_pool) and return Susceptible
    triplets at EXACT bipartite-graph distance k, plus an id->k map for
    manifest auditing (the realized distance of every chosen index case
    must be traceable, not assumed from the requested k).

    k=0 returns active_pool itself, truncated to pool_size — bit-identical
    in content to the pre-existing 'active' placement.

    Each hop excludes every triplet seen at a smaller distance (so pool
    membership is the EXACT hop, not "at most k"), and is capped at
    `frontier_cap` per hop to bound the Cypher query against dense hub
    entities. If a hop's frontier comes back empty (the active
    neighborhood's local subgraph is exhausted before reaching k), the
    walk stops early and returns whatever was found at the last
    successful hop — logged, not silently padded.
    """
    if k < 0:
        raise ValueError(f"k must be >= 0, got {k}")
    if k > MAX_K:
        logger.warning(
            f"[khop] k={k} exceeds the audited cap ({MAX_K}); proceeding, "
            f"but distances beyond {MAX_K} hops are unvalidated territory "
            f"(likely graph-wide reach — consider --seed-placement random instead)."
        )

    seen_ids = {t["id"] for t in active_pool}
    if k == 0:
        pool = active_pool[:pool_size]
        return pool, {t["id"]: 0 for t in pool}

    frontier_ids = list(seen_ids)
    hop_pool: list[dict] = []
    for hop in range(1, k + 1):
        hop_pool = client.get_adjacent_triplets(
            frontier_ids, exclude_ids=seen_ids,
            state=STATE_SUSCEPTIBLE, limit=frontier_cap,
        )
        if not hop_pool:
            logger.warning(
                f"[khop] frontier exhausted at hop {hop}/{k} — no unseen "
                f"Susceptible triplet shares an entity with the hop-{hop - 1} "
                f"frontier. Pool will be smaller than requested (or empty)."
            )
            break
        seen_ids |= {t["id"] for t in hop_pool}
        frontier_ids = [t["id"] for t in hop_pool]

    pool = hop_pool[:pool_size]
    return pool, {t["id"]: k for t in pool}
