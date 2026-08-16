# Chapter 1 — Introduction

<!-- Reworked paragraph by paragraph under docs/writing/00_protocol.md.
     Only approved paragraphs live here. Old pre-draft: _predraft/ch1_introduction_v0.md -->

## 1.1 Motivation

A large language model, or LLM, produces text by repeatedly predicting the next word.
That is enough to answer a question or summarise a document, but the model predicts
likely text, not checked facts, and that gap is where this thesis begins. On its own
an LLM handles one task at a time. Over the last few years developers have started
wiring several of them together, giving each model a narrow role such as searching for
sources, pulling facts out of a document, or writing the final answer, and letting the
models pass work to each other to finish a larger job. A setup like this is a
multi-agent system, and each model inside it is an agent. Frameworks such as AutoGen
[1] and MetaGPT [2] made these systems easier to build.

The agents need a way to share what they find. They can pass long messages back and
forth, but that gets slow, and a model starts to forget earlier steps once the
conversation grows too long. A steadier option is a shared memory: one store that
every agent can write to and read from. A natural way to build that store is a
knowledge graph, which records a fact as a link between two things, for example
(Paris, capital of, France). Because the graph holds each fact as its own small,
searchable entry, work that one agent extracts can be organised and retrieved later
instead of worked out again [3]. In a shared setting that also means a fact one agent
writes becomes something another agent can read and build on. The graph becomes the
group's shared notebook.

That shared notebook is also the weak point. LLMs make mistakes even when nobody is
trying to trick them. They state facts that their input never supported, attach a fact
to the wrong name, or drop a detail such as a date that changes what the fact means.
This behaviour is usually called hallucination [4]. When one model works alone, a
wrong answer stays a local problem: the user reads it and moves on. In a shared-memory
system it does not stay local. Once a wrong fact is written into the graph, the next
agent that reads it has no easy way to tell it apart from a correct one, because it
came from the same trusted store. That agent can then build on the wrong fact and
write new, also wrong, facts back into the graph.

This is the situation the thesis studies. As more systems place several LLMs around
one shared memory, the cost of a single bad write no longer stops at one answer. It
can pass to other agents and grow. Work on LLM safety has mostly checked one model or
one output at a time, which can miss an error that only causes damage after it travels
through a shared store; Chapter 2 looks at that gap in detail. The thesis asks how far
such errors spread, what makes them spread, and whether a memory that records where
each fact came from can hold them back.

## 1.2 Problem Statement

The failure this thesis is built around has a specific shape. In a shared-memory
multi-agent system, one agent's wrong fact does not stay a single wrong answer. It gets
written into the shared graph, retrieved by other agents as if it were true, used to
derive new facts, and written back. The error reproduces and spreads. This thesis calls
that pattern cascading knowledge contamination. It needs no attacker. It runs on the
ordinary mechanics of extraction, retrieval, and reuse that make shared memory useful
in the first place.

The reason a cascade is worth worrying about is that errors in a chain multiply rather
than add. Here is a simple illustration. If every step in a ten-step pipeline were
correct 95% of the time, and each step depended on the step before it, the whole chain
would be correct about 60% of the time, because 0.95 to the tenth power is 0.599. A
system built from reliable parts is wrong about four times in ten. The real systems
studied in this thesis are far more reliable per step than 95%, so this number
illustrates the mechanism rather than measuring the thesis. The narrow point still
holds: in a system where each step depends on the last, a per-step error rate that
looks tiny on its own stops being tiny once errors can feed each other.

Three things are missing from how this failure is usually understood, and Chapter 2
develops each one with the relevant literature. First, much of the work on LLM errors
focuses on the adversarial case, where someone crafts a malicious input to corrupt a
model, while the errors here are honest mistakes by well-behaved models. Second, the
common safety checks work on a single output at a time, so they cannot see a problem
that only shows up in how the whole system behaves over many steps. Third, no measure
of a cascade has become standard: there is not yet an agreed number that tells a
designer whether a system will contain an error or let it spread. Recent work has begun
to propose such models, but none has become the shared reference, so in practice
contamination is still described after it happens rather than predicted beforehand.

So the problem this thesis takes on has two halves: to show how non-adversarial
contamination spreads through a shared-memory system, and to measure that spread in a
way a designer can use before deployment rather than only explain after the fact. This
matters because such systems are already being built with frameworks like the ones
named above [1], [2]. A design that quietly amplifies its own errors is most dangerous
in the settings these systems are aimed at, such as research assistants or clinical and
financial tools, where a wrong fact carries real cost. Measuring the spread lets designs
be compared, so a design that contains contamination can be told apart from one that
does not.

## 1.3 Research Questions

The problem breaks into four research questions. They build on each other. The first
asks whether contamination happens at all and under what conditions. The next two ask
what makes it worse. The last asks whether it can be stopped without spoiling the
system's answers.

**RQ1. Under what conditions do non-adversarial errors (no attacker involved) persist
and spread through a shared-memory multi-agent system, instead of dying out?**
This asks whether a single injected error stays where it is put, spreads to other parts
of the memory, or fades, and what has to be true of the system for each outcome.

**RQ2. Which type of extraction error damages later reasoning the most: an entity
disambiguation error (a fact attached to the wrong name), qualifier loss (a dropped
condition such as a date), or relation strengthening (a weak link restated as a strong
one)?**
This ranks the three error types by how far they spread and how much they hurt answers.

**RQ3. How do a system's design choices change how fast and how far contamination
travels?**
The choices studied are how densely the knowledge graph is connected, how often agents
write to the shared memory, and how often that memory is checked for errors.

**RQ4. Can provenance-aware retrieval reduce contamination without hurting answer
quality?**
Provenance means a record of where each fact came from. A provenance-aware system uses
that record in two ways: it holds back facts whose confidence is too low so agents do
not retrieve them, and, once a fact is found to be wrong, it lowers the trust in every
later fact built on that one (its descendants). This is the mitigation the thesis tests,
adapted from database provenance research; Chapter 3 describes how it is built. The
question also asks where this mitigation stops working.

The first three questions describe the problem: when contamination spreads, which
errors drive it, and which design choices control it. The fourth asks what to do about
it. Chapter 5 answers all four against the experiments, and Chapter 6 discusses what the
answers mean for anyone building these systems.

## 1.4 Approach

The thesis studies contamination in a controlled testbed rather than in a live product.
Working in a testbed means the error can be placed on purpose, at a known spot, and then
watched as it moves. A live system would not allow that: real errors appear at random
and are hard to trace cleanly. The cost is that a testbed is a simplified stand-in for a
real system, a point Chapter 6 returns to.

The testbed has three parts. The first is a knowledge graph stored in Neo4j, a database
built to hold networks of linked facts. This graph is the shared memory, and it starts
out filled with correct facts from the T-REx dataset, a large set of facts drawn from
Wikipedia, which acts as the clean starting population. The second part is a small set
of agents, built on open language models, that read text from two datasets, the
question-answering set HotpotQA and the claim-checking set FEVER, pull facts out of it,
and write those facts into the graph. The third part is a set of agents that read from
the graph to answer questions. Chapter 3 gives the full design and Chapter 4 the
implementation.

To create contamination on demand, the thesis injects the three error types from RQ2
into chosen facts, one type at a time, so their effects can be told apart. As the agents
work, a snapshot of the graph is recorded at each step, and every fact is marked as
clean, contaminated, or caught, matching the Susceptible, Infected, and Recovered states
of the SIR model. The SIR model is borrowed from how epidemiologists track a disease
through a population. It turns the step-by-step counts into a single number, the basic
reproduction number R0, which says whether one contaminated fact tends to produce more
than one new contaminated fact (spread) or fewer than one (fade).

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

## 1.5 Thesis Contribution

This thesis makes four contributions.

The first is a way to measure contamination as if it were a disease. The thesis applies
the SIR model to the facts held in a shared knowledge graph and reads off a reproduction
number for each error type and each system setting. Other recent work [5] models error
spread in multi-agent systems as a contagion over the agents and the messages they pass;
this thesis places the contagion on the facts in the shared memory instead. Chapter 2
sets out that difference.

The second is an empirical study of how non-adversarial contamination spreads: which
conditions let it persist and spread, which error types are most harmful, and how the
design choices of RQ3 change its speed and reach. The findings are reported in Chapter 5.

The third is a negative result on mitigation. The project set out to show that a
provenance-aware memory, built from database lineage ideas, would contain contamination.
Under a realistic language-model validator it does not, and the thesis identifies the
reason. Chapter 5 gives the evidence and Chapter 6 discusses what it means.

The fourth is the testbed itself: a pipeline that fills the graph, injects the errors,
measures the spread, and runs the mitigation, under a fixed experimental procedure and
with repeated runs under different random seeds. It is prepared for open release so that
others can reproduce and extend the work.

## 1.6 Thesis Outline

The rest of the thesis is organised as follows. Chapter 2 reviews the work this thesis
builds on and sets it apart from the recent papers closest to it. Chapter 3 describes the
method: the agents, the knowledge graph and how each fact carries its history, the three
error types and how they are injected, the SIR model and how R0 is computed, and the
provenance-aware mitigation. Chapter 4 covers how all of this was actually built,
including the hardware limits that shaped some of the choices. Chapter 5 reports the
results, from the clean baseline through the contamination experiments, the reproduction
numbers, the effect of the design choices, and the mitigation. Chapter 6 discusses what
the results say about each research question and states the limits of the study. Chapter
7 concludes.
