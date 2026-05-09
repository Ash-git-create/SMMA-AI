"""
Neo4j client — connection management and CRUD helpers for the KG.

Graph model
-----------
(:Entity {id, name})
    -[:SUBJECT_OF]->
(:Triplet {id, subject, predicate, object, source_text, source,
           state, confidence, lineage, source_id, agent_id, timestamp,
           error_type})
    -[:HAS_OBJECT]->
(:Entity {id, name})

(:Triplet)-[:DERIVED_FROM]->(:Triplet)   # lineage edges added by agents
"""

from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv
from neo4j import GraphDatabase, Driver

from src.graph.provenance_schema import TripletMetadata

load_dotenv()

_BATCH_SIZE = 500


class Neo4jClient:
    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self._driver: Driver = GraphDatabase.driver(
            uri or os.environ["NEO4J_URI"],
            auth=(
                user or os.environ["NEO4J_USERNAME"],
                password or os.environ["NEO4J_PASSWORD"],
            ),
            notifications_min_severity="OFF",  # suppress schema-hint noise (e.g. missing rel types)
        )

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> Neo4jClient:
        return self

    def __exit__(self, *_) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Schema setup
    # ------------------------------------------------------------------

    def create_indexes(self) -> None:
        """Create indexes and constraints. Safe to call multiple times."""
        with self._driver.session() as s:
            s.run("CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE")
            s.run("CREATE CONSTRAINT triplet_id IF NOT EXISTS FOR (t:Triplet) REQUIRE t.id IS UNIQUE")
            s.run("CREATE INDEX triplet_state IF NOT EXISTS FOR (t:Triplet) ON (t.state)")
            s.run("CREATE INDEX triplet_confidence IF NOT EXISTS FOR (t:Triplet) ON (t.confidence)")
            s.run("CREATE INDEX entity_name IF NOT EXISTS FOR (e:Entity) ON (e.name)")

    def clear_all(self) -> None:
        """Delete every node and relationship. Use with care."""
        with self._driver.session() as s:
            s.run("MATCH (n) DETACH DELETE n")

    # ------------------------------------------------------------------
    # Bulk loading
    # ------------------------------------------------------------------

    def bulk_load_triplets(self, records: list[dict]) -> int:
        """
        Load a list of processed T-REx records into Neo4j.

        Each record must have: id, subject, predicate, object,
        source_text, source  + a TripletMetadata attached as 'meta'.

        Returns the number of triplets created.
        """
        total = 0
        for i in range(0, len(records), _BATCH_SIZE):
            batch = records[i : i + _BATCH_SIZE]
            rows = [
                {
                    "tid":         r["id"],
                    "subject":     r["subject"],
                    "predicate":   r["predicate"],
                    "object":      r["object"],
                    "source_text": r.get("source_text", ""),
                    "source":      r.get("source", ""),
                    **r["meta"].to_dict(),
                }
                for r in batch
            ]
            with self._driver.session() as s:
                result = s.run(
                    """
                    UNWIND $rows AS row
                    MERGE (subj:Entity {id: row.subject})
                        ON CREATE SET subj.name = row.subject
                    MERGE (obj:Entity  {id: row.object})
                        ON CREATE SET obj.name = row.object
                    CREATE (t:Triplet {
                        id:          row.tid,
                        subject:     row.subject,
                        predicate:   row.predicate,
                        object:      row.object,
                        source_text: row.source_text,
                        source:      row.source,
                        state:       row.state,
                        confidence:  row.confidence,
                        lineage:     row.lineage,
                        source_id:   row.source_id,
                        agent_id:    row.agent_id,
                        timestamp:   row.timestamp,
                        error_type:  row.error_type
                    })
                    CREATE (subj)-[:SUBJECT_OF]->(t)
                    CREATE (t)-[:HAS_OBJECT]->(obj)
                    RETURN count(t) AS n
                    """,
                    rows=rows,
                )
                total += result.single()["n"]
        return total

    # ------------------------------------------------------------------
    # CRUD helpers
    # ------------------------------------------------------------------

    def get_triplet(self, triplet_id: str) -> Optional[dict]:
        with self._driver.session() as s:
            rec = s.run(
                "MATCH (t:Triplet {id: $id}) RETURN t", id=triplet_id
            ).single()
            return dict(rec["t"]) if rec else None

    def update_state(self, triplet_id: str, state: str) -> None:
        with self._driver.session() as s:
            s.run(
                "MATCH (t:Triplet {id: $id}) SET t.state = $state",
                id=triplet_id, state=state,
            )

    def update_confidence(self, triplet_id: str, confidence: float) -> None:
        with self._driver.session() as s:
            s.run(
                "MATCH (t:Triplet {id: $id}) SET t.confidence = $confidence",
                id=triplet_id, confidence=confidence,
            )

    def add_lineage_edge(self, derived_id: str, source_id: str) -> None:
        with self._driver.session() as s:
            s.run(
                """
                MATCH (derived:Triplet {id: $derived_id})
                MATCH (src:Triplet    {id: $source_id})
                MERGE (derived)-[:DERIVED_FROM]->(src)
                """,
                derived_id=derived_id, source_id=source_id,
            )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def count_by_state(self) -> dict[str, int]:
        """Return {S: n, I: n, R: n} — the SIR node counts."""
        with self._driver.session() as s:
            result = s.run(
                "MATCH (t:Triplet) RETURN t.state AS state, count(t) AS n"
            )
            return {row["state"]: row["n"] for row in result}

    def get_triplets_above_threshold(self, threshold: float, limit: int = 20) -> list[dict]:
        """Retrieve triplets with confidence >= threshold (Trio retrieval filter)."""
        with self._driver.session() as s:
            result = s.run(
                "MATCH (t:Triplet) WHERE t.confidence >= $threshold RETURN t LIMIT $limit",
                threshold=threshold, limit=limit,
            )
            return [dict(rec["t"]) for rec in result]

    def get_downstream(self, triplet_id: str) -> list[dict]:
        """Return all triplets derived (directly or transitively) from triplet_id."""
        with self._driver.session() as s:
            result = s.run(
                """
                MATCH (src:Triplet {id: $id})<-[:DERIVED_FROM*1..]-(derived:Triplet)
                RETURN derived
                """,
                id=triplet_id,
            )
            return [dict(rec["derived"]) for rec in result]

    def search_triplets(
        self,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict]:
        filters = []
        params: dict = {"limit": limit}
        if subject:
            filters.append("t.subject = $subject")
            params["subject"] = subject
        if predicate:
            filters.append("t.predicate = $predicate")
            params["predicate"] = predicate
        if state:
            filters.append("t.state = $state")
            params["state"] = state
        where = ("WHERE " + " AND ".join(filters)) if filters else ""
        with self._driver.session() as s:
            result = s.run(
                f"MATCH (t:Triplet) {where} RETURN t LIMIT $limit", **params
            )
            return [dict(rec["t"]) for rec in result]
