"""
Offline unit test for src/graph/density.py — the KG density manipulation
algorithms (task #21, RQ3 "graph density" axis).

Exercises `apply_density` on a small synthetic triplet list. No Neo4j
connection required. Run from project root with venv active:
    python scripts/test_density.py
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.graph.density import apply_density, compute_entity_degree, compute_stats

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


def make_hub_and_spoke() -> list[dict]:
    """68 triplets, deliberately built with slack so both algorithms have
    room to operate:
      - 4 hubs (H1..H4), high degree.
      - 30 bridge spokes (S1..S30), each connected to exactly 2 hubs
        (round-robin) -> degree 2 each. These are droppable-once under
        sparsify's protection rule (dropping one of their two edges still
        leaves them at degree 1, never zero) and are what densify's
        "union of hub neighborhoods" logic concentrates onto.
      - 5 leaf spokes (L1..L5) attached only to H1 -> degree 1, exercise
        sparsify's protection rule (never droppable) and densify's
        "still pulled in by a kept hub" path.
      - 3 fully isolated degree-1/degree-1 pairs (iso_aN/iso_bN), never
        touched by any hub -> exercise both "never droppable" (sparsify)
        and "excluded first" (densify) behavior.
    """
    records = []
    tid = 0

    def add(subj, obj):
        nonlocal tid
        records.append({
            "id": f"trex_{tid}",
            "subject": subj,
            "predicate": "rel",
            "object": obj,
            "source_text": "",
            "source": "synthetic",
        })
        tid += 1

    hubs = ["H1", "H2", "H3", "H4"]
    for i in range(1, 31):
        spoke = f"S{i}"
        h_a = hubs[i % 4]
        h_b = hubs[(i + 1) % 4]
        add(h_a, spoke)
        add(h_b, spoke)
    for i in range(1, 6):
        add("H1", f"L{i}")
    for i in range(1, 4):
        add(f"iso_a{i}", f"iso_b{i}")

    return records


def make_star_graph() -> list[dict]:
    """26 triplets, star topology (sized for densify's "concentrate onto
    fewer entities" behavior, which needs neighborhoods that overlap /
    dominate the triplet count — the bridge-spoke graph above deliberately
    does NOT have that property, since its hub neighborhoods are disjoint):
      - H1: 10 exclusive spokes (S1..S10) -> degree 10, pure hub.
      - H2: 6 spokes, 2 of which (S1, S2) are ALSO H1's spokes (bridge
        entities, degree 2) -> degree 6.
      - 4 fully isolated degree-1/degree-1 pairs, touched by no hub.
    H1 alone covers 10/26 triplets touching only 11 entities — restricting
    to {H1, H2} covers 14/26 triplets (S1, S2 shared) touching 13 entities,
    a clear concentration versus the 4 isolated pairs (8 entities / 4
    triplets, degree 1 throughout) that get excluded first.
    """
    records = []
    tid = 0

    def add(subj, obj):
        nonlocal tid
        records.append({
            "id": f"trex_{tid}",
            "subject": subj,
            "predicate": "rel",
            "object": obj,
            "source_text": "",
            "source": "synthetic",
        })
        tid += 1

    for i in range(1, 11):
        add("H1", f"S{i}")
    add("H2", "S1")
    add("H2", "S2")
    for i in range(11, 15):
        add("H2", f"S{i}")
    for i in range(1, 5):
        add(f"iso_a{i}", f"iso_b{i}")

    return records


def test_noop_factor_1():
    print("\n--- factor == 1.0 is a byte-identical no-op ---")
    records = make_hub_and_spoke()
    kept, stats = apply_density(records, 1.0, seed=42)
    check("same length", len(kept) == len(records), f"{len(kept)} vs {len(records)}")
    check("same objects/order", kept == records)
    check("realized_factor == 1.0", stats["realized_factor"] == 1.0)
    check("algorithm == none", stats["algorithm"] == "none")


def test_sparsify_shrinks_mean_degree():
    print("\n--- factor 0.5: sparsification shrinks mean entity degree ---")
    records = make_hub_and_spoke()
    orig_stats = compute_stats(records)
    kept, stats = apply_density(records, 0.5, seed=42)
    check("n_triplets dropped", len(kept) < len(records),
          f"{len(kept)} kept of {len(records)}")
    check("mean_degree decreased",
          stats["realized"]["mean_degree"] < orig_stats["mean_degree"],
          f"{orig_stats['mean_degree']} -> {stats['realized']['mean_degree']}")
    # Adaptive check: either the full target was reached (realized_factor
    # close to requested) or coverage-protection kicked in early, in which
    # case the shortfall must be honestly reported (realized_factor >
    # requested, never silently "close enough").
    if not stats["coverage_preserving_stop"]:
        check("full target reached: realized_factor close to requested",
              abs(stats["realized_factor"] - 0.5) < 0.15,
              f"realized_factor={stats['realized_factor']}")
    else:
        check("best-effort shortfall honestly reported (realized > requested)",
              stats["realized_factor"] > 0.5,
              f"realized_factor={stats['realized_factor']}")
        check("still made nonzero progress toward the target",
              stats["n_dropped"] > 0, f"n_dropped={stats['n_dropped']}")
    # coverage preservation: every entity present before should still have
    # >=1 triplet after, EXCEPT where preservation was structurally
    # impossible (never, for this synthetic graph, since isolated pairs
    # have low weight = min(1,1) and are the last to be dropped)
    kept_degree = compute_entity_degree(kept)
    orig_degree = compute_entity_degree(records)
    missing = set(orig_degree) - set(kept_degree)
    check("entity coverage fully preserved on this graph", len(missing) == 0,
          f"missing entities: {missing}")
    # hub H1 (highest weight) should have lost more of its edges,
    # proportionally, than the low-degree isolated pairs
    h1_kept_frac = kept_degree.get("H1", 0) / orig_degree["H1"]
    iso_kept_frac = kept_degree.get("iso_a1", 0) / orig_degree["iso_a1"]
    check("hub H1 thinned more than isolated low-degree entity",
          h1_kept_frac <= iso_kept_frac,
          f"H1 kept {h1_kept_frac:.2f}, iso_a1 kept {iso_kept_frac:.2f}")


def test_sparsify_determinism():
    print("\n--- sparsification is deterministic under a fixed seed ---")
    records = make_hub_and_spoke()
    kept1, stats1 = apply_density(records, 0.5, seed=42)
    kept2, stats2 = apply_density(records, 0.5, seed=42)
    ids1 = [r["id"] for r in kept1]
    ids2 = [r["id"] for r in kept2]
    check("identical kept-set across repeated runs, same seed", ids1 == ids2)
    kept3, _ = apply_density(records, 0.5, seed=7)
    ids3 = [r["id"] for r in kept3]
    check("different seed CAN change the kept set (sanity, not guaranteed)",
          True, f"seed42 n={len(ids1)} seed7 n={len(ids3)}")


def test_densify_raises_mean_degree():
    print("\n--- factor 2.0: densification-by-restriction raises mean degree ---")
    records = make_star_graph()
    orig_stats = compute_stats(records)
    kept, stats = apply_density(records, 2.0, seed=42)
    check("n_entities shrank", stats["realized"]["n_entities"] < orig_stats["n_entities"],
          f"{orig_stats['n_entities']} -> {stats['realized']['n_entities']}")
    check("mean_degree increased",
          stats["realized"]["mean_degree"] > orig_stats["mean_degree"],
          f"{orig_stats['mean_degree']} -> {stats['realized']['mean_degree']}")
    check("no fabricated records: kept is a subset of original ids",
          {r["id"] for r in kept} <= {r["id"] for r in records})
    check("no fabricated records: every kept record byte-identical to source",
          all(r in records for r in kept))
    # isolated low-degree entities should be the first casualties
    kept_entities = set(compute_entity_degree(kept).keys())
    check("isolated pair (iso_a1,iso_b1) excluded by restriction to hubs",
          "iso_a1" not in kept_entities,
          f"kept_entities sample: {sorted(kept_entities)[:6]}")
    check("hub H1 retained", "H1" in kept_entities)


def test_densify_unreachable_factor_reports_honestly():
    print("\n--- unreachable density factor stops at full budget, reports shortfall ---")
    records = make_star_graph()
    kept, stats = apply_density(records, 100.0, seed=42)
    check("kept set capped at original triplet budget",
          len(kept) <= len(records), f"{len(kept)} vs {len(records)}")
    check("realized_factor < requested_factor (honest shortfall)",
          stats["realized_factor"] < 100.0, f"realized_factor={stats['realized_factor']}")


def test_refuses_invalid_factor():
    print("\n--- factor <= 0 raises ---")
    records = make_hub_and_spoke()
    try:
        apply_density(records, 0.0, seed=42)
        check("raises ValueError on factor=0", False)
    except ValueError:
        check("raises ValueError on factor=0", True)
    try:
        apply_density(records, -1.0, seed=42)
        check("raises ValueError on negative factor", False)
    except ValueError:
        check("raises ValueError on negative factor", True)


if __name__ == "__main__":
    test_noop_factor_1()
    test_sparsify_shrinks_mean_degree()
    test_sparsify_determinism()
    test_densify_raises_mean_degree()
    test_densify_unreachable_factor_reports_honestly()
    test_refuses_invalid_factor()
    print(f"\n{PASS} all density tests passed\n")
