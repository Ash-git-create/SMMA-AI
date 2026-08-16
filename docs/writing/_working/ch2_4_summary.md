# 2.4 Summary (working draft — awaiting gates)

**P1.**
This chapter laid out the four ideas the thesis builds on and reviewed the recent work
closest to it. The background introduced the four: multi-agent systems that share a
knowledge-graph memory, the hallucinations that put wrong facts into that memory, the SIR
model that measures how a contagion spreads, and the database idea of provenance that the
mitigation is built from. The related work then showed that the problem is current.
Several 2026 papers model how errors spread between agents; others try to contain that
spread with provenance-like machinery.

**P2.**
Two gaps run through that work. The spread is modelled over agents and the messages
between them, not over the facts in a shared knowledge graph. That graph is the level at
which a memory system is actually built and queried. And the containment work reports that
provenance-like machinery works, but shows this under favourable conditions rather than
under the ordinary, imperfect validator a real system runs. This thesis is built to close
both gaps: it measures contagion at the level of facts in a shared graph, and it tests a
provenance-aware mitigation under a realistic validator instead of assuming it succeeds.

**P3.**
Chapter 3 turns this position into a method. It describes the agents and the shared
graph, the three error types and how they are injected, the SIR model and how the
reproduction number is computed, and the provenance-aware mitigation the thesis puts to
the test.
