# Ch2 deepening Wave A (2.1.1 knowledge graphs + 2.1.4 provenance) — awaiting gates

## Append to end of 2.1.1 (after "...a contaminated fact that gets used.")

**A1.**
How a knowledge graph is built shapes how contamination behaves in it. A knowledge graph
stores each fact as a triple of the form (subject, relation, object), a format that comes
from the Resource Description Framework used for linked data on the web. Subjects and
objects are entities, ideally drawn from a shared vocabulary so the same thing is always
named the same way, and the relation names the tie between them. Facts enter the graph in
one of three ways: entered by hand, imported from an existing structured source, or
extracted from text by a program. This thesis uses the third route, and it is the one that
lets errors in, because a model reading text can misread it.

**A2.**
Because extracted graphs contain mistakes, a body of work studies how to find and fix
them, under the name knowledge-graph refinement [28]. Refinement methods look for facts
that are internally inconsistent, that contradict the rest of the graph, or that are
unlikely given the graph's structure. They share an assumption: that an error leaves a
trace the rest of the graph can reveal. One of this thesis's findings is that a common
extraction error, replacing a correct value with a wrong one, leaves no such trace,
because it overwrites the very evidence a refinement check would rely on.

**A3.**
Sharing a memory between agents is also an old idea. Early artificial-intelligence systems
used a blackboard architecture, in which independent modules read from and wrote to a
common workspace and coordinated only through what they left there, rather than by
messaging each other directly [29]. A shared knowledge graph is a modern version of that
pattern. It brings the same benefit, that any agent can build on any other's work, and the
same risk, that a wrong entry misleads whoever reads it next. Much of this thesis is a
study of that risk in its modern form.

## Insert in 2.1.4 AFTER the confidence-cost paragraph (ends "...a live shared memory needs.") and BEFORE "Applied to a shared knowledge graph..."

**B1.**
Database research distinguishes several kinds of provenance, usually summarised as why,
how, and where. Why-provenance names the source records that justify a result;
how-provenance records the way they were combined; and where-provenance points to the
exact place a value was copied from [13]. The lineage this thesis uses is closest to why-
and how-provenance: it records which earlier facts a derived fact rests on and, through
the boolean formula, how they were combined. That is enough to trace a wrong fact forward
to its dependents, which is what the mitigation needs.

**B2.**
Storing facts with confidences turns a database into a probabilistic database, one that
represents not a single certain state of the world but many possible states, each with a
probability [30]. A query over such a database returns, in principle, an answer for every
possible state, weighted by how likely that state is. This is a powerful idea, and it is
also where the cost comes from: the number of possible states grows very quickly, so exact
answers are expensive, which is why practical systems approximate, as described above.

**B3.**
A later line of work showed that many of these provenance and confidence calculations are
instances of one algebraic pattern, in which combining facts corresponds to two operations
that behave like addition and multiplication [31]. This is the same pattern the mitigation
uses when it multiplies confidences for an AND and combines them for an OR. The value of
the pattern here is modest but real: it means the simple arithmetic the mitigation performs
rests on an established footing rather than being an arbitrary choice.
