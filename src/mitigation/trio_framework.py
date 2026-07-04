"""
Trio framework — provenance-aware contamination mitigation (Phase 3, RQ4).

Inspired by Stanford's Trio/ULDB (Uncertainty-Lineage Databases): every KG
node is an x-tuple (value, confidence, lineage), and the three mitigation
mechanisms all operate on that provenance:

1. Confidence propagation (this module, applied at WRITE time by the
   ExtractionAgent): a derived triplet's confidence is computed from its
   lineage parents via arithmetization of the lineage formula —
   conjunction ("derived from all of these") multiplies parent confidences,
   assuming independence, times the extractor's base confidence.
   Consequence: confidence decays with derivation depth, so agent-written
   generations sink toward the retrieval floor while pristine sources stay
   at 1.0. Without this, every derived fact enters at a flat default and
   the floor separates nothing.

2. Retrieval confidence floor (enforced by callers via the min_confidence
   parameter of Neo4jClient.get_related_triplets): agents only consume
   facts above the floor. Confidence is the ONLY retrieval currency —
   quarantined nodes are excluded because deprecation zeroes their
   confidence, not via a state check. That keeps the mechanism pure Trio:
   one number decides visibility.

3. Cascade deprecation (this module, triggered by the ValidationAgent when
   a node is quarantined): walk DERIVED_FROM lineage edges transitively and
   quarantine every downstream dependent — if a source was contaminated,
   everything built on it is suspect. This intentionally over-quarantines
   (a derived node may have had other, clean parents); the collateral
   damage is measured, not assumed away (detection confusion in the
   contamination runner).

Ground rules preserved: this module writes `state`/`confidence` only —
never `error_type` (ground truth belongs to the injector/experimenter).
"""

from __future__ import annotations

from math import prod

from loguru import logger

from src.graph.neo4j_client import Neo4jClient
from src.graph.provenance_schema import STATE_RECOVERED

# Deprecated nodes drop to zero confidence — below any sensible retrieval
# floor, which is what actually removes them from circulation.
DEPRECATED_CONFIDENCE = 0.0


def propagate_confidence(
    parent_confidences: list[float],
    base_confidence: float,
) -> float:
    """
    Arithmetized conjunction: confidence of a triplet derived from ALL its
    lineage parents = product of parent confidences × the extractor's base
    confidence (its own error rate). Assumes parent independence — the
    standard ULDB simplification; documented as a limitation.

    No parents (a root extraction) → just the base confidence.
    """
    conf = base_confidence * prod(parent_confidences)
    return max(0.0, min(1.0, conf))


def noisy_or(confidences: list[float]) -> float:
    """
    Arithmetized disjunction (independent alternatives):
    P(any) = 1 - ∏(1 - p_i). Used when a fact has ALTERNATIVE derivations
    (disjunctive lineage) — corroboration raises confidence.
    """
    return max(0.0, min(1.0, 1.0 - prod(1.0 - c for c in confidences)))


def cascade_deprecate(client: Neo4jClient, source_triplet_id: str) -> int:
    """
    Walk DERIVED_FROM edges from *source_triplet_id* and quarantine every
    transitively derived triplet: state=R, confidence=DEPRECATED_CONFIDENCE.

    Returns the number of newly quarantined nodes. Idempotent — already-
    Recovered nodes are skipped.
    """
    downstream = client.get_downstream(source_triplet_id)
    count = 0
    for t in downstream:
        if t.get("state") != STATE_RECOVERED:
            client.update_state(t["id"], STATE_RECOVERED)
            client.update_confidence(t["id"], DEPRECATED_CONFIDENCE)
            count += 1
    if count:
        logger.info(
            f"[trio] Cascade deprecation from {source_triplet_id}: "
            f"{count} downstream nodes quarantined."
        )
    return count
