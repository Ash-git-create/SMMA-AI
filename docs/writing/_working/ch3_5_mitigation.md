# 3.5 Trio-inspired mitigation framework (working draft — awaiting gates)

**P1.**
The mitigation under test adapts three mechanisms from the Trio model of Section 2.1.4,
each aimed at one part of the contagion. Section 3.4 tied spread to two rates: beta, how
readily contaminated facts are retrieved and reused, and gamma, how well validation catches
them. The first two mechanisms push on these two rates, and the third supports them.

**P2.**
The first mechanism is a confidence floor on retrieval. Every fact carries a confidence
score, and agents are only allowed to retrieve facts whose confidence is above a threshold,
set to 0.5. The aim is to keep low-confidence, possibly contaminated facts out of the
working context in the first place, which acts on the beta channel by narrowing what can be
retrieved.

**P3.**
The second mechanism is validation with quarantine. On each step the ValidationAgent
samples a set of facts that agents read or wrote in that cycle, twenty-five by default, and
judges each one. A fact the judge scores below a quarantine threshold, set to 0.4, is
quarantined: it is moved out of retrieval and marked Recovered. Quarantine also triggers
cascade deprecation, the mechanism from Section 3.2: the system walks the lineage forward
from the quarantined fact and deprecates everything derived from it. This mechanism acts on
the gamma channel, since it is the system's way of catching and removing infected facts.

**P4.**
The third mechanism is confidence propagation at write time. When a fact is derived from
retrieved ones, its confidence is not reset but computed from the confidence of its parents,
using the arithmetization of the lineage formula described in Section 2.1.4. The effect is
that uncertainty compounds along a chain of derivations rather than being forgotten at each
step, so a fact built on shaky ground inherits that shakiness.

**P5.**
These three mechanisms are treated as separate levers, not a single package. Alongside the
full combination, the experiments include configurations that switch on only the confidence
floor, or only the validation channel, so that each can be studied on its own (Section 3.6).
Nothing here assumes the combination helps. Whether a provenance-aware memory actually
contains contamination is the fourth research question, and it is left to the results to
answer.
