# 2.1 Background (working draft — awaiting gates; block-level approval)

## 2.1.1 Multi-agent LLM systems and shared memory

Chapter 1 introduced multi-agent systems and shared memory in outline. This section
fills in the background a reader needs before the rest of the thesis. A multi-agent
system built on large language models divides a task among several model-driven agents
that each handle one part and pass results to one another [7]. Frameworks such as
AutoGen [1] and MetaGPT [2] provide the plumbing for this: they let a developer define
agents, give each a role, and set the rules by which they talk. The idea is that a group
of specialised agents can solve problems that are too large or too varied for one model
working alone.

Agents coordinate in one of two broad ways. They can pass messages directly, each
sending its output to the next as text. Or they can share a common memory that all of
them read from and write to. Direct message passing is simple but limited: the
conversation grows long, earlier detail is lost, and a fact found by one agent is not
easily reused by another later on. A shared memory removes these limits by giving every
agent a common store. When that store is searched to supply an agent with relevant facts
before it answers, the pattern is called retrieval-augmented generation [8], which
grounds a model's output in retrieved text rather than in its trained weights alone.

Much of this shared memory is built as a knowledge graph, a store that holds each fact
as a labelled link between two entities, such as (Paris, capital of, France). A
knowledge graph makes the relationships between facts explicit and supports the
multi-step retrieval that multi-agent tasks need, and recent systems use it directly as
the memory that agents query [3]. Because every agent both reads and writes this graph,
the correctness of the whole system depends on the correctness of what is written into
it. That is the property the rest of this thesis studies. It is also why the thesis
attaches to each fact a record of where it came from, an idea drawn from database
provenance research and covered in Section 2.1.4.

## 2.1.2 Hallucination in large language models

A hallucination is an output from a language model that is not supported by its input or
by fact [4]. Hallucinations happen because of how these models work. A language model is
trained to predict likely text, not to check facts, so it will produce a fluent and
confident sentence whether or not that sentence is true. When the model is asked about
something its training did not cover well, or when it extracts facts from a document
under length or format pressure, it fills the gap with a plausible guess. Surveys of the
problem show it is widespread across models and tasks [9].

Researchers separate hallucinations along two lines. The first is faithfulness against
factuality [10]: a faithful output stays true to the given source text, while a factual
output stays true to the world, and a model can fail either one. The second is where the
error sits. An extraction step can attach a fact to the wrong entity, drop a qualifier
that limits when a fact holds, or state a relationship more strongly than the source
allows. These are ordinary, non-adversarial mistakes: no attacker causes them, they are
simply how models sometimes fail.

This thesis works with three such error types, chosen because they are common and because
their effects can be separated cleanly: entity disambiguation errors, qualifier loss, and
relation strengthening. Chapter 3 defines each one precisely and explains how it is
injected into the knowledge graph on purpose. The point for now is that these are the
kinds of mistake a well-behaved model makes during normal use. What matters for this
thesis is what happens to such a mistake after it is written into shared memory.

## 2.1.3 Epidemiological models: the SIR framework

To measure how an error spreads, the thesis borrows a model from epidemiology, the study
of how diseases move through a population. The most established such model is the
Susceptible-Infected-Recovered model, or SIR, first set out by Kermack and McKendrick in
1927 [11]. It divides a population into three groups. Susceptible members can still catch
the disease. Infected members have it and can pass it on. Recovered members have had it
and can no longer spread it. Over time, members move from Susceptible to Infected to
Recovered.

Two rates govern this movement. The transmission rate, written as beta, sets how quickly
the disease passes from infected to susceptible members. The recovery rate, written as
gamma, sets how quickly infected members stop being infectious. From these two rates
comes the model's central quantity, the basic reproduction number R0, equal to beta
divided by gamma [12]. R0 counts how many further cases one infected member sets off
before recovering, when everyone around is still susceptible. The value one is the
dividing line: above one, each case leads to more than one more and the infection keeps
growing; below one, the chain of cases shrinks and the outbreak ends on its own.

The same mathematics fits the spread of an error through a shared memory. A
knowledge-graph fact can be susceptible (correct but not yet checked), infected
(contaminated by an error), or recovered (found and quarantined). Transmission happens
when an agent retrieves a contaminated fact and writes new contaminated facts from it,
and recovery happens when a validation step catches an error. Section 3.4 sets out
exactly how the thesis maps these states onto the graph and computes R0 for each error
type and system setting, so that the threshold at one becomes a direct test of whether a
given design contains an error or lets it spread.

## 2.1.4 Provenance and uncertainty in databases: the Trio system

The mitigation this thesis tests comes from database research on provenance, which ties
each piece of data to the sources and operations that produced it [13]. In a database,
provenance answers questions such as which source records a result was computed from and
what operations produced it. If a source record turns out to be wrong, provenance lets
the system find every result that depended on it. This is exactly the ability a
contaminated shared memory needs: a way to trace a bad fact forward to everything built
on top of it.

The Stanford Trio system built this idea into a working database that treats uncertainty
and lineage as first-class parts of the data [14]. Its data model, the
Uncertainty-Lineage Database, represents an uncertain fact as a set of alternative
possible values, each carrying how confident the system is that it is the correct one,
together with a lineage formula recording which earlier values it was derived from [15].
A derived value's confidence is then computed from the confidence of its ancestors.
Because lineage records these dependencies, a value that is later found to be wrong can
be traced forward to the values that were built on it, following the general provenance
idea of the previous paragraph. The thesis uses a simplified form of this model in which
each fact holds a single value rather than a set of alternatives, described in Chapter 3.

Applied to a shared knowledge graph, these ideas give each fact a confidence score and a
lineage that links it to the facts it was derived from. An agent can then be told to
retrieve only facts above a confidence threshold, and when an error is found, the system
can walk the lineage and lower the confidence of every fact that descended from it.
Chapter 3 describes the version of this the thesis builds, and Chapter 5 reports how well
it works. Section 2.3 places that result against other recent attempts to use
provenance-like ideas for the same purpose.
