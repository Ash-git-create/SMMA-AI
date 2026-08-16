# 1.3 Research Questions (revised after gates — awaiting approval)

**P1 (lead-in).**
The problem breaks into four research questions. They build on each other. The first
asks whether contamination happens at all and under what conditions. The next two ask
what makes it worse. The last asks whether it can be stopped without spoiling the
system's answers.

**RQ block.**
RQ1. Under what conditions do non-adversarial errors (no attacker involved) persist and
spread through a shared-memory multi-agent system, instead of dying out? This asks
whether a single injected error stays where it is put, spreads to other parts of the
memory, or fades, and what has to be true of the system for each outcome.

RQ2. Which type of extraction error damages later reasoning the most: an entity
disambiguation error (a fact attached to the wrong name), qualifier loss (a dropped
condition such as a date), or relation strengthening (a weak link restated as a strong
one)? This ranks the three error types by how far they spread and how much they hurt
answers.

RQ3. How do a system's design choices change how fast and how far contamination
travels? The choices studied are how densely the knowledge graph is connected, how
often agents write to the shared memory, and how often that memory is checked for
errors.

RQ4. Can provenance-aware retrieval reduce contamination without hurting answer
quality? Provenance means a record of where each fact came from. A provenance-aware
system uses that record in two ways: it holds back facts whose confidence is too low so
agents do not retrieve them, and, once a fact is found to be wrong, it lowers the trust
in every later fact built on that one (its descendants). This is the mitigation the
thesis tests, adapted from database provenance research; Chapter 3 describes how it is
built. The question also asks where this mitigation stops working.

**P2 (closing / roadmap).**
The first three questions describe the problem: when contamination spreads, which
errors drive it, and which design choices control it. The fourth asks what to do about
it. Chapter 5 answers all four against the experiments, and Chapter 6 discusses what the
answers mean for anyone building these systems.
