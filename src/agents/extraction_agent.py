"""
ExtractionAgent — text → SPO triplets → Neo4j.

Uses Mistral Nemo (via llm_client) to extract Subject-Predicate-Object triplets
from a passage of text, then writes each triplet to Neo4j with full provenance
metadata (x-tuple: value + confidence + lineage).

Usage:
    from src.agents.extraction_agent import ExtractionAgent
    agent = ExtractionAgent(agent_id="extractor-01")
    triplets = agent.extract_and_store("Paris is the capital of France.")
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from src.agents.llm_client import ModelRole, get_client
from src.graph.neo4j_client import Neo4jClient
from src.graph.provenance_schema import (
    LineageFormula,
    TripletMetadata,
    STATE_SUSCEPTIBLE,
)

_SYSTEM_PROMPT = """\
You are a knowledge graph extraction engine. Your only job is to extract \
Subject-Predicate-Object (SPO) triplets from the provided text.

Rules:
1. Output ONLY a JSON array — no prose, no explanation.
2. Each element must be: {"subject": "...", "predicate": "...", "object": "..."}
3. Subject and object must be named entities or noun phrases.
4. Predicate must be a short, normalised relation label (snake_case preferred).
5. Do not invent facts not present in the text.
6. Extract exactly what the text ASSERTS, even if you believe the statement is
   false, unverified, or fictional. You are recording the text's claims, not
   judging their truth. "X was born in 1978" always yields
   {"subject": "X", "predicate": "born_in", "object": "1978"}.
7. Single-sentence texts still contain triplets — a short claim is not a
   reason to return an empty array.
8. Only return [] if the text truly contains no subject-predicate-object
   assertion at all.

Example — text: "Paris is the capital of France, located in Europe."
[
  {"subject": "Paris", "predicate": "is_capital_of", "object": "France"},
  {"subject": "Paris", "predicate": "located_in", "object": "Europe"}
]

Example — text: "The Moon is made of cheese." (false, but the text asserts it)
[
  {"subject": "The Moon", "predicate": "made_of", "object": "cheese"}
]
"""


class ExtractionAgent:
    """
    Extracts SPO triplets from text using Mistral Nemo and writes them to Neo4j.

    Parameters
    ----------
    agent_id:
        Identifier for this agent instance — stored in provenance metadata.
    confidence_default:
        Confidence score assigned to freshly extracted triplets before validation.
    source_context_ids:
        Optional list of KG triplet IDs that this extraction is based on.
        When provided, extracted triplets inherit a conjunction lineage formula.
    neo4j_client:
        Optional pre-built client. If None, a new one is created per call.
    """

    def __init__(
        self,
        agent_id: str = "extraction_agent",
        confidence_default: float = 0.85,
        neo4j_client: Optional[Neo4jClient] = None,
    ):
        self.agent_id = agent_id
        self.confidence_default = confidence_default
        self._external_client = neo4j_client
        self._llm = get_client(ModelRole.EXTRACTION)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_and_store(
        self,
        text: str,
        source_context_ids: Optional[list[str]] = None,
        source_label: str = "agent_extraction",
        context_facts: Optional[list[dict]] = None,
    ) -> list[dict]:
        """
        Extract triplets from *text* and write them to Neo4j.

        context_facts: KG triplets retrieved as context for this extraction.
        They are shown to the LLM alongside the passage — this is the channel
        through which contaminated KG facts influence new extractions (the
        susceptibility component of beta). Their ids become the lineage
        parents, and a DERIVED_FROM edge is written per parent so cascade
        deprecation can walk the graph.

        Returns the list of written triplet dicts (each includes the 'id' key).
        """
        if context_facts and not source_context_ids:
            source_context_ids = [f["id"] for f in context_facts if "id" in f]

        raw_triplets = self._call_llm(text, context_facts)
        if not raw_triplets:
            logger.debug(f"[{self.agent_id}] No triplets extracted from text.")
            return []

        records = self._build_records(raw_triplets, source_context_ids, source_label, text)

        client = self._external_client or Neo4jClient()
        try:
            n = client.bulk_load_triplets(records)
            # Materialize lineage as graph edges — the lineage formula string
            # alone is not walkable by cascade_deprecate.
            if source_context_ids:
                for r in records:
                    for src_id in source_context_ids:
                        client.add_lineage_edge(r["id"], src_id)
            logger.info(
                f"[{self.agent_id}] Stored {n} triplets"
                + (f" with {len(source_context_ids)} lineage parents each"
                   if source_context_ids else "")
            )
        finally:
            if self._external_client is None:
                client.close()

        return records

    def extract_only(self, text: str, context_facts: Optional[list[dict]] = None) -> list[dict]:
        """Extract triplets from text without writing to Neo4j."""
        return self._call_llm(text, context_facts)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_llm(self, text: str, context_facts: Optional[list[dict]] = None) -> list[dict]:
        """Send text to Mistral Nemo and parse the JSON array response."""
        context_block = ""
        if context_facts:
            fact_lines = "\n".join(
                f"  - ({f['subject']}) --[{f['predicate']}]--> ({f['object']})"
                for f in context_facts
            )
            context_block = (
                "Facts already in the knowledge graph, for context "
                "(they may be relevant to interpreting the text):\n"
                f"{fact_lines}\n\n"
            )
        prompt = f"{context_block}Extract all SPO triplets from the following text:\n\n{text}"
        try:
            response = self._llm.chat(prompt=prompt, system=_SYSTEM_PROMPT)
            return self._parse_response(response.content)
        except Exception as exc:
            logger.warning(f"[{self.agent_id}] LLM call failed: {exc}")
            return []

    def _parse_response(self, content: str) -> list[dict]:
        """Extract the JSON array from the LLM response, tolerating markdown fences."""
        # Strip ```json ... ``` fences if the model wraps output
        cleaned = re.sub(r"```(?:json)?\s*", "", content).replace("```", "").strip()
        try:
            data = json.loads(cleaned)
            if not isinstance(data, list):
                raise ValueError("Expected a JSON array.")
            valid = []
            for item in data:
                if all(k in item for k in ("subject", "predicate", "object")):
                    valid.append({
                        "subject":   str(item["subject"]).strip(),
                        "predicate": str(item["predicate"]).strip(),
                        "object":    str(item["object"]).strip(),
                    })
            return valid
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(f"[{self.agent_id}] Failed to parse LLM output: {exc}\nRaw: {content[:200]}")
            return []

    def _build_records(
        self,
        triplets: list[dict],
        source_context_ids: Optional[list[str]],
        source_label: str,
        source_text: str,
    ) -> list[dict]:
        """Attach provenance metadata to each extracted triplet."""
        now = datetime.now(timezone.utc).isoformat()
        records = []
        for t in triplets:
            tid = str(uuid.uuid4())
            lineage = (
                LineageFormula.conjunction(source_context_ids)
                if source_context_ids
                else LineageFormula.from_single(tid)
            )
            meta = TripletMetadata(
                source_id=tid,
                agent_id=self.agent_id,
                timestamp=now,
                confidence=self.confidence_default,
                lineage=lineage,
                state=STATE_SUSCEPTIBLE,
            )
            records.append({
                "id":          tid,
                "subject":     t["subject"],
                "predicate":   t["predicate"],
                "object":      t["object"],
                "source_text": source_text[:500],
                "source":      source_label,
                "meta":        meta,
            })
        return records
