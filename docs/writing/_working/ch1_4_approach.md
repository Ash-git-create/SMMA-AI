# 1.4 Approach (revised after gates — awaiting approval)

**P1.** (passed clean)
The thesis studies contamination in a controlled testbed rather than in a live product.
Working in a testbed means the error can be placed on purpose, at a known spot, and then
watched as it moves. A live system would not allow that: real errors appear at random
and are hard to trace cleanly. The cost is that a testbed is a simplified stand-in for a
real system, a point Chapter 6 returns to.

**P2.** (glossed Neo4j and T-REx; fixed FEVER; split the long sentence)
The testbed has three parts. The first is a knowledge graph stored in Neo4j, a database
built to hold networks of linked facts. This graph is the shared memory, and it starts
out filled with correct facts from the T-REx dataset, a large set of facts drawn from
Wikipedia, which acts as the clean starting population. The second part is a small set
of agents, built on open language models, that read text from two datasets, the
question-answering set HotpotQA and the claim-checking set FEVER, pull facts out of it,
and write those facts into the graph. The third part is a set of agents that read from
the graph to answer questions. Chapter 3 gives the full design and Chapter 4 the
implementation.

**P3.** (added the S/I/R mapping; replaced "photographed" with "snapshot recorded")
To create contamination on demand, the thesis injects the three error types from RQ2
into chosen facts, one type at a time, so their effects can be told apart. As the agents
work, a snapshot of the graph is recorded at each step, and every fact is marked as
clean, contaminated, or caught, matching the Susceptible, Infected, and Recovered states
of the SIR model. The SIR model is borrowed from how epidemiologists track a disease
through a population. It turns the step-by-step counts into a single number, the basic
reproduction number R0, which says whether one contaminated fact tends to produce more
than one new contaminated fact (spread) or fewer than one (fade).

**P4.** (glossed exact-match and veracity; split into shorter sentences)
Finally, the thesis switches on the provenance-aware mitigation from RQ4 and runs the
same experiments again, so the mitigated and unmitigated systems can be compared
directly. Two kinds of measurement are kept apart throughout. The first is how well the
system answers questions: exact-match, meaning the answer is identical to the correct
one, on HotpotQA, and veracity, meaning a claim is labelled correctly as true, false, or
unverifiable, on FEVER. The second is how contaminated the system is: the reproduction
number, the share of answer sentences that trace back to a trustworthy fact, and how
well hallucinated facts can be detected. Keeping these apart matters because a system can
still answer some questions correctly while its memory quietly fills with errors, and
Chapter 5 shows this is exactly what happens.
