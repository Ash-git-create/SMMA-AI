# Ch2 deepening wave 2 (2.1.3 network epi + 2.1.4 confidence computation) — awaiting gates

## Insert in 2.1.3 AFTER the difference-equations/R0 paragraph, BEFORE the KG-mapping paragraph

**C1.**
The basic model assumes everyone mixes with everyone equally, which real populations do
not. A more realistic version places the population on a network, where each member makes
contact only along its links [25]. On a network the spread depends on the shape of the
connections as well as on beta and gamma. Members with many links, the hubs, are more
likely both to catch an infection and to pass it on, so a small number of highly connected
members can drive most of the spread. These are the superspreaders, and on a strongly
hub-dominated network the usual threshold at R0 = 1 can break down, with infections
persisting at transmission rates that would die out in a well-mixed population [26].

**C2.**
A knowledge graph is exactly such a network. Its facts are not all equally connected: a few
popular entities are linked to very many facts, while most are linked to few. A
contaminated fact attached to a highly connected entity is retrieved far more often than one
on the fringe, and can act as a superspreader. Chapter 5 returns to this when it examines
why certain error placements spread much further than others.

## Insert in 2.1.4 AFTER the arithmetization paragraph, BEFORE the applied-to-KG paragraph

**D1.**
Computing these confidences exactly is harder than it looks. When many facts share
ancestors, their lineage formulas overlap, and working out the exact probability that a
derived fact is correct grows expensive as the formulas get larger, a difficulty studied in
the wider field of probabilistic databases [27]. Trio's answer, and the one this thesis
borrows, is to approximate: rather than solve the full formula, it combines the parent
confidences with the simple arithmetic rules above. The approximation gives up some
exactness in return for being able to keep confidences up to date as the graph grows, which
is what a live shared memory needs.
