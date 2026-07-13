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
from src.mitigation import trio_framework


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
    oracle:
        If True, quarantine decisions come from the experimenter's ground
        truth (the `error_type` property written by the ErrorInjector and the
        transmission bookkeeping) instead of the LLM judge — zero LLM calls
        per audit. This is the RQ4 upper-bound arm: it keeps the entire Trio
        architecture (targeted audits, quarantine, cascade deprecation)
        while replacing the judge with perfect judgement, isolating
        judge-precision effects from architecture effects. Confidence of
        clean nodes is never touched (no re-scoring), so the confidence-
        laundering channel is absent by construction.
    validator_prompt:
        Judge prompt variant for the internal OrchestrationAgent ("default"
        or "tuned" — the task #20 quote-first prompt). Ignored when oracle
        is True or an explicit orchestration_agent is supplied.
    """

    def __init__(
        self,
        agent_id: str = "validation_agent",
        quarantine_threshold: float = 0.4,
        orchestration_agent: Optional[OrchestrationAgent] = None,
        neo4j_client: Optional[Neo4jClient] = None,
        oracle: bool = False,
        validator_prompt: str = "default",
    ):
        self.agent_id = agent_id
        self.quarantine_threshold = quarantine_threshold
        self.oracle = oracle
        self._orchestrator = None if oracle else (
            orchestration_agent
            or OrchestrationAgent(infection_threshold=quarantine_threshold,
                                  validator_prompt=validator_prompt)
        )
        self._external_client = neo4j_client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_audit_pass(
        self,
        sample_size: int = 100,
        candidates: Optional[list[str]] = None,
    ) -> dict:
        """
        Run one audit pass over Susceptible and Infected triplets.

        candidates: optional explicit triplet IDs to audit (capped at
        sample_size). This is TARGETED validation — auditing the facts agents
        actually read and wrote this cycle. Uniform random sampling (the
        default) audits each node with probability sample_size/|KG|, which at
        KG scale makes gamma vanish: 50 audits over a 51K-node graph touch a
        given corrupted node with p≈0.001 per pass. Where the validator looks
        is as much a design variable as how often it runs.

        Returns a summary dict:
            {audited, quarantined, cascaded, sir_counts}
        """
        client = self._external_client or Neo4jClient()
        try:
            return self._audit(client, sample_size, candidates)
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
        triplets derived from it (transitively). Delegates to the Trio
        framework — the algorithm is the mitigation mechanism itself.

        Returns the count of newly quarantined nodes.
        """
        client = self._external_client or Neo4jClient()
        try:
            return trio_framework.cascade_deprecate(client, source_triplet_id)
        finally:
            if self._external_client is None:
                client.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _audit(
        self,
        client: Neo4jClient,
        sample_size: int,
        candidate_ids: Optional[list[str]] = None,
    ) -> dict:
        if candidate_ids is not None:
            # Targeted mode: audit the given nodes (skip already-quarantined).
            candidates = []
            for tid in candidate_ids[:sample_size]:
                t = client.get_triplet(tid)
                if t is not None and t.get("state") != STATE_RECOVERED:
                    candidates.append(t)
        else:
            # Uniform random sample of Susceptible + Infected nodes.
            # randomize=True is required — without it Neo4j returns the same
            # rows every pass, so the audit would re-check identical nodes.
            candidates = client.search_triplets(
                state=STATE_SUSCEPTIBLE, limit=sample_size // 2, randomize=True
            )
            candidates += client.search_triplets(
                state=STATE_INFECTED, limit=sample_size // 2, randomize=True
            )

        audited = len(candidates)
        quarantined = 0
        cascaded = 0

        for triplet in candidates:
            tid = triplet["id"]

            if self.oracle:
                # Ground-truth verdict: any error_type (seeded or
                # propagated_*) marks the node as contaminated.
                if triplet.get("error_type"):
                    client.update_state(tid, STATE_RECOVERED)
                    client.update_confidence(tid, 0.0)
                    quarantined += 1
                    logger.debug(
                        f"[{self.agent_id}] Quarantined {tid} "
                        f"(oracle, error_type={triplet['error_type']})"
                    )
                    cascaded += self.cascade_deprecate(tid)
                continue

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
