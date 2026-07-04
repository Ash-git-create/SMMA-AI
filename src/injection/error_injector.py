"""
ErrorInjector — controlled injection of the three thesis error types into
KG triplets.

Error taxonomy (RQ2):
  entity_disambiguation — the object entity is swapped for a different entity
      that occurs with the SAME predicate elsewhere in the KG (a plausible
      confusion, not random noise).
  qualifier_loss — temporal/spatial/conditional qualifiers are stripped from
      the object (parentheticals, date ranges, trailing comma-qualifiers).
  relation_strengthening — a weak associative predicate is upgraded to a
      strong causal/definitive one via a fixed mapping.

Ground-truth bookkeeping (see provenance_schema.py):
  - `error_type` marks ground-truth contamination — set ONLY here.
  - `original_*` fields preserve the pre-corruption values for analysis.
  - `state` is NOT touched: detection (state=I) is the agents' job, and
    Detection AUROC compares their judgment against error_type.
  - `confidence` is NOT touched: an undetected error looks exactly like a
    trusted fact — that is the whole problem being studied.

Every injection run writes a JSON manifest (results/raw/) with before/after
values, the seed, and the config, so any run is fully reconstructable.
"""

from __future__ import annotations

import random
import re
from datetime import datetime, timezone
from typing import Optional

from loguru import logger

from src.graph.neo4j_client import Neo4jClient
from src.graph.provenance_schema import STATE_SUSCEPTIBLE

ERROR_TYPES = ("entity_disambiguation", "qualifier_loss", "relation_strengthening")

# Weak associative → strong causal/definitive predicate upgrades.
# Checked as substrings of the (lowercased) predicate; first match wins.
_STRENGTHEN_MAP = [
    ("associated with",   "caused"),
    ("related to",        "caused"),
    ("linked to",         "caused"),
    ("connected to",      "caused"),
    ("influenced",        "caused"),
    ("contributed to",    "was the sole cause of"),
    ("participated in",   "led"),
    ("participant in",    "leader of"),
    ("participating team", "winning team"),
    ("cast member",       "lead actor"),
    ("member of",         "leader of"),
    ("part of",           "creator of"),
    ("has part",          "is entirely composed of"),
    ("worked with",       "directed"),
    ("collaborated",      "directed"),
    ("known for",         "invented"),
    ("involved in",       "orchestrated"),
    ("affiliated with",   "controls"),
    ("shares border with", "governs"),
    ("nominated for",     "winner of"),
    ("diplomatic relation", "military alliance with"),
    ("twinned administrative body", "governed by"),
    ("played for",        "captained"),
    ("appeared in",       "starred in"),
    ("educated at",       "graduated top of class at"),
    ("supported",         "founded"),
    ("follows",           "replaced"),
    ("followed by",       "abolished by"),
]

_QUALIFIER_PATTERNS = [
    re.compile(r"\s*\([^)]*\)"),                       # parentheticals: "(1844–1846)"
    re.compile(r"\s*,\s[^,]+$"),                        # trailing comma-qualifier: ", California"
    re.compile(r"\s*(?:from|between|during|until|since)\s.+$", re.IGNORECASE),
    re.compile(r"\s*\b(?:1[0-9]{3}|20[0-9]{2})\s*[–\-]\s*(?:1[0-9]{3}|20[0-9]{2})\b"),  # year ranges
]

# Full dates → year only (temporal precision loss): "24 October 1968" → "1968"
_FULL_DATE = re.compile(
    r"^\s*\d{1,2}\s+(January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+(\d{4})\s*$", re.IGNORECASE,
)
_ISO_DATE = re.compile(r"^\s*(\d{4})-\d{2}-\d{2}\s*$")


class ErrorInjector:
    """Applies controlled corruptions to Susceptible KG triplets."""

    def __init__(
        self,
        neo4j_client: Optional[Neo4jClient] = None,
        random_seed: int = 42,
    ):
        self._external_client = neo4j_client
        self._rng = random.Random(random_seed)
        self.random_seed = random_seed

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def inject(
        self,
        error_type: str,
        count: int,
        dry_run: bool = False,
        pool: Optional[list[dict]] = None,
    ) -> list[dict]:
        """
        Inject *count* errors of *error_type* into random Susceptible,
        not-yet-corrupted triplets. Returns one record per applied injection:
            {triplet_id, error_type, field, before, after}

        pool: optional explicit candidate list (triplet dicts). Used for
        targeted seeding — e.g. Phase 2.4 seeds index cases inside the active
        retrieval subgraph instead of uniformly across the KG (uniform random
        injections at low prevalence never intersect the task neighborhoods).
        """
        if error_type not in ERROR_TYPES:
            raise ValueError(f"Unknown error type '{error_type}'. Use one of {ERROR_TYPES}")

        client = self._external_client or Neo4jClient()
        try:
            return self._inject(client, error_type, count, dry_run, pool)
        finally:
            if self._external_client is None:
                client.close()

    def inject_all_types(
        self,
        count_per_type: int,
        dry_run: bool = False,
        pool: Optional[list[dict]] = None,
    ) -> list[dict]:
        """Inject count_per_type errors of each of the three types."""
        records = []
        for et in ERROR_TYPES:
            records += self.inject(et, count_per_type, dry_run, pool)
        return records

    # ------------------------------------------------------------------
    # Transformations (pure — unit-testable without a DB)
    # ------------------------------------------------------------------

    @staticmethod
    def strip_qualifier(obj: str) -> Optional[str]:
        """Remove the first matching qualifier from the object string.
        Full dates are truncated to the year (temporal precision loss).
        Returns None if the object carries no recognizable qualifier."""
        m = _FULL_DATE.match(obj)
        if m:
            return m.group(2)
        m = _ISO_DATE.match(obj)
        if m:
            return m.group(1)
        for pattern in _QUALIFIER_PATTERNS:
            stripped = pattern.sub("", obj).strip()
            if stripped and stripped != obj.strip():
                return stripped
        return None

    @staticmethod
    def strengthen_predicate(predicate: str) -> Optional[str]:
        """Upgrade a weak associative predicate to a strong causal one.
        Returns None if the predicate has no weak form to strengthen."""
        pred_lower = predicate.lower()
        for weak, strong in _STRENGTHEN_MAP:
            if weak in pred_lower:
                # replace case-insensitively, preserving surrounding text
                return re.sub(re.escape(weak), strong, predicate, flags=re.IGNORECASE)
        return None

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _inject(
        self,
        client: Neo4jClient,
        error_type: str,
        count: int,
        dry_run: bool,
        pool: Optional[list[dict]] = None,
    ) -> list[dict]:
        # Oversample candidates: not every triplet admits every corruption
        # (no qualifier to strip, no weak predicate to strengthen).
        if pool is None:
            pool = client.search_triplets(
                state=STATE_SUSCEPTIBLE, limit=count * 10, randomize=True
            )
            if error_type == "qualifier_loss":
                # Qualifier-bearing triplets are a small share of the KG — a
                # uniform sample under-supplies them, so add date triplets directly.
                for pred in ("date of birth", "date of death"):
                    pool += client.search_triplets(
                        state=STATE_SUSCEPTIBLE, predicate=pred,
                        limit=count * 2, randomize=True,
                    )
        seen_ids = set()
        candidates = []
        for t in pool:
            if t["id"] not in seen_ids and not t.get("error_type"):
                seen_ids.add(t["id"])
                candidates.append(t)
        self._rng.shuffle(candidates)

        applied = []
        now = datetime.now(timezone.utc).isoformat()

        for t in candidates:
            if len(applied) >= count:
                break
            change = self._corrupt(t, error_type, candidates)
            if change is None:
                continue
            field, before, after = change
            if not dry_run:
                client.update_triplet_fields(
                    t["id"],
                    error_type=error_type,
                    injected_at=now,
                    **{field: after, f"original_{field}": before},
                )
            # Mark the in-memory dict too: callers reuse the same pool across
            # error types (targeted seeding), and the not-yet-corrupted check
            # reads these dicts — without this a triplet can be injected twice.
            t["error_type"] = error_type
            t[field] = after
            applied.append({
                "triplet_id": t["id"],
                "error_type": error_type,
                "field":      field,
                "before":     before,
                "after":      after,
                "subject":    t["subject"],
            })

        if len(applied) < count:
            logger.warning(
                f"[injector] {error_type}: only {len(applied)}/{count} injectable "
                f"among {len(candidates)} candidates — raise the candidate pool "
                f"or accept the shortfall (logged, not silent)."
            )
        logger.info(f"[injector] {error_type}: {len(applied)} injections"
                    + (" (dry-run, not written)" if dry_run else ""))
        return applied

    def _corrupt(self, t: dict, error_type: str, pool: list[dict]) -> Optional[tuple[str, str, str]]:
        """Compute (field, before, after) for one triplet, or None if this
        triplet does not admit this error type."""
        if error_type == "qualifier_loss":
            stripped = self.strip_qualifier(t["object"])
            return ("object", t["object"], stripped) if stripped else None

        if error_type == "relation_strengthening":
            strong = self.strengthen_predicate(t["predicate"])
            return ("predicate", t["predicate"], strong) if strong else None

        if error_type == "entity_disambiguation":
            # Swap object for another entity seen with the same predicate —
            # a plausible-but-wrong substitution.
            same_pred = [c["object"] for c in pool
                         if c["predicate"] == t["predicate"]
                         and c["object"] != t["object"]]
            wrong = self._rng.choice(same_pred) if same_pred else None
            if wrong is None:
                others = [c["object"] for c in pool if c["object"] != t["object"]]
                wrong = self._rng.choice(others) if others else None
            return ("object", t["object"], wrong) if wrong else None

        return None
