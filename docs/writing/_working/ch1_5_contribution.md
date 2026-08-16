# 1.5 Thesis Contribution (MINIMAL version — defers findings to abstract + ch5)

**P1 (lead-in).**
This thesis makes four contributions.

**P2 (contribution 1: framework).**
The first is a way to measure contamination as if it were a disease. The thesis applies
the SIR model to the facts held in a shared knowledge graph and reads off a reproduction
number for each error type and each system setting. Other recent work [5] models error
spread in multi-agent systems as a contagion over the agents and the messages they pass;
this thesis places the contagion on the facts in the shared memory instead. Chapter 2
sets out that difference.

**P3 (contribution 2: empirical study, no findings previewed).**
The second is an empirical study of how non-adversarial contamination spreads: which
conditions let it persist and spread, which error types are most harmful, and how the
design choices of RQ3 change its speed and reach. The findings are reported in Chapter 5.

**P4 (contribution 3: negative result, stated not detailed).**
The third is a negative result on mitigation. The project set out to show that a
provenance-aware memory, built from database lineage ideas, would contain contamination.
Under a realistic language-model validator it does not, and the thesis identifies the
reason. Chapter 5 gives the evidence and Chapter 6 discusses what it means.

**P5 (contribution 4: testbed).**
The fourth is the testbed itself: a pipeline that fills the graph, injects the errors,
measures the spread, and runs the mitigation, under a fixed experimental procedure and
with repeated runs under different random seeds. It is prepared for open release so that
others can reproduce and extend the work.
