"""
OrchestrationAgent — validates triplets and scores confidence using Llama 3.1 8B.

Responsibilities:
  1. Accept a candidate triplet (SPO) and contextual KG triplets as evidence.
  2. Ask the LLM to judge whether the candidate is supported by the evidence.
  3. Assign a revised confidence score based on the judgment.
  4. Update the triplet's confidence in Neo4j.
  5. Mark a triplet as Infected (state=I) if confidence falls below the threshold.

Usage:
    from src.agents.orchestration_agent import OrchestrationAgent
    agent = OrchestrationAgent()
    result = agent.validate_triplet(triplet_id="uuid-...", context_triplets=[...])
"""

from __future__ import annotations

import json
import re
from typing import Optional

from loguru import logger

from src.agents.llm_client import ModelRole, get_client
from src.graph.neo4j_client import Neo4jClient
from src.graph.provenance_schema import STATE_INFECTED, STATE_SUSCEPTIBLE

_SYSTEM_PROMPT = """\
You are a knowledge graph fact-checker. You receive a candidate fact and a list \
of supporting evidence triplets from a knowledge graph.

Your job is to judge whether the candidate fact is supported by the evidence.

Respond ONLY with a JSON object — no prose:
{
  "verdict": "SUPPORTED" | "UNSUPPORTED" | "UNCERTAIN",
  "confidence": <float 0.0–1.0>,
  "reason": "<one sentence>"
}

Rules:
- SUPPORTED: the candidate is directly or logically implied by the evidence (confidence 0.7–1.0)
- UNSUPPORTED: the candidate contradicts or is absent from the evidence (confidence 0.0–0.35)
- UNCERTAIN: the evidence is ambiguous or incomplete (confidence 0.35–0.7)
"""

# Tuned judge (task #20): adaptation of the winning offline variant
# (v2_quote_first, phase39_validator_tuning.csv — flag precision 0.154 vs
# 0.053, recall 2/2, false alarms 29% vs 47%) to the in-run setting, where
# evidence is KG triplets rather than a source passage. Carries over the two
# structural fixes: (1) evidence-then-verdict ordering — the judge must quote
# the specific evidence line BEFORE labelling; (2) absence of evidence is
# UNCERTAIN, never UNSUPPORTED — under the 0.4 quarantine threshold this is
# the change that stops sparse-evidence pristine nodes being quarantined.
# The JSON contract (verdict/confidence/reason) is unchanged so parsing and
# thresholds stay identical; only the judgement rules differ.
_TUNED_SYSTEM_PROMPT = """\
You are a knowledge graph fact-checker. You receive a candidate fact and a list \
of evidence triplets from the same knowledge graph.

Judge ONLY whether the candidate is consistent with the evidence list — not \
whether it is true in the real world. Do not use world knowledge: a candidate \
that sounds wrong but does not conflict with any evidence line is UNCERTAIN, \
never UNSUPPORTED.

Step 1 — copy the single evidence line most relevant to the candidate into \
"evidence_quote" (verbatim; empty string if no evidence line mentions either \
entity of the candidate).
Step 2 — compare the candidate with that line only, and give the verdict.

Respond ONLY with a JSON object — no prose:
{
  "evidence_quote": "<verbatim evidence line, or empty>",
  "verdict": "SUPPORTED" | "UNSUPPORTED" | "UNCERTAIN",
  "confidence": <float 0.0–1.0>,
  "reason": "<one sentence>"
}

Rules:
- SUPPORTED: the quoted evidence states or implies the candidate (confidence 0.7–1.0). \
Less-specific-but-consistent candidates are SUPPORTED, as are paraphrases and \
reworded predicates.
- UNSUPPORTED: the quoted evidence CONTRADICTS the candidate (confidence 0.0–0.35). \
Requires a non-empty evidence_quote that the candidate contradicts. \
Absence of evidence is NOT contradiction.
- UNCERTAIN: no evidence line mentions the candidate's entities, or the \
comparison is ambiguous (confidence 0.35–0.7).
"""


class OrchestrationAgent:
    """
    Validates a candidate triplet against KG context and updates its confidence.

    Parameters
    ----------
    agent_id:
        Identifier stored in log messages.
    infection_threshold:
        If revised confidence falls below this, the triplet is marked state=I.
    retrieval_threshold:
        Minimum confidence to pull context triplets from the KG.
        0.0 = no floor (Phase 2 baseline, unmitigated). The Trio mitigation
        (Phase 3) raises this — it is the experimental variable of RQ4.
    neo4j_client:
        Optional pre-built client.
    validator_prompt:
        "default" = the original judge prompt (Phase 2/3 arms).
        "tuned" = the task #20 quote-first judge — same model, same JSON
        contract, stricter rules for UNSUPPORTED verdicts.
    llm_client:
        Optional pre-built LLM client (e.g. from
        llm_client.make_anthropic_client(...)) to use instead of the
        role-default client. Used by the task #34 cross-family judge
        replication to route ONLY the in-run validator's judge to Claude
        Haiku, without touching get_client()/ORCHESTRATION_PROVIDER — which
        would also redirect the eval judge (same ModelRole.ORCHESTRATION,
        used by run_contamination.py's task-eval/probe questions) and thus
        violate the "never switch the Groq judge model mid-experiment"
        invariant (CLAUDE.md rule 7). If None (default), behaviour is
        byte-identical to before this parameter existed.
    """

    def __init__(
        self,
        agent_id: str = "orchestration_agent",
        infection_threshold: float = 0.4,
        retrieval_threshold: float = 0.0,
        neo4j_client: Optional[Neo4jClient] = None,
        validator_prompt: str = "default",
        llm_client=None,
    ):
        self.agent_id = agent_id
        self.infection_threshold = infection_threshold
        self.retrieval_threshold = retrieval_threshold
        self._external_client = neo4j_client
        self._llm = llm_client if llm_client is not None else get_client(ModelRole.ORCHESTRATION)
        if validator_prompt not in ("default", "tuned"):
            raise ValueError(f"Unknown validator_prompt: {validator_prompt!r}")
        self._system_prompt = (
            _TUNED_SYSTEM_PROMPT if validator_prompt == "tuned" else _SYSTEM_PROMPT
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate_triplet(
        self,
        triplet_id: str,
        context_triplets: Optional[list[dict]] = None,
    ) -> dict:
        """
        Validate a single triplet by its Neo4j ID.

        If context_triplets is None, fetches them from the KG automatically
        (using the subject of the target triplet as a search key).

        Returns a result dict:
            {triplet_id, verdict, old_confidence, new_confidence, state, reason}
        """
        client = self._external_client or Neo4jClient()
        try:
            return self._run_validation(client, triplet_id, context_triplets)
        finally:
            if self._external_client is None:
                client.close()

    def validate_batch(self, triplet_ids: list[str]) -> list[dict]:
        """Validate a list of triplet IDs. Returns one result dict per triplet."""
        client = self._external_client or Neo4jClient()
        results = []
        try:
            for tid in triplet_ids:
                result = self._run_validation(client, tid, context_triplets=None)
                results.append(result)
        finally:
            if self._external_client is None:
                client.close()
        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _run_validation(
        self,
        client: Neo4jClient,
        triplet_id: str,
        context_triplets: Optional[list[dict]],
    ) -> dict:
        target = client.get_triplet(triplet_id)
        if target is None:
            logger.warning(f"[{self.agent_id}] Triplet not found: {triplet_id}")
            return {"triplet_id": triplet_id, "verdict": "NOT_FOUND", "error": True}

        if context_triplets is None:
            # Evidence = triplets sharing an entity with the target, best
            # confidence first, above the retrieval floor (0.0 = no floor).
            context_triplets = client.get_related_triplets(
                subject=target["subject"],
                obj=target["object"],
                exclude_id=triplet_id,
                min_confidence=self.retrieval_threshold,
                limit=20,
            )

        verdict_data = self._call_llm(target, context_triplets)
        if verdict_data is None:
            # LLM call or parse failed — do NOT touch the KG. Writing a
            # fallback confidence here would let infra failures masquerade
            # as contamination in the measurements.
            logger.warning(f"[{self.agent_id}] LLM failure — no update for {triplet_id}")
            return {
                "triplet_id":     triplet_id,
                "verdict":        "ERROR",
                "old_confidence": target.get("confidence", 1.0),
                "new_confidence": target.get("confidence", 1.0),
                "state":          target.get("state", STATE_SUSCEPTIBLE),
                "reason":         "LLM call or parse failure — skipped",
                "error":          True,
            }

        old_conf = target.get("confidence", 1.0)
        new_conf = verdict_data.get("confidence", old_conf)
        verdict = verdict_data.get("verdict", "UNCERTAIN")
        reason = verdict_data.get("reason", "")

        # Update Neo4j
        client.update_confidence(triplet_id, new_conf)
        new_state = target.get("state", STATE_SUSCEPTIBLE)
        if new_conf < self.infection_threshold and new_state == STATE_SUSCEPTIBLE:
            client.update_state(triplet_id, STATE_INFECTED)
            new_state = STATE_INFECTED
            logger.info(
                f"[{self.agent_id}] Marked INFECTED: {triplet_id} "
                f"(confidence {old_conf:.2f} → {new_conf:.2f})"
            )
        else:
            logger.debug(
                f"[{self.agent_id}] Validated: {triplet_id} verdict={verdict} "
                f"conf {old_conf:.2f} → {new_conf:.2f}"
            )

        return {
            "triplet_id":     triplet_id,
            "verdict":        verdict,
            "old_confidence": old_conf,
            "new_confidence": new_conf,
            "state":          new_state,
            "reason":         reason,
        }

    def _call_llm(self, target: dict, context: list[dict]) -> Optional[dict]:
        """Ask Llama 3.1 8B to judge whether the target triplet is supported.

        Returns None on API failure or unparseable output — callers must
        treat that as "no judgment", never as a confidence value.
        """
        ctx_lines = "\n".join(
            f"  - ({t['subject']}) --[{t['predicate']}]--> ({t['object']})"
            for t in context[:20]
        )
        prompt = (
            f"Candidate fact:\n"
            f"  ({target['subject']}) --[{target['predicate']}]--> ({target['object']})\n\n"
            f"Evidence from knowledge graph:\n{ctx_lines or '  (none)'}\n\n"
            f"Is the candidate fact supported by this evidence?"
        )
        try:
            response = self._llm.chat(prompt=prompt, system=self._system_prompt)
            return self._parse_response(response.content)
        except Exception as exc:
            logger.warning(f"[{self.agent_id}] LLM call failed: {exc}")
            return None

    def _parse_response(self, content: str) -> Optional[dict]:
        cleaned = re.sub(r"```(?:json)?\s*", "", content).replace("```", "").strip()
        try:
            data = json.loads(cleaned)
            verdict = data.get("verdict", "UNCERTAIN")
            if verdict not in ("SUPPORTED", "UNSUPPORTED", "UNCERTAIN"):
                verdict = "UNCERTAIN"
            confidence = float(data.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))
            return {
                "verdict":    verdict,
                "confidence": confidence,
                "reason":     str(data.get("reason", "")),
            }
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.warning(f"[{self.agent_id}] Failed to parse LLM output: {exc}\nRaw: {content[:200]}")
            return None
