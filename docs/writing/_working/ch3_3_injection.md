# 3.3 Error taxonomy and controlled injection (working draft — awaiting gates)

**P1.**
Three types of non-adversarial error are used, chosen to cover the common ways an
extraction step goes wrong. An entity disambiguation error replaces the subject or object
with a wrong but related entity, for instance confusing two things that share a name. A
qualifier loss drops a modifier that limits when or where a fact holds, such as a date or
a place, which quietly widens the claim. A relation strengthening upgrades a weak link
into a strong or causal one, turning "is associated with" into "causes". Table 3.3 gives
an illustrative example of each.

[TBL]Table 3.3: The three error types, with an illustrative example of each.

| Error type | What changes | Illustrative example (before, then after) |
|---|---|---|
| Entity disambiguation | a wrong but related entity replaces the subject or object | (Georgia, capital is, Tbilisi), then (Georgia, capital is, Atlanta) |
| Qualifier loss | a time, place, or condition is dropped | (Obama, president of, USA in 2009-2017), then (Obama, president of, USA) |
| Relation strengthening | a weak link becomes a strong or causal one | (exercise, associated with, longer life), then (exercise, causes, longer life) |

**P2.**
The ErrorInjector makes these changes to triplets already in the graph, corrupting fifteen
of them per error type in each run by default. These corrupted triplets are the index
cases, the starting points of the outbreak. Not every triplet can take every corruption:
relation strengthening, for example, needs a triplet whose predicate is genuinely weak to
begin with. The injector therefore filters for triplets that admit the change. When the
index cases are drawn from the part of the graph the task will actually query (the default,
explained next), relation strengthening usually finds only nine or ten admissible triplets
out of fifteen, while drawing from the whole graph always yields fifteen. Relation-
strengthening results are therefore reported with the number of index cases actually
placed.

**P3.**
Where the index cases are placed is itself a variable the thesis controls. By default they
are placed inside the active retrieval subgraph: the region of the graph that the task
workload actually reads, built from the entities the run will touch. A control condition
instead places the same number of index cases at random across the whole Susceptible
graph. The contrast between these two conditions is what isolates retrieval reachability as
a necessary condition for spread, the first research question: an error can sit in the
shared memory and still go nowhere if no agent ever retrieves it. Section 5.3 reports that
contrast.
