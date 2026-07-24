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
from typing import Iterable, Optional

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

    _UPDATABLE_FIELDS = {
        "subject", "predicate", "object", "confidence", "state",
        "error_type", "original_subject", "original_predicate",
        "original_object", "injected_at",
    }

    def update_triplet_fields(self, triplet_id: str, **fields) -> None:
        """Update a fixed set of allowed fields on a triplet (used by the
        ErrorInjector to apply controlled corruptions with an original-value
        audit trail)."""
        bad = set(fields) - self._UPDATABLE_FIELDS
        if bad:
            raise ValueError(f"Fields not updatable: {bad}")
        sets = ", ".join(f"t.{k} = ${k}" for k in fields)
        with self._driver.session() as s:
            s.run(
                f"MATCH (t:Triplet {{id: $id}}) SET {sets}",
                id=triplet_id, **fields,
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

    def count_by_error_type(self) -> dict[str, int]:
        """Ground-truth contamination counts: {error_type: n} over triplets
        with error_type set (seeded injections + propagated infections)."""
        with self._driver.session() as s:
            result = s.run(
                "MATCH (t:Triplet) WHERE t.error_type IS NOT NULL "
                "RETURN t.error_type AS et, count(t) AS n"
            )
            return {row["et"]: row["n"] for row in result}

    def detection_confusion(self) -> dict[str, int]:
        """Cross-tab of detected state (agents' judgment) x ground-truth
        contamination (error_type presence): {'S_clean': n, 'R_contam': n, ...}.
        R_contam = true quarantines; R_clean = mitigation collateral damage."""
        with self._driver.session() as s:
            result = s.run(
                "MATCH (t:Triplet) "
                "RETURN t.state AS state, t.error_type IS NOT NULL AS contam, "
                "count(t) AS n"
            )
            return {
                f"{row['state']}_{'contam' if row['contam'] else 'clean'}": row["n"]
                for row in result
            }

    def get_contamination_confidences(
        self, clean_sample: int = 500
    ) -> tuple[list[float], list[float]]:
        """(contaminated_confidences, clean_confidences) for detection AUROC:
        all ground-truth-contaminated nodes vs a random clean sample."""
        with self._driver.session() as s:
            contam = [
                row["c"] for row in s.run(
                    "MATCH (t:Triplet) WHERE t.error_type IS NOT NULL "
                    "RETURN t.confidence AS c"
                )
            ]
            clean = [
                row["c"] for row in s.run(
                    "MATCH (t:Triplet) WHERE t.error_type IS NULL "
                    "RETURN t.confidence AS c ORDER BY rand() LIMIT $n",
                    n=clean_sample,
                )
            ]
        return contam, clean

    def get_triplets_above_threshold(self, threshold: float, limit: int = 20) -> list[dict]:
        """Retrieve triplets with confidence >= threshold (Trio retrieval filter)."""
        with self._driver.session() as s:
            result = s.run(
                "MATCH (t:Triplet) WHERE t.confidence >= $threshold "
                "RETURN t ORDER BY t.confidence DESC, t.id LIMIT $limit",
                threshold=threshold, limit=limit,
            )
            return [dict(rec["t"]) for rec in result]

    def get_related_triplets(
        self,
        subject: str,
        obj: str,
        exclude_id: str,
        min_confidence: float = 0.0,
        limit: int = 20,
    ) -> list[dict]:
        """
        Retrieve triplets that share an entity with (subject, obj), highest
        confidence first. This is the evidence-retrieval used for validation:
        related facts only — never arbitrary rows.

        Tie-break on t.id: Neo4j otherwise returns confidence-ties in
        arbitrary order, which varies across DB reloads — retrieval (and
        therefore every downstream LLM prompt) must be byte-stable for
        run-to-run comparisons to be attributable to treatment, not noise.
        """
        with self._driver.session() as s:
            result = s.run(
                """
                MATCH (t:Triplet)
                WHERE t.id <> $exclude_id
                  AND t.confidence >= $min_confidence
                  AND (t.subject IN [$subject, $obj] OR t.object IN [$subject, $obj])
                RETURN t
                ORDER BY t.confidence DESC, t.id
                LIMIT $limit
                """,
                subject=subject, obj=obj, exclude_id=exclude_id,
                min_confidence=min_confidence, limit=limit,
            )
            return [dict(rec["t"]) for rec in result]

    def get_adjacent_triplets(
        self,
        frontier_ids: list[str],
        exclude_ids: Iterable[str],
        state: Optional[str] = None,
        limit: int = 5000,
    ) -> list[dict]:
        """
        One bipartite-graph hop outward from `frontier_ids`: triplets that
        share an Entity node with any triplet in the frontier — as subject
        or object, in either triplet, via SUBJECT_OF/HAS_OBJECT — excluding
        `exclude_ids` (already-visited triplets) and optionally filtered to
        a single `state`.

        Set-wise expansion: one query per frontier batch (batched at
        _BATCH_SIZE, matching bulk_load_triplets), each capped at `limit`.
        Used by k-hop seed placement (RQ1/RQ3 bridge, run_contamination.py)
        to walk outward from the active retrieval subgraph without a
        per-node loop, which would be combinatorial over the ~50K-triplet
        KG — dense hub entities can otherwise pull in a large fraction of
        the graph in a single hop, hence the LIMIT.
        """
        exclude = set(exclude_ids)
        found: dict[str, dict] = {}
        with self._driver.session() as s:
            for i in range(0, len(frontier_ids), _BATCH_SIZE):
                if len(found) >= limit:
                    break
                batch = frontier_ids[i : i + _BATCH_SIZE]
                query = (
                    "UNWIND $batch AS fid\n"
                    "MATCH (t:Triplet {id: fid})-[:SUBJECT_OF|HAS_OBJECT]-(e:Entity)"
                    "-[:SUBJECT_OF|HAS_OBJECT]-(nt:Triplet)\n"
                    "WHERE NOT nt.id IN $exclude\n"
                )
                params: dict = {"batch": batch, "exclude": list(exclude), "limit": limit}
                if state:
                    query += "  AND nt.state = $state\n"
                    params["state"] = state
                query += "RETURN DISTINCT nt LIMIT $limit"
                result = s.run(query, **params)
                for rec in result:
                    d = dict(rec["nt"])
                    found.setdefault(d["id"], d)
        return list(found.values())[:limit]

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
        randomize: bool = False,
    ) -> list[dict]:
        """
        Filtered triplet lookup. Set randomize=True for a uniform random
        sample — audit passes and infection seeding MUST use this, otherwise
        Neo4j returns the same rows every call and biases the SIR estimates.
        """
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
        order = "ORDER BY rand()" if randomize else ""
        with self._driver.session() as s:
            result = s.run(
                f"MATCH (t:Triplet) {where} RETURN t {order} LIMIT $limit", **params
            )
            return [dict(rec["t"]) for rec in result]
