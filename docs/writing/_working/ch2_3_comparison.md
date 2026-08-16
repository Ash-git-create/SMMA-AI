# 2.3 Related Work Comparison (revised after gates — awaiting approval)

## 2.3.1 Non-adversarial versus adversarial contamination

**P1.**
The adversarial work in Section 2.2 and this thesis study the same object, a corrupted
shared memory, but from opposite ends. Attacks such as PoisonedRAG [16] start from an
attacker who chooses the false content and places it to cause a chosen effect. This
thesis starts from no attacker at all. The false content is whatever a well-behaved model
happens to get wrong, and where it lands is decided by the ordinary work of extraction,
not by design. The two settings need different defences: an adversarial defence looks for
a malicious source, while the non-adversarial case has nothing malicious to find. The
thesis therefore measures how a chance error spreads, not how an attacker's payload is
delivered.

## 2.3.2 Contagion on facts versus contagion on agents

**P1.**
The error-spread models in Section 2.2 and this thesis both treat spreading error as a
contagion, but they disagree on what carries it. Niu et al. [5], Jamshidi et al. [17],
and Liu [18] follow the error as it moves between agents through the messages they
exchange. This thesis follows it as it moves between facts in a shared knowledge graph.
The difference is not cosmetic. A message-passing chain and a shared graph have different
shapes: a chain passes each output once to the next agent, while a graph lets any agent
retrieve any fact at any later step. The unit of contagion here is a stored fact, the
basic unit a graph-based memory is built from and retrieved by. The reproduction number
is measured over those facts rather than over the agents.

**P2.**
This difference in structure shows up in the results. Jamshidi et al. [17] report that
errors shrink as they pass down a message chain, because each error is diluted by fresh
input at every step. In a shared knowledge graph the picture is different: a contaminated
fact can be retrieved again and again by many agents, so it is reinforced rather than
diluted, and the spread does not die out on its own (Chapter 5). The two results describe
two different architectures, and this thesis's setting is the graph case, not the chain.

## 2.3.3 Testing provenance mitigation rather than assuming it

**P1.**
The containment work in Section 2.2 is the closest to this thesis, and also where it
parts company most sharply. Xie et al. [6] and Margalit et al. [19] build or propose
provenance-like machinery, lineage tracking and governed sharing, and report or assume
that it contains the spread; Xie et al. report success in at least 89% of runs. This
thesis builds a comparable provenance-aware mitigation and tests it under a language-model
validator that makes the same kind of misses a real validator would. Under those
conditions the mitigation does not contain the spread. Chapter 5 gives the evidence and
Chapter 6 works through why the results differ. The short version is that even a perfect
validator, one that never misses an error, only brings the spread down to its break-even
point rather than containing it, and the validator a real system actually has falls well
short of even that.

**P2.**
One containment result points the same way as this thesis rather than against it. Itkin
[20] finds that the timing of correction decides whether shared belief settles or breaks
down. This thesis finds an analogous effect: how often the shared memory is checked has a
threshold of its own, where any regular in-run checking holds the spread down but
deferring all of it to the end lets the outbreak run (Chapter 5). The two thresholds are
not the same quantity. Still, that two independent studies both find the timing of
correction to have a threshold is a point in favour of the finding, and the thesis treats
Itkin's result as convergent evidence.
