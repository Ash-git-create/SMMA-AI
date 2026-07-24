"""
Smoke-test for k-hop graded seed placement (task #21 component).

Tests src.injection.khop_placement.khop_frontier — the hop-bookkeeping
logic (frontier expansion, exclusion of already-seen triplets, exact-k
tagging, pool_size truncation, early-exhaustion handling) — against a
fake in-memory adjacency client, so no live Neo4j is required. The Cypher
query in Neo4jClient.get_adjacent_triplets itself needs a live-KG smoke
test (see the snippet at the bottom of this file / khop_placement.py
docstring) — that part is NOT exercised here.

Run from project root with venv active:
    python scripts/test_khop_placement.py
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.injection.khop_placement import MAX_K, khop_frontier

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"


def check(name: str, condition: bool, detail: str = "") -> None:
    tag = PASS if condition else FAIL
    msg = f"  [{tag}] {name}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    if not condition:
        sys.exit(1)


def _triplet(tid: str) -> dict:
    return {"id": tid, "subject": f"s{tid}", "predicate": "p", "object": f"o{tid}"}


class FakeAdjacencyClient:
    """Deterministic stand-in for Neo4jClient.get_adjacent_triplets.

    `hops` maps hop-index (1-based) -> the full candidate list that hop
    would surface BEFORE exclusion, so the test can assert the exclusion
    logic (previously-seen ids must never reappear) actually happens in
    khop_frontier rather than being pre-baked into the fixture.
    """

    def __init__(self, hops: dict[int, list[dict]]):
        self.hops = hops
        self.calls: list[tuple[list[str], set, str | None, int]] = []
        self._call_n = 0

    def get_adjacent_triplets(self, frontier_ids, exclude_ids, state=None, limit=5000):
        self._call_n += 1
        self.calls.append((list(frontier_ids), set(exclude_ids), state, limit))
        candidates = self.hops.get(self._call_n, [])
        return [t for t in candidates if t["id"] not in exclude_ids][:limit]


def test_k0_returns_active_pool_unchanged():
    print("\n--- khop_frontier: k=0 ---")
    active_pool = [_triplet("a1"), _triplet("a2"), _triplet("a3")]
    client = FakeAdjacencyClient(hops={})  # k=0 must never call the client
    pool, hop_map = khop_frontier(client, active_pool, k=0, pool_size=10)

    check("k=0 pool == active_pool", pool == active_pool)
    check("k=0 all tagged khop=0", all(v == 0 for v in hop_map.values()))
    check("k=0 hop_map covers every returned id",
          set(hop_map) == {t["id"] for t in pool})
    check("k=0 never calls the adjacency client", client._call_n == 0)


def test_k1_excludes_active_pool_and_tags_correctly():
    print("\n--- khop_frontier: k=1 ---")
    active_pool = [_triplet("a1"), _triplet("a2")]
    hop1_candidates = [_triplet("a1"), _triplet("b1"), _triplet("b2")]  # a1 must be filtered
    client = FakeAdjacencyClient(hops={1: hop1_candidates})
    pool, hop_map = khop_frontier(client, active_pool, k=1, pool_size=10)

    ids = {t["id"] for t in pool}
    check("k=1 excludes active-pool ids", "a1" not in ids and "a2" not in ids)
    check("k=1 includes true 1-hop neighbors", ids == {"b1", "b2"})
    check("k=1 all tagged khop=1", all(v == 1 for v in hop_map.values()))
    check("k=1 makes exactly one adjacency call", client._call_n == 1)
    frontier_arg, exclude_arg, state_arg, _ = client.calls[0]
    check("k=1 frontier seeded from active_pool ids",
          set(frontier_arg) == {"a1", "a2"})
    check("k=1 exclude set == active_pool ids", exclude_arg == {"a1", "a2"})
    check("k=1 filters to Susceptible", state_arg == "S")


def test_k2_excludes_both_prior_frontiers():
    print("\n--- khop_frontier: k=2 ---")
    active_pool = [_triplet("a1")]
    hop1 = [_triplet("b1"), _triplet("b2")]
    # hop2 candidate list re-surfaces a1/b1 (should be filtered) plus new c-nodes
    hop2 = [_triplet("a1"), _triplet("b1"), _triplet("c1"), _triplet("c2")]
    client = FakeAdjacencyClient(hops={1: hop1, 2: hop2})
    pool, hop_map = khop_frontier(client, active_pool, k=2, pool_size=10)

    ids = {t["id"] for t in pool}
    check("k=2 excludes k=0 and k=1 ids", ids == {"c1", "c2"})
    check("k=2 all tagged khop=2", all(v == 2 for v in hop_map.values()))
    check("k=2 makes exactly two adjacency calls", client._call_n == 2)
    # second call's frontier must be hop1's output (b1, b2), not active_pool
    frontier_arg2, exclude_arg2, _, _ = client.calls[1]
    check("k=2 second-hop frontier is hop-1 output", set(frontier_arg2) == {"b1", "b2"})
    check("k=2 second-hop excludes a1+b1+b2", exclude_arg2 == {"a1", "b1", "b2"})


def test_pool_size_truncation():
    print("\n--- khop_frontier: pool_size truncation ---")
    active_pool = [_triplet("a1")]
    hop1 = [_triplet(f"b{i}") for i in range(10)]
    client = FakeAdjacencyClient(hops={1: hop1})
    pool, hop_map = khop_frontier(client, active_pool, k=1, pool_size=3)

    check("pool truncated to pool_size", len(pool) == 3)
    check("hop_map matches truncated pool", len(hop_map) == 3)


def test_frontier_exhaustion_stops_early_no_crash():
    print("\n--- khop_frontier: frontier exhaustion ---")
    active_pool = [_triplet("a1")]
    # hop1 returns nothing — k=3 should stop after hop 1, not crash on hop 2/3
    client = FakeAdjacencyClient(hops={1: []})
    pool, hop_map = khop_frontier(client, active_pool, k=3, pool_size=10)

    check("exhausted frontier returns empty pool, no crash", pool == [])
    check("exhausted frontier returns empty hop_map", hop_map == {})
    check("stops after the empty hop (no call 2/3)", client._call_n == 1)


def test_k_validation_and_beyond_cap_warns_not_raises():
    print("\n--- khop_frontier: k bounds ---")
    active_pool = [_triplet("a1")]
    try:
        khop_frontier(FakeAdjacencyClient({}), active_pool, k=-1, pool_size=5)
        check("negative k raises", False)
    except ValueError:
        check("negative k raises ValueError", True)

    # k > MAX_K should proceed (warn, not raise)
    hops = {i: [_triplet(f"x{i}_{j}") for j in range(2)] for i in range(1, MAX_K + 2)}
    client = FakeAdjacencyClient(hops=hops)
    pool, hop_map = khop_frontier(client, active_pool, k=MAX_K + 1, pool_size=10)
    check("k > MAX_K still returns a pool (warns, does not raise)", len(pool) > 0)
    check(f"k={MAX_K + 1} pool tagged with that k", all(v == MAX_K + 1 for v in hop_map.values()))


if __name__ == "__main__":
    test_k0_returns_active_pool_unchanged()
    test_k1_excludes_active_pool_and_tags_correctly()
    test_k2_excludes_both_prior_frontiers()
    test_pool_size_truncation()
    test_frontier_exhaustion_stops_early_no_crash()
    test_k_validation_and_beyond_cap_warns_not_raises()
    print(f"\n\033[32mAll tests passed.\033[0m\n")
