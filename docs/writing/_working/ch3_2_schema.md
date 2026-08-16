# 3.2 Knowledge graph and provenance schema (working draft — awaiting gates)

**P1.**
The shared memory is a Neo4j graph. Neo4j is a database that stores data as nodes joined
by labelled links, which suits a knowledge graph directly. Each fact is a triplet: a
subject, a predicate, and an object, such as (Marie Curie, won, Nobel Prize in Physics).
Every triplet is stored with a set of extra fields that record where it came from and how
much it is trusted. Table 3.2 lists these fields.

[TBL]Table 3.2: The provenance fields stored with every triplet.

| Field | What it records |
|---|---|
| source_id | which document or earlier triplet the fact was drawn from |
| agent_id | which agent wrote it |
| timestamp | when it was written |
| confidence_score | how much the system trusts it, from 0 to 1 |
| lineage | the earlier facts this one was derived from |
| error_type | ground-truth contamination label, kept for measurement and hidden from agents |

**P2.**
This layout follows the Trio model from Section 2.1.4. Each fact is stored with a value, a
confidence score, and a lineage formula. The lineage formula is written down at the moment
a derived fact is created: it records which retrieved facts the new one was built from, as
a boolean expression over their identifiers. Lineage does two jobs in this thesis. First,
it makes cascade deprecation possible: when a fact is found to be wrong, the system can
follow the lineage forward and deprecate everything built on it (Section 3.5). Second, it
gives the experiment a ground-truth record of how each error spread, because every
propagated error can be traced back to the injected fact it came from. In every run this
trace-back succeeded for all propagated errors.

**P3.**
One field needs care. The error_type field records the ground-truth contamination status
of a fact: whether it is clean, an injected error, or an error propagated from one. This
is bookkeeping for measurement only. It is never shown to the agents and never returned by
retrieval, so the agents cannot use it to tell clean facts from contaminated ones. Without
it the epidemiological measurement would have no ground truth to compare against; if it
were exposed, the experiment would be measuring a system that can cheat. Keeping it hidden
from agents but available to the analysis is what lets the spread be measured cleanly.

**P4.**
Before each run the graph is loaded with about fifty thousand correct triplets from the
T-REx dataset, a large set of facts drawn from Wikipedia and aligned with Wikidata. These
are the Susceptible population of the SIR model: accurate, but not yet checked by the
system, and stored in exactly the same form as anything an agent writes. Because a pristine
T-REx fact and an agent-written fact look identical in the graph, an agent has no built-in
way to tell a trustworthy starting fact from a freshly written, possibly contaminated one.
That is the condition the thesis studies.
