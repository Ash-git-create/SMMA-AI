"""
Provenance schema for KG triplets — implements the x-tuple structure from
the Trio framework: each triplet stores (value, confidence, lineage_formula).

SIR states:
  S — Susceptible: pristine T-REx ground-truth, not yet contaminated
  I — Infected: contains an error (injected or hallucinated)
  R — Recovered: flagged by ValidationAgent, quarantined

IMPORTANT — ground truth vs detection:
  `state` records the *detected/operational* SIR status, written by agents
  (OrchestrationAgent marks I, ValidationAgent marks R). Ground-truth
  contamination is marked independently via `error_type`, set ONLY by the
  ErrorInjector. Detection metrics (AUROC) compare state against error_type;
  agents must never write error_type, and truth must never be inferred from
  state alone.

Lineage formula: DNF boolean string linking a derived node to its ancestors.
  Baseline triplet: lineage = its own source_id  (it IS the source)
  Derived triplet:  lineage = "src_a AND src_b"  (conjunction of parents)
  Uncertainty:      lineage = "src_a OR src_b"   (disjunction)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

BASELINE_AGENT_ID = "baseline_loader"
STATE_SUSCEPTIBLE = "S"
STATE_INFECTED = "I"
STATE_RECOVERED = "R"


@dataclass
class TripletMetadata:
    source_id: str
    agent_id: str
    timestamp: str
    confidence: float
    lineage: str
    state: str = STATE_SUSCEPTIBLE
    error_type: Optional[str] = None  # qualifier_loss | entity_disambiguation | relation_strengthening

    @classmethod
    def baseline(cls, source_id: str) -> TripletMetadata:
        """Metadata for a T-REx ground-truth triplet: full confidence, Susceptible."""
        return cls(
            source_id=source_id,
            agent_id=BASELINE_AGENT_ID,
            timestamp=datetime.now(timezone.utc).isoformat(),
            confidence=1.0,
            lineage=source_id,
            state=STATE_SUSCEPTIBLE,
        )

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
            "lineage": self.lineage,
            "state": self.state,
            "error_type": self.error_type,
        }


class LineageFormula:
    """Build DNF lineage formulas from parent source IDs."""

    @staticmethod
    def from_single(source_id: str) -> str:
        return source_id

    @staticmethod
    def conjunction(parent_ids: list[str]) -> str:
        """All parents must hold — used when a triplet synthesises from N sources."""
        return " AND ".join(parent_ids)

    @staticmethod
    def disjunction(parent_ids: list[str]) -> str:
        """Any parent suffices — used when source is uncertain."""
        return " OR ".join(parent_ids)

    @staticmethod
    def ancestors(formula: str) -> set[str]:
        """Return all source IDs referenced in a lineage formula."""
        tokens = formula.replace("(", "").replace(")", "").split()
        return {t for t in tokens if t not in ("AND", "OR")}
