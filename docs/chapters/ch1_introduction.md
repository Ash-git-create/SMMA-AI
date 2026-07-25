# Chapter 1 — Introduction

> **Draft status (2026-07-25):** first full draft. Cross-references to later
> chapters use chapter/section numbers as currently drafted; headline figures
> quoted here are previews of results established with full statistics in
> Chapter 5 and are traceable to the archived result files named there.

## 1.1 Background: shared memory in multi-agent LLM systems

Large Language Models (LLMs) have moved beyond single-turn question answering
into *multi-agent systems* (MAS): collections of LLM-driven agents that
divide a complex task among themselves and coordinate to solve it. A research
agent might delegate literature retrieval to one sub-agent, extraction to
another, and synthesis to a third; a clinical or financial assistant might
chain specialised agents across a long workflow. The pattern is attractive
because it decomposes problems that exceed a single model's context or
reliability, and because specialised agents with narrow roles are easier to
prompt, test, and reason about than one monolithic agent.

A defining feature of the more capable of these systems is a **shared,
persistent memory layer**. Rather than passing their entire reasoning history
to one another as messages, agents write intermediate results into a common
store and read from it as needed. That store is frequently structured as a
**Knowledge Graph (KG)** — a database of facts held as subject–predicate–object
(SPO) triplets, such as *(Paris, capitalOf, France)* — because a graph makes
relationships explicit, supports multi-hop retrieval, and lets many agents
accumulate and reuse structured knowledge across sessions. The shared KG
becomes the system's collective memory: what one agent learns, every other
agent can later retrieve.

This architecture delivers real benefits — efficiency, traceability, and a
form of distributed cognition in which agents build on each other's work. But
it also couples the agents together through the memory in a way that direct
message-passing does not. Every agent's output becomes a potential input to
every other agent, mediated by the shared store. The central concern of this
thesis is what happens to that coupled system when the facts written into the
shared memory are wrong — not because an attacker made them wrong, but simply
because an LLM, in the ordinary course of its work, made a mistake.

## 1.2 The contamination problem: why errors compound

LLMs make characteristic, non-adversarial errors when they extract or
synthesise facts. They *hallucinate* — assert things that are not supported by
their input. They attribute a property to the wrong entity, drop a temporal or
conditional qualifier that changes a fact's meaning, or upgrade a hedged
association into a confident causal claim. In a single-agent, single-turn
setting such an error is a local, one-off failure. In a shared-memory MAS it
is not local at all.

When an agent writes an erroneous triplet into the shared KG, that error
becomes retrievable context for every downstream agent. A later agent that
retrieves the corrupted fact has no way, in general, to know it is corrupted:
it arrives through the same trusted channel as every genuine fact. The
downstream agent reasons over it, produces new conclusions that depend on it,
and writes *those* back into the memory. The error has now reproduced. Other
agents retrieve the derived facts, build on them in turn, and the corruption
propagates outward through the shared store. This is the phenomenon this
thesis calls **cascading knowledge contamination**: a self-sustaining spread
of error through a shared memory, requiring no attacker, driven entirely by
the ordinary mechanics of retrieval and reuse.

The reason such cascades matter is that error compounds *multiplicatively*
along a pipeline, not additively. If each step in a sequential workflow is
95% reliable, a chain of ten interdependent steps succeeds with probability
0.95¹⁰ ≈ 0.59 — a system built from highly reliable parts degrades to
near-coin-flip reliability over a modest number of steps. This arithmetic is
illustrative rather than a claim this thesis measures directly (the
uninjected error rate of the system studied here is far below 5%; see Chapter
5 and the limitations discussion in Chapter 6). Its purpose is to make the
stakes concrete: in a coupled system, small per-step error rates do not stay
small, and a memory that faithfully preserves and re-serves whatever it is
given will preserve and re-serve mistakes with the same fidelity as facts.

Framed this way, the problem is naturally *epidemiological*. A corrupted fact
that spreads through a population of agents and knowledge nodes behaves like a
contagion: some nodes are susceptible, some are infected, some may be caught
and removed. This thesis takes that analogy seriously and makes it
quantitative, borrowing the compartmental models epidemiology uses to
describe how fast and how far a contagion spreads.

## 1.3 The gap: non-adversarial, systemic contamination

Security research on LLMs has concentrated overwhelmingly on the
*adversarial* case: prompt injection, data poisoning, jailbreaks, and — most
directly related — deliberate memory-poisoning attacks in which an adversary
crafts inputs to corrupt an agent's stored knowledge. That literature is
valuable, but it assumes an attacker with intent and control. It does not
address the failure mode that arises with no attacker at all: the ordinary,
expected extraction errors of well-behaved models, spreading through a shared
memory purely because the architecture reuses them.

Three gaps follow. First, the *non-adversarial* origin of the corruption is
under-studied — most work presumes a hostile input, not an honest mistake.
Second, the *systemic* level of analysis is missing — existing auditing
methods examine individual messages or outputs in isolation, whereas
contamination is a property of the coupled system's dynamics, invisible to any
single-message check. Third, there is no *quantitative model* of how fast or
how far such contamination travels: the field lacks the equivalent of a
reproduction number that would let a designer predict whether a given
architecture will contain an error or amplify it. This thesis addresses all
three by building a controlled testbed in which non-adversarial errors are
injected into a shared KG, their spread is tracked at the level of the whole
system, and their contagion is quantified with an epidemiological model.

## 1.4 Research questions

The thesis is organised around four research questions.

**RQ1 — Persistence and spread.** Under what network and operational
conditions do non-adversarial extraction errors persist and spread within a
shared-memory MAS, rather than decaying harmlessly?

**RQ2 — Error-type harm.** Which taxonomic error types — entity
disambiguation failures, qualifier loss, or relation strengthening — are most
harmful to downstream reasoning, and why?

**RQ3 — Architectural levers.** How do systemic design choices — graph
density, memory write frequency, and validation interval — affect the velocity
and reach of contamination?

**RQ4 — Provenance-aware mitigation.** Can a Trio-inspired, provenance-aware
retrieval and validation strategy reduce contamination while preserving answer
quality, and what are its limits?

## 1.5 Contributions

This work makes the following contributions. Several of them invert the
expectation the project began with, and that inversion is deliberate and
central rather than incidental.

1. **A formal epidemiological framework for knowledge contamination.** The
   thesis adapts the discrete-time Susceptible–Infected–Recovered (SIR) model
   to the nodes of a shared KG, deriving a Basic Reproduction Number (R₀) per
   error type and per configuration as its headline metric. This gives
   designers a single, interpretable quantity — is R₀ above or below one? — for
   predicting whether an architecture contains or amplifies error. To our
   knowledge this is the first application of compartmental epidemiology to
   non-adversarial contamination in a shared-memory MAS.

2. **An empirical characterisation of how contamination spreads (RQ1–RQ3).**
   The experiments establish that spread is gated by *retrieval reachability*:
   an error persists in memory but does not spread unless it enters the region
   of the graph that agents actually retrieve — reachability behaves as a hard
   threshold, not a smooth gradient. They further show that *reach and harm
   decouple* at realistic contamination densities (the memory can be
   substantially corrupted while task metrics remain flat), that entity
   disambiguation failures are the most contagious error type and relation
   strengthening the least, and that the architectural levers of RQ3 act
   through well-defined dose–responses — including a threshold in validation
   *cadence*, where any in-run auditing contains the outbreak but deferring all
   validation to the end lets it run unchecked.

3. **A negative result, with mechanism, on provenance-aware mitigation
   (RQ4).** The project set out to show that database-provenance techniques —
   lineage tracking, confidence propagation, and cascade deprecation, adapted
   from the Stanford Trio system — would contain contamination. Under a
   realistic LLM validator they largely do not: the full mitigation produces no
   reliable reduction in spread, single-digit quarantine precision, and a
   *degradation* in error detectability through a confidence-laundering effect.
   The thesis identifies the mechanism — *structural blindness*: replacement
   errors erase their own contradicting evidence, so an evidence-gated judge has
   nothing to catch — and locates the true causal lever, which is validator
   *recall* rather than precision, cadence, or the cascade machinery. It
   further shows that even a perfect, ground-truth validator only reaches the
   epidemic threshold rather than comfortable containment, and that the failure
   is not an artefact of one model: it reproduces across judge capability
   (frontier Claude models) and across model family (a Claude judge fails the
   same way as the original Llama judge). A negative result of this kind, with
   an identified mechanism and a stated quality bar a validator must clear, is
   more useful to practitioners than the confirmatory result originally
   anticipated.

4. **An open-source, reproducible testbed.** The full pipeline — KG population
   from ground-truth facts, controlled injection of the three error types,
   the epidemiological measurement harness, and the mitigation framework — is
   released as a controlled environment for studying contamination dynamics,
   with a clean-room experimental protocol and multi-seed replication
   throughout.

## 1.6 Scope and honest framing

Two framing points are stated at the outset so they colour everything that
follows. First, the contamination studied here is **injected**, not observed
in the wild: the thesis characterises the *conditional* dynamics — given that
an error enters the retrieval-reachable memory, how does it spread — rather
than how often such errors arise unprompted, which is measured separately and
found to be small. Second, the project's central mitigation hypothesis was
**refuted, not confirmed**, and the thesis reports that refutation and its
mechanism directly rather than reframing it. Chapter 6 collects the full set
of limitations and deviations from the original research proposal in one
place. The intent throughout is that a reader can trace every quantitative
claim to an archived result file and can see exactly where the evidence
supports a strong claim and where it supports only a hedged one.

## 1.7 Structure of the thesis

The remainder of the thesis is organised as follows. **Chapter 2** reviews the
related work across the three fields the thesis joins: multi-agent LLM systems
and their failure modes, epidemiological modelling of information spread, and
provenance and uncertainty in databases. **Chapter 3** presents the
methodology — the agent architecture, the KG and provenance schema, the error
taxonomy and injection mechanism, the SIR formulation and R₀ derivation, the
Trio-inspired mitigation, and the experimental design and metrics. **Chapter
4** covers the implementation: infrastructure, dataset preparation, the agents
and their prompts, the injector, the simulation runner, and the mitigation
module, including the hardware constraints that shaped several design choices.
**Chapter 5** reports the results — baseline performance, contamination
propagation and its SIR fits, R₀ across error types and configurations, the
architectural dose–responses, the mitigation arms, and the cross-family and
cross-capability robustness checks — with full statistics. **Chapter 6**
discusses the findings against each research question, and states the
limitations, threats to validity, and deviations from the research proposal.
**Chapter 7** concludes with a summary of contributions and their practical
implications for the designers of shared-memory multi-agent systems.
