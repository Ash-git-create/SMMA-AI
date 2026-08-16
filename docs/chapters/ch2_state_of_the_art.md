# Chapter 2 — State of the Art

<!-- Written paragraph by paragraph under docs/writing/00_protocol.md.
     Only approved content lives here. -->

## 2.1 Background

### 2.1.1 Multi-agent LLM systems and shared memory

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

Retrieval is the channel this thesis studies. In its simplest form, retrieval-augmented
generation matches a query against a store of text and returns the most similar passages,
which are then placed in the model's prompt. Similarity is increasingly measured with dense
vectors: a model trained for the purpose turns the query and each passage into a list of
numbers, and the passages whose numbers sit closest to the query's are returned [21]. The
generator then answers using those passages as context.

A knowledge graph changes what is retrieved. Instead of passages, the store returns facts
and the links between them, and retrieval can follow those links across several steps to
gather facts that are related but not next to each other, which is what multi-hop questions
need. Placing a knowledge graph behind a language model in this way is now a distinct line
of work [22], including the graph-based retrieval of GraphRAG mentioned above [3]. For this
thesis the point is simple: whatever an agent retrieves becomes the ground it reasons on,
so a contaminated fact that is retrieved is a contaminated fact that gets used.

How a knowledge graph is built shapes how contamination behaves in it. A knowledge graph
stores each fact as a triple of the form (subject, relation, object), a format that comes
from the Resource Description Framework, a web standard for recording facts as links
between things. Subjects and objects are entities, ideally drawn from a shared vocabulary
so the same thing is always named the same way, and the relation names the tie between
them. Facts enter the graph in one of three ways: entered by hand, imported from an
existing structured source, or extracted from text by a program. This thesis uses the
third route, and it is the one that lets errors in, because a model reading text can
misread it.

Because extracted graphs contain mistakes, a body of work studies how to find and fix
them, under the name knowledge-graph refinement [28]. Refinement methods look for facts
that are internally inconsistent, that contradict the rest of the graph, or that are
unlikely given the graph's structure. They share an assumption: that an error leaves a
trace the rest of the graph can reveal. One of this thesis's findings is that a common
extraction error, replacing a correct value with a wrong one, leaves no such trace,
because it overwrites the very evidence a refinement check would rely on.

Sharing a memory between agents is also an old idea. Early artificial-intelligence systems
used a blackboard architecture, in which independent modules read from and wrote to a
common workspace and coordinated only through what they left there, rather than by
messaging each other directly [29]. A shared knowledge graph is a modern version of that
pattern. It brings the same benefit, that any agent can build on any other's work, and the
same risk, that a wrong entry misleads whoever reads it next. Much of this thesis is a
study of that risk in its modern form.

### 2.1.2 Hallucination in large language models

A hallucination is an output from a language model that is not supported by its input or
by fact [4]. Hallucinations happen because of how these models work. A language model is
trained to predict likely text, not to check facts, so it will produce a fluent and
confident sentence whether or not that sentence is true. When the model is asked about
something its training did not cover well, or when it extracts facts from a document
under length or format pressure, it fills the gap with a plausible guess. Surveys of the
problem show it is widespread across models and tasks [9].

Two further properties of these models matter for what follows. First, their errors tend to
compound: a model shown its own earlier output stays consistent with it, so an early mistake
is carried forward instead of corrected, and a short chain of steps can drift further from
the facts at each one [9]. Second, the same models have no built-in step that checks a
statement against a source of truth before writing it down, so nothing inside the model
stops a plausible-sounding error from being produced [9]. Extraction, the task at the centre
of this thesis, meets both conditions at once, because it asks the model to turn free text
into filled, structured slots at speed.

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

If hallucinations cannot be prevented, the natural response is to detect them, and how to
do that is its own research area. One approach asks the model itself: the same claim is
generated several times, and claims the model states inconsistently across those samples
are treated as likely hallucinations [23]. A different approach checks the claim against an
outside source, retrieving evidence and asking whether it supports the claim. Judge-based
methods take this further and use a second language model to rate an answer [24]. The
validator in this thesis combines the last two: it judges a fact against the evidence held
in the graph.

These methods share a weakness that matters here. A detector that checks a claim against
retrieved evidence can only work if the evidence is there to check against. When the
contamination has replaced the original fact rather than sitting beside it, there is no
contradicting evidence to find, and the detector is blind to it. Chapter 5 shows this is
exactly what happens to the validator, and Section 5.4.3 names the mechanism.

Once an error is written into shared memory, the question becomes how far it travels. When
one person passes a claim to others who pass it on again, the result is an information
cascade, and false claims cascade as readily as true ones. A large study of news spreading
on social media found that false stories reached more people and spread faster than true
ones, partly because they were more novel and drew stronger reactions [32].

Studies of spreading behaviour distinguish two ways things spread [33]. In simple contagion
a single exposure is enough to pass something on, as with a cold or a simple rumour. In
complex contagion a person takes something up only after several other people already have,
which is common for beliefs and habits. The contamination this thesis studies behaves like
simple contagion: one retrieval of a wrong fact is enough for an agent to reuse it, because
the agent treats whatever it retrieves as trustworthy without waiting for a second source to
confirm it. That single-exposure behaviour is what makes the epidemic model of the next
section a good fit.

### 2.1.3 Epidemiological models: the SIR framework

To measure how an error spreads, the thesis borrows a model from epidemiology, the study
of how diseases move through a population. The most established such model is the
Susceptible-Infected-Recovered model, or SIR, first set out by Kermack and McKendrick in
1927 [11]. It divides a population into three groups. Susceptible members can still catch
the disease. Infected members have it and can pass it on. Recovered members have had it
and can no longer spread it. Over time, members move from Susceptible to Infected to
Recovered.

Two rates govern this movement. The transmission rate, written as β, sets how quickly
the disease passes from infected to susceptible members. The recovery rate, written as
γ, sets how quickly infected members stop being infectious. From these two rates
comes the model's central quantity, the basic reproduction number R₀, equal to β
divided by γ [12]. R₀ counts how many further cases one infected member sets off
before recovering, when everyone around is still susceptible. The value one is the
dividing line: above one, each case leads to more than one more and the infection keeps
growing; below one, the chain of cases shrinks and the outbreak ends on its own.

The model is written as a set of update rules applied once per time step. Writing S, I,
and R for the counts in each group and N for the total, a discrete-time step updates the
three groups as follows:

![](docs/figures/fig_sir_equations.png)

The first rule moves new infections out of the susceptible group, the second adds them to
the infected group and takes recoveries out of it, and the third collects the recoveries.
The reproduction number R₀ = β/γ follows from these rules: an infected member stays
infectious for about 1/γ steps and infects about β others per step while the
population is still mostly susceptible, so it produces about β/γ new cases before
it recovers.

The basic SIR model makes three simplifying assumptions: a closed population, with no
members entering or leaving during the outbreak; homogeneous mixing, so that every member
is equally likely to meet every other; and a single infected state that collapses the whole
course of an infection into one stage. These assumptions keep the model simple to fit, and
they are reasonable for the short, closed runs this thesis studies.

When an infection has a latent period, during which a member is infected but not yet
infectious, a fourth group is added between Susceptible and Infected, giving the SEIR model,
with E for exposed [34]. Other variants let recovered members lose immunity and turn
susceptible again. This thesis keeps the plain SIR form, because a contaminated fact is
either able to spread or has been quarantined, with no meaningful latent stage, and because
the simpler model has fewer parameters to fit from short runs. Section 3.4 states how the
model is fitted here.

The basic model assumes everyone mixes with everyone equally, which real populations do
not. A more realistic version places the population on a network, where each member makes
contact only along its links [25]. On a network the spread depends on the shape of the
connections as well as on β and γ. Members with many links, the hubs, are more
likely both to catch an infection and to pass it on, so a small number of highly connected
members can drive most of the spread. These are the superspreaders, and on a strongly
hub-dominated network the usual threshold at R₀ = 1 can break down, with infections
persisting at transmission rates that would die out in a well-mixed population [26].

A knowledge graph is exactly such a network. Its facts are not all equally connected: a few
popular entities are linked to very many facts, while most are linked to few. A
contaminated fact attached to a highly connected entity is retrieved far more often than
one on the fringe, and can act as a superspreader. Chapter 5 returns to this when it
examines why certain error placements spread much further than others.

It also helps to separate two things an outbreak can be measured by. One is how fast it
grows, which R₀ captures. The other is how far it eventually reaches, meaning the share of
the population infected by the time it stops, known as the final size. In the classic model
the two move together, since a higher R₀ produces a larger final size. They come apart when
new susceptible members keep arriving, because then even a slow-spreading process can build
up a large cumulative reach over many steps. The shared memory studied here is closer to
that second case, since fresh facts keep entering it, so this thesis measures both the speed
at which contamination spreads and the total number of facts it eventually touches, because
a design can do well on one and badly on the other.

Epidemiology also gives a target for control. To stop an infection from growing, enough of
the population must already be immune that each new case reaches, on average, fewer than one
susceptible member. The fraction that must be protected for this to hold is 1 - 1/R₀, so a
faster-spreading infection, with a higher R₀, demands that a larger share be covered [12].
The same arithmetic applies to a contaminated knowledge graph. Once validation has already
protected part of the graph, the quantity that matters is the effective reproduction number,
meaning the same count measured when not everyone is still susceptible. Validation has to
reach enough of the graph to pull that number below one, and how much coverage that takes
rises with how readily errors spread. Chapter 5 examines how large that share has to be, and
what happens to the spread when it is not met.

The same three states map onto the facts in a shared memory, shown in Figure 2.1. A
knowledge-graph fact is susceptible when it is correct but not yet checked, infected when
it has been contaminated by an error, and recovered when a validation step has caught and
quarantined it. Transmission happens when an agent retrieves a contaminated fact and
writes new contaminated facts from it, so β stands for how often the graph is read and
how readily a model reuses what it reads. Recovery happens when a validation step catches
an error, so γ stands for how good that checking is. Section 3.4 gives the exact form
of these rules used in the thesis and how R₀ is fitted from a run, so that the threshold
at one becomes a direct test of whether a design contains an error or lets it spread.

![Figure 2.1: The SIR model mapped onto knowledge-graph facts. A fact moves from Susceptible (clean, unchecked) to Infected (contaminated) at rate β, and from Infected to Recovered (quarantined) at rate γ.](docs/figures/fig_sir_compartments.png)

### 2.1.4 Provenance and uncertainty in databases: the Trio system

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

The lineage formula is what makes the confidence numbers add up. It is a boolean
expression that records how a derived fact was built from earlier ones. If a fact was
concluded from two earlier facts that were both needed, its lineage is their AND; if it
could have come from either of two independent sources, its lineage is their OR.
Confidence is then read off this formula by turning the logic into arithmetic, a step
called arithmetization. For two independent facts, an AND multiplies their confidences,
because both must hold; an OR combines them as 1 - (1 - c1)·(1 - c2), which multiplies the
chance of each source being wrong and so leaves a higher confidence than either source
alone. This lets the system work out a derived fact's confidence directly from its
ancestors' confidences, without re-checking the whole chain by hand.

Computing these confidences exactly is expensive. When many facts share ancestors, their
lineage formulas overlap, and working out the exact probability that a derived fact is
correct becomes hard as the formulas grow, a difficulty studied in probabilistic databases,
systems that store facts alongside their probability of being true [27]. This thesis takes a
practical shortcut instead: rather than solve the full formula, it combines the parent
confidences with the simple arithmetic rules above, treating the ancestors as independent.
That is an approximation, and it trades some exactness for the ability to keep confidences
up to date as the graph grows, which is what a live shared memory needs.

Database research distinguishes several kinds of provenance, usually summarised as why,
how, and where. Why-provenance names the source records that justify a result;
how-provenance records the way they were combined; and where-provenance points to the
exact place a value was copied from [13]. The lineage this thesis uses is closest to why-
and how-provenance: it records which earlier facts a derived fact rests on and, through the
boolean formula, how they were combined. That is enough to trace a wrong fact forward to
its dependents, which is what the mitigation needs.

Storing facts with confidences turns a database into a probabilistic database, one that
represents many possible states of the world at once, each with its own probability [30].
A query over such a database returns, in principle, an answer for every possible state,
weighted by how likely that state is. This is a powerful idea, and it is also where the
cost comes from: the number of possible states grows very quickly, so exact answers are
expensive, which is why practical systems approximate, as described above.

A later line of work showed that many of these provenance and confidence calculations are
instances of one algebraic pattern, in which combining facts corresponds to two operations
that behave like addition and multiplication [31]. This is the same pattern the mitigation
uses when it multiplies confidences for an AND and combines them for an OR. The value of
the pattern here is modest but real: it means the simple arithmetic the mitigation performs
rests on an established footing rather than being an arbitrary choice.

Applied to a shared knowledge graph, these ideas give each fact a confidence score and a
lineage that links it to the facts it was derived from. An agent can then be told to
retrieve only facts above a confidence threshold, and when an error is found, the system
can walk the lineage and lower the confidence of every fact that descended from it.
Chapter 3 describes the version of this the thesis builds, and Chapter 5 reports how well
it works. Section 2.3 places that result against other recent attempts to use
provenance-like ideas for the same purpose.

## 2.2 Related Work

Three strands of recent work touch this thesis: attacks on agent memory, models of how
errors spread between agents, and attempts to contain that spread. This section describes
each strand, and Section 2.3 sets out where this thesis sits against it. The first strand
is adversarial. Recent work shows that an attacker can poison a shared memory by feeding
it crafted inputs, so that later retrievals return the attacker's content [16]. This work
matters, but it assumes an attacker with intent. The errors this thesis studies have no
attacker behind them.

The second strand models how errors move between agents once they are present. Niu et al.
[5] adapt a compartmental epidemic model to a network of language-model agents and derive
the conditions under which errors invade the network. Jamshidi et al. [17] track factual
errors as they pass down a chain of agents and find, on their setup, that the errors
shrink rather than grow. Liu [18] studies how the preferences of a language model acting
as an evaluator spread to other agents. These works share this thesis's view of error
spread as a contagion, but they place the contagion on the agents and the messages
between them.

The third strand tries to contain the spread. Xie et al. [6] inject a single error into a
group of collaborating agents and add a governance layer that tracks each message's
ancestry. They report that it stops the error from taking over in most runs. Margalit et
al. [19] name the failure modes of shared agent memory, including the loss of provenance,
and propose provenance tracking and governed sharing as the fix. Itkin [20] studies the
timing of validation and finds that correcting too late, or too aggressively, can
destabilise the agents' shared belief rather than settle it. The first two propose or
assume that provenance-like machinery will contain the spread.

These three strands give the immediate context for this thesis. Section 2.3 compares them
with the present work point by point and states what it adds.

## 2.3 Related Work Comparison

### 2.3.1 Non-adversarial versus adversarial contamination

The adversarial work in Section 2.2 and this thesis study the same object, a corrupted
shared memory, but from opposite ends. Attacks such as PoisonedRAG [16] start from an
attacker who chooses the false content and places it to cause a chosen effect. This
thesis starts from no attacker at all. The false content is whatever a well-behaved model
happens to get wrong, and where it lands is decided by the ordinary work of extraction,
not by design. The two settings need different defences: an adversarial defence looks for
a malicious source, while the non-adversarial case has nothing malicious to find. The
thesis therefore measures how a chance error spreads, not how an attacker's payload is
delivered.

### 2.3.2 Contagion on facts versus contagion on agents

The error-spread models in Section 2.2 and this thesis both treat spreading error as a
contagion, but they disagree on what carries it. Niu et al. [5], Jamshidi et al. [17],
and Liu [18] follow the error as it moves between agents through the messages they
exchange. This thesis follows it as it moves between facts in a shared knowledge graph.
The difference is not cosmetic. A message-passing chain and a shared graph have different
shapes: a chain passes each output once to the next agent, while a graph lets any agent
retrieve any fact at any later step. The unit of contagion here is a stored fact, the
basic unit a graph-based memory is built from and retrieved by. The reproduction number
is measured over those facts rather than over the agents.

This difference in structure shows up in the results. Jamshidi et al. [17] report that
errors shrink as they pass down a message chain, because each error is diluted by fresh
input at every step. In a shared knowledge graph the picture is different: a contaminated
fact can be retrieved again and again by many agents, so it is reinforced rather than
diluted, and the spread does not die out on its own (Chapter 5). The two results describe
two different architectures, and this thesis's setting is the graph case, not the chain
(Figure 2.2).

![Figure 2.2: Two pictures of contagion. In a message chain (left) an error is passed once and diluted at each step. In a shared knowledge graph (right) one contaminated fact is retrieved by many agents and used to write more contaminated facts, so it is reinforced.](docs/figures/fig_contagion_contrast.png)

### 2.3.3 Testing provenance mitigation rather than assuming it

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

One containment result points the same way as this thesis rather than against it. Itkin
[20] finds that the timing of correction decides whether shared belief settles or breaks
down. This thesis finds an analogous effect: how often the shared memory is checked has a
threshold of its own, where any regular in-run checking holds the spread down but
deferring all of it to the end lets the outbreak run (Chapter 5). The two thresholds are
not the same quantity. Still, that two independent studies both find the timing of
correction to have a threshold is a point in favour of the finding, and the thesis treats
Itkin's result as convergent evidence.

Table 2.1 draws these comparisons together across the dimensions that matter for this
thesis: what the error spreads over, whether the setting is a shared knowledge-graph
memory, and whether a provenance-style mitigation is actually built and tested rather than
proposed.

[TBL]Table 2.1: How this thesis compares with the closest recent work.

| Work | Error spreads over | Shared KG memory | Provenance mitigation |
|---|---|---|---|
| This thesis | facts in the graph | yes | built and tested; fails under a realistic validator |
| Niu et al. [5] | agents and messages | no | not addressed |
| Jamshidi et al. [17] | an agent chain | no | none (finds attenuation) |
| Xie et al. [6] | agents and messages | no | genealogy layer, reported to work |
| Margalit et al. [19] | shared agent memory | in part | proposed, not stress-tested |
| Itkin [20] | agent beliefs | no | correction timing studied |
| Zou et al. [16] | a retrieval store | no | none (adversarial attack) |

## 2.4 Summary

This chapter laid out the four ideas the thesis builds on and reviewed the recent work
closest to it. The background introduced the four: multi-agent systems that share a
knowledge-graph memory, the hallucinations that put wrong facts into that memory, the SIR
model that measures how a contagion spreads, and the database idea of provenance that the
mitigation is built from. The related work then showed that the problem is current.
Several 2026 papers model how errors spread between agents; others try to contain that
spread with provenance-like machinery.

Two gaps run through that work. The spread is modelled over agents and the messages
between them, not over the facts in a shared knowledge graph. That graph is the level at
which a memory system is actually built and queried. And the containment work reports that
provenance-like machinery works, but shows this under favourable conditions rather than
under the ordinary, imperfect validator a real system runs. This thesis is built to close
both gaps: it measures contagion at the level of facts in a shared graph, and it tests a
provenance-aware mitigation under a realistic validator instead of assuming it succeeds.

Chapter 3 turns this position into a method. It describes the agents and the shared
graph, the three error types and how they are injected, the SIR model and how the
reproduction number is computed, and the provenance-aware mitigation the thesis puts to
the test.
