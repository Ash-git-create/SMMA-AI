"""
ValidationAgent — audits KG nodes, flags low-confidence triplets, triggers cascade deprecation.

Responsibilities:
  1. Scan all Susceptible (S) triplets and re-score them via OrchestrationAgent.
  2. Mark low-confidence triplets as Recovered (R) — quarantined, not queried.
  3. Walk lineage graph: deprecate all downstream triplets derived from a bad source.
  4. Report SIR state counts after each audit pass.

The ValidationAgent is the "gamma" term in the SIR model:
  higher validation frequency → higher gamma → lower R₀.

Usage:
    from src.agents.validation_agent import ValidationAgent
    agent = ValidationAgent(quarantine_threshold=0.4)
    report = agent.run_audit_pass(sample_size=200)
"""

from __future__ import annotations

from typing import Optional

from loguru import logger

from src.agents.orchestration_agent import OrchestrationAgent
from src.graph.neo4j_client import Neo4jClient
from src.graph.provenance_schema import (
    STATE_INFECTED,
    STATE_RECOVERED,
    STATE_SUSCEPTIBLE,
)


class ValidationAgent:
    """
    Audits the KG, quarantines suspicious triplets, and cascades deprecation.

    Parameters
    ----------
    agent_id:
        Identifier for this agent instance.
    quarantine_threshold:
        Triplets with confidence below this are moved to state=R (Recovered/quarantined).
    orchestration_agent:
        Optional pre-built OrchestrationAgent. If None, one is created internally.
    neo4j_client:
        Optional pre-built Neo4jClient.
    """

    def __init__(
        self,
        agent_id: str = "validation_agent",
        quarantine_threshold: float = 0.4,
        orchestration_agent: Optional[OrchestrationAgent] = None,
        neo4j_client: Optional[Neo4jClient] = None,
    ):
        self.agent_id = agent_id
        self.quarantine_threshold = quarantine_threshold
        self._orchestrator = orchestration_agent or OrchestrationAgent(
            infection_threshold=quarantine_threshold
        )
        self._external_client = neo4j_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_audit_pass(self, sample_size: int = 100) -> dict:
        """
        Run one audit pass over Susceptible and Infected triplets.

        Samples up to *sample_size* triplets, validates each, quarantines failures,
        then cascades deprecation from confirmed infected nodes.

        Returns a summary dict:
            {audited, quarantined, cascaded, sir_counts}
        """
        client = self._external_client or Neo4jClient()
        try:
            return self._audit(client, sample_size)
        finally:
            if self._external_client is None:
                client.close()

    def quarantine_triplet(self, triplet_id: str) -> None:
        """Directly mark a triplet as Recovered (quarantined) without re-scoring."""
        client = self._external_client or Neo4jClient()
        try:
            client.update_state(triplet_id, STATE_RECOVERED)
            client.update_confidence(triplet_id, 0.0)
            logger.info(f"[{self.agent_id}] Quarantined: {triplet_id}")
        finally:
            if self._external_client is None:
                client.close()

    def cascade_deprecate(self, source_triplet_id: str) -> int:
        """
        Walk the lineage graph from *source_triplet_id* and quarantine all
        triplets derived from it (transitively).

        Returns the count of newly quarantined nodes.
        """
        client = self._external_client or Neo4jClient()
        try:
            downstream = client.get_downstream(source_triplet_id)
            count = 0
            for t in downstream:
                if t.get("state") != STATE_RECOVERED:
                    client.update_state(t["id"], STATE_RECOVERED)
                    client.update_confidence(t["id"], 0.0)
                    count += 1
            if count:
                logger.info(
                    f"[{self.agent_id}] Cascade deprecation from {source_triplet_id}: "
                    f"{count} downstream nodes quarantined."
                )
            return count
        finally:
            if self._external_client is None:
                client.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _audit(self, client: Neo4jClient, sample_size: int) -> dict:
        # Pull candidates: Susceptible + Infected nodes to check
        candidates = client.search_triplets(state=STATE_SUSCEPTIBLE, limit=sample_size // 2)
        candidates += client.search_triplets(state=STATE_INFECTED, limit=sample_size // 2)

        audited = len(candidates)
        quarantined = 0
        cascaded = 0

        for triplet in candidates:
            tid = triplet["id"]
            result = self._orchestrator.validate_triplet(tid)

            if result.get("error"):
                continue

            new_conf = result.get("new_confidence", triplet.get("confidence", 1.0))

            if new_conf < self.quarantine_threshold:
                # Move to Recovered (quarantined)
                client.update_state(tid, STATE_RECOVERED)
                client.update_confidence(tid, new_conf)
                quarantined += 1
                logger.debug(
                    f"[{self.agent_id}] Quarantined {tid} "
                    f"(conf={new_conf:.2f}, verdict={result.get('verdict')})"
                )
                # Cascade: deprecate everything derived from this node
                cascaded += self.cascade_deprecate(tid)

        sir_counts = client.count_by_state()
        logger.info(
            f"[{self.agent_id}] Audit pass complete — "
            f"audited={audited}, quarantined={quarantined}, cascaded={cascaded} | "
            f"SIR: {sir_counts}"
        )
        return {
            "audited":     audited,
            "quarantined": quarantined,
            "cascaded":    cascaded,
            "sir_counts":  sir_counts,
        }
