# Chapter 3 — Methodology

<!-- Reworked from _predraft/ch3_methodology_v0.md, paragraph by paragraph under
     docs/writing/00_protocol.md. Agent roles corrected against the code 2026-08-10. -->

## 3.1 System overview

The experimental system is a shared-memory multi-agent architecture: several agents
driven by language models read from and write to one central knowledge graph. This is
the pattern the thesis studies, chosen because the research questions concern exactly the
failure this architecture can cause. When many agents share one memory, an error written
by one of them becomes retrievable context for all the others. Figure 3.1 shows the whole
system.

Three agents work on the graph, each with a fixed role. The ExtractionAgent reads text
and turns it into subject-predicate-object triplets, short facts of the form (subject,
relation, object) such as (Paris, capital of, France), which it writes into the graph. It
also runs the step-by-step synthesis described below, in which retrieved facts are turned
into new ones. The OrchestrationAgent is a confidence judge: given a triplet and the
evidence for it already in the graph, it labels the triplet supported, unsupported, or
uncertain and gives it a confidence score. The ValidationAgent uses that judge to audit
the graph, quarantining triplets whose confidence is too low and deprecating anything
derived from them. Table 3.1 lists the model each agent runs.

[TBL]Table 3.1: The three agents, the model each runs, and its role.

| Agent | Model (as run) | Role |
|---|---|---|
| ExtractionAgent | Mistral Nemo 12B (Mistral API) | Turns text and retrieved facts into subject-predicate-object triplets and writes them to the graph |
| OrchestrationAgent | Llama 3.1 8B (Groq API) | Confidence judge: scores a triplet against its evidence as supported, unsupported, or uncertain |
| ValidationAgent | Llama 3.1 8B (Groq API) | Audits the graph with the judge, quarantines low-confidence triplets, deprecates their descendants |

Two different models are used, split by job. The ExtractionAgent runs the larger Mistral
Nemo 12B, which is stronger at pulling structured facts out of text, and this same model
also drives the step-by-step synthesis. The OrchestrationAgent and ValidationAgent run the
smaller and faster Llama 3.1 8B. This split, a stronger extractor and a faster judge, is
kept throughout. Section 4.1 describes how the models are hosted.

An experiment runs in discrete steps. In each step the system works through a batch of
entities. For each entity it retrieves up to five triplets linked to it in the graph,
assembles them into a working context (the block of facts placed in the model's prompt),
has the extraction model write new statements from that context, and stores the resulting
triplets back in the graph with a link to the facts they came from. Contamination spreads
at the moment a corrupted triplet is among those retrieved and changes what gets written
back. The retrieval step is therefore the route the contagion travels, which is why the
SIR model of Section 3.4 ties the transmission rate to how often the graph is read. Two
further pieces sit alongside this loop: the ErrorInjector, which seeds the controlled
errors that start each experiment (Section 3.3), and a separate question-answering step
that measures task quality by reading retrieved context (Section 3.7).

![Figure 3.1: The system architecture. The ExtractionAgent (Mistral Nemo 12B) both pulls facts from text and, in the propagation loop, synthesises new facts from retrieved ones, writing all of them into the shared Neo4j knowledge graph. The ValidationAgent (Llama 3.1 8B), using the OrchestrationAgent as its judge, audits the graph and quarantines unreliable facts. The ErrorInjector places controlled errors. Retrieval carries transmission (β) and validation carries recovery (γ).](docs/figures/fig_architecture.png)

## 3.2 Knowledge graph and provenance schema

The shared memory is a Neo4j graph. Neo4j stores data as nodes joined by labelled links,
which is the shape of a knowledge graph, so each fact lives in the store as two things
joined by a relation. Each fact is a triplet: a subject,
a predicate, and an object, such as (Marie Curie, won, Nobel Prize in Physics). Every
triplet is stored with a set of extra fields that record where it came from, how much it
is trusted, and its status. Table 3.2 lists them.

[TBL]Table 3.2: The fields stored with every triplet.

| Field | What it records |
|---|---|
| source_id | which document or earlier triplet the fact was drawn from |
| agent_id | which agent wrote it |
| timestamp | when it was written |
| confidence | how much the system trusts it, from 0 to 1 |
| lineage | the earlier facts this one was derived from |
| state | its SIR status (Susceptible, Infected, or Recovered); see Section 3.4 |
| error_type | ground-truth contamination label, kept for measurement and hidden from agents |

This layout follows the Trio model from Section 2.1.4. Each fact is stored with a value, a
confidence score, and a lineage formula. The lineage formula is written down at the moment
a derived fact is created: it records which retrieved facts the new one was built from, as
a boolean AND/OR expression over those facts (Section 2.1.4). This formula drives cascade
deprecation: when a fact is found to be wrong, the system follows it forward and deprecates
everything built on it (Section 3.5). Alongside it, the experiment keeps its own record of
how each error spread. Each injected error carries a root label that is passed forward to
every fact derived under its influence, so a propagated error can always be attributed to
the injected fact it came from. This attribution holds by construction; a fallback for
unattributed errors exists in the analysis code but never fired in any archived run.

One field needs care. The error_type field records the ground-truth contamination status
of a fact: whether it is clean, an injected error, or an error propagated from one. This
is bookkeeping for measurement only. The retrieval step passes triplets to the agents as
plain subject-predicate-object text, so error_type is never placed in the context the
model sees, and the agents cannot use it to tell clean facts from contaminated ones.
Without this hidden label the epidemiological measurement would have no ground truth to
compare against; if it were exposed to the agents, the experiment would be measuring a
system that can cheat.

Before each run the graph is loaded with about 50,000 correct triplets from the
T-REx dataset, a large set of facts drawn from Wikipedia and aligned with Wikidata. These
are the Susceptible population of the SIR model: accurate, but not yet checked by the
system, and stored in exactly the same form as anything an agent writes. Because a pristine
T-REx fact and an agent-written fact look identical in the graph, an agent has no built-in
way to tell a trustworthy starting fact from a freshly written, possibly contaminated one.
That is the condition the thesis studies.

## 3.3 Error taxonomy and controlled injection

Three types of non-adversarial error are used, chosen to cover the common ways an
extraction step goes wrong. An entity disambiguation error replaces the object with a
wrong but related entity, for instance confusing two things that share a name. A qualifier
loss drops a modifier that limits when or where a fact holds, such as a date or a place,
which quietly widens the claim. A relation strengthening upgrades a weak link into a strong
or causal one, turning "is associated with" into "caused". Table 3.3 shows each with an
example.

[TBL]Table 3.3: The three error types, with an illustrative example of each.

| Error type | What changes | Illustrative example (before, then after) |
|---|---|---|
| Entity disambiguation | a wrong but related entity replaces the object | (Georgia, capital is, Tbilisi), then (Georgia, capital is, Atlanta) |
| Qualifier loss | a time, place, or condition is dropped | (Obama, president of, USA in 2009-2017), then (Obama, president of, USA) |
| Relation strengthening | a weak link becomes a strong or causal one | (exercise, associated with, longer life), then (exercise, caused, longer life) |

![Figure 3.2: The three error injections. Each takes an original fact (left) and produces a corrupted one (right): an entity is swapped for a related but wrong one, a qualifier is dropped, or a weak relation is strengthened into a causal one.](docs/figures/fig_injection.png)

The ErrorInjector makes these changes to triplets already in the graph, corrupting 15
of them per error type in each run by default. These corrupted triplets are the index
cases, the starting points of the outbreak. Not every triplet can take every corruption:
relation strengthening, for example, needs a triplet whose predicate is genuinely weak to
begin with. The injector therefore filters for triplets that admit the change. When the
index cases are drawn from the part of the graph the task will actually query (the default,
explained next), relation strengthening usually finds only 9 or 10 eligible triplets
out of 15, while drawing from the whole graph always yields 15. Relation-
strengthening results are therefore reported with the number of index cases actually
placed.

Where the index cases are placed is itself a variable the thesis controls. By default they
are placed inside the active retrieval subgraph: the region of the graph that the task
workload actually reads, built from the entities the run will touch. A control condition
instead places the same number of index cases at random across the whole Susceptible graph
(the pristine T-REx facts). The contrast between these two conditions is what isolates
retrieval reachability as a necessary condition for spread, the first research question: an
error can sit in the shared memory and still go nowhere if no agent ever retrieves it.
Section 5.3 reports that contrast.

## 3.4 Epidemiological formulation

Section 2.1.3 set out the SIR model in general. This section fixes what its three states
mean for this system and how its rates are measured. A fact is Susceptible while it is a
pristine T-REx fact, correct but not yet checked. It becomes Infected the moment it is
contaminated, either because it is an injected index case or because an agent wrote it
while a contaminated fact was in its context. It becomes Recovered when the ValidationAgent
quarantines it. The counts of facts in each state, step by step, are the raw material for
the model.

The transmission rate β and the recovery rate γ each stand for something concrete
here. Beta is the chance, per step, that a contaminated fact in an agent's context leads it
to write a new contaminated fact; it rises with how often the graph is read and with how
readily the model reuses what it reads. Gamma is how effectively the validation step
catches and quarantines contaminated facts. The reproduction number R₀ = β / γ then
says whether one contaminated fact tends to produce more than one more. In runs that carry
no validation, γ is zero and R₀ is undefined; those runs are described instead by their
per-step effective reproduction, the average number of new contaminated facts each
contaminated fact produces in one step.

The states are measured from the run's own bookkeeping. The Infected count at each step is
the number of facts marked contaminated so far, minus the contaminated ones that have since
been quarantined; the Recovered count is the number of contaminated facts quarantined. From
these step-by-step counts, β and γ are estimated after the run by fitting the SIR
difference equations to the measured trajectory: the equations are run forward with trial
values until the simulated curve matches the observed one as closely as possible, using
non-linear least squares. Section 5.5 reports the fits and how well they match.

Two points about this fit need stating. First, the graph is large and the outbreak is
small: with about 50,000 facts and fewer than 100 ever infected, the
Susceptible pool never runs down, so the model cannot show the late flattening that a real
epidemic reaches when it runs out of susceptibles. The fit is therefore of the early,
growing phase, and its quality is reported alongside every estimate. Second, the fitted R₀
is checked against a simpler measure that needs no model: the number of new contaminated
facts each index case produces, counted directly from the lineage bookkeeping. This
model-free count is reported overall. A matching per-error-type breakdown answers the
second research question: which error type spreads most.

## 3.5 Trio-inspired mitigation framework

The mitigation under test adapts three mechanisms from the Trio model of Section 2.1.4,
each aimed at one part of the contagion. Section 3.4 tied spread to two rates: β, how
readily contaminated facts are retrieved and reused, and γ, how well validation catches
them. The first two mechanisms push on these two rates, and the third supports them.

The first mechanism is a confidence floor on retrieval. Every fact carries a confidence
score, and agents are only allowed to retrieve facts whose confidence is above a threshold,
set to 0.5. The aim is to keep low-confidence, possibly contaminated facts out of the
working context in the first place, which acts on the β channel by narrowing what can be
retrieved.

The second mechanism is validation with quarantine. On each step the ValidationAgent
samples a set of facts that agents read or wrote in that cycle, 25 of them, and
judges each one. A fact the judge scores below a quarantine threshold, set to 0.4, is
quarantined: it is moved out of retrieval and marked Recovered. Quarantine also triggers
cascade deprecation, the mechanism from Section 3.2: the system walks the lineage forward
from the quarantined fact and deprecates everything derived from it. This mechanism acts on
the γ channel, since it is the system's way of catching and removing infected facts.

The third mechanism is confidence propagation at write time. When a fact is derived from
retrieved ones, its confidence is not reset but computed from the confidence of its parents,
using the arithmetization of the lineage formula described in Section 2.1.4. The effect is
that uncertainty compounds along a chain of derivations rather than being forgotten at each
step, so a fact built on shaky ground inherits that shakiness.

These three mechanisms are treated as separate levers, not a single package. Alongside the
full combination, the experiments include configurations that switch on only the confidence
floor, or only the validation channel, so that each can be studied on its own (Section 3.6).
Nothing here assumes the combination helps. Whether a provenance-aware memory actually
contains contamination is the fourth research question, and it is left to the results to
answer.

## 3.6 Experimental design

Every run starts from an identical state, a clean-room protocol that keeps the arms, the
experiment's named configurations, comparable. Before each run the graph is cleared and
reloaded with the pristine T-REx snapshot, the extraction pipeline is replayed with a fixed
seed and the same set of documents, and only then does the contamination run begin. Because
this starting point is the same every time, two runs differ only in the things the
experiment means to change: their configuration file and, within a repeated run, the random
seed that places the errors.

![Figure 3.3: The experiment pipeline. Every run starts from the clean room, injects the index cases, runs a fixed number of steps in which agents retrieve, synthesise, and write facts back (and, in arms with validation enabled, audit and quarantine), and then measures the outcome.](docs/figures/fig_pipeline.png)

[TBL]Table 3.4: The experiment arms. Floor is the retrieval confidence threshold; Audits is the validation sampling per step; Prop. is write-time confidence propagation.

| Arm | Floor | Audits | Prop. | Purpose |
|---|---|---|---|---|
| baseline | off | off | off | unmitigated spread |
| ablation_floor | 0.5 | off | on | the retrieval floor alone |
| ablation_validation | off | 25/step | off | the validation channel alone |
| mitigated | 0.5 | 25/step | on | the full Trio combination |
| control_random | off | off | off | baseline with random error placement (RQ1 control) |
| oracle | 0.5 | 25/step, ground truth | on | full Trio with a perfect judge (RQ4 upper bound) |
| mitigated_tuned | 0.5 | 25/step, tuned prompt | on | full Trio with a prompt-tuned judge |

Two of these arms need a word of explanation. The oracle arm replaces the validator's
judgement with the experiment's own ground-truth labels, while leaving everything else about
validation the same. It shows the best the architecture could do with a perfect judge, and
by design it cannot exist outside the laboratory, because a real system has no ground-truth
channel to consult. The tuned arm changes only the judge's instructions, keeping the model,
the response format, and the thresholds fixed; its prompt was chosen beforehand on a set of
hand-labelled examples. Together the two arms bracket the validator: the oracle shows the
ceiling, the tuned arm a realistic middle.

Beyond these core arms, several sweeps vary one factor at a time to answer the third and
fourth research questions: how often the memory is checked, how far the index cases (the
injected errors) sit from the region agents retrieve, and how accurate the validator is.
Each sweep is described where its results appear in Chapter 5.

The baseline and the full mitigated arm were each run across four random seeds, 42 to 45:
the baseline to fix how much results vary from seed to seed, the mitigated arm to test
whether its result holds across seeds. A single-run difference smaller than about twice the
baseline's standard deviation is treated as within that seed-to-seed noise and is hedged
accordingly. The random-placement control is a single seed by design, because its effect is
forced by the setup rather than being a statistical average, and this is noted as a
limitation rather than repeated.

Two controls keep the numbers comparable and stable. The questions used to measure task
quality are drawn with a fixed seed of their own, separate from the seed that places the
errors, so task scores can be compared across runs; the contamination probes (the direct
checks of the injected facts, described in Section 3.7) use the run's seed. And every call to
a language model goes through a shared client that caches results and waits and retries when
a rate limit is hit, so a rate-limited run takes longer in wall-clock time but produces the
same result. No completed run lost a call this way.

## 3.7 Evaluation metrics

The system is measured on two fronts at once, and keeping them apart is central to the
analysis. One front is task quality: whether the system still answers questions well. The
other is contamination: how much of the memory is corrupted, how far the corruption has
spread, and whether it can be detected. Table 3.5 lists the metrics under each front.

[TBL]Table 3.5: The evaluation metrics.

| Metric | What it measures | How |
|---|---|---|
| Exact Match and F1 | task quality | HotpotQA answers against the ground truth (Exact Match is the share answered exactly right; F1 is a word-overlap score), at steps 0, 5, and 10, on a fixed set of 50 questions |
| Veracity Accuracy | task quality | FEVER claim classification: the share of claims labelled correctly against the ground truth |
| Probe contamination rate | persistence of an error | direct questions about the injected facts: the share whose answer gives the corrupted version |
| Propagated and exposed counts | spread | from the lineage bookkeeping: propagated is new facts whose value reproduces an injected error; exposed is new facts written while at least one fact in their lineage was already contaminated (propagated is a subset of exposed) |
| Detection AUROC | detectability | how well a fact's own confidence score, read as a suspicion signal, separates contaminated facts from clean ones (AUROC is the area under the ROC curve) |
| Quarantine precision | mitigation quality | the share of quarantined facts that were truly contaminated |
| R₀ and effective reproduction | contagion velocity | the fitted rates from Section 3.4, plus the model-free per-seed count |

The probe contamination rate and the task metrics answer different questions, and this
thesis leans on the difference. A probe asks the system directly about a fact that was
injected and checks whether it now gives the corrupted answer, so it measures whether the
error persists and is believed. The task metrics measure whether the overall workload still
produces good answers. A memory can be badly contaminated on the probes while the task
scores barely move, and Chapter 5 shows this happening. Reporting only task metrics would
hide the contamination; reporting only probes would overstate the harm.

One more answer-side metric is included, the unsupported sentence ratio. It measures how
much of an answer can be traced back to a trustworthy fact in the memory. An answer sentence
counts as supported if its content overlaps, by a plain word match, with a retrieved fact;
the unsupported sentence ratio is the share of substantive answer sentences (those making a
factual claim, not filler or a bare yes or no) that no retrieved fact supports, with
abstentions such as "unknown" set aside. This check uses no language-model judge, on
purpose, because the judges are themselves under study and a metric that must stay
trustworthy cannot depend on them. It has one honest limit, stated here and returned to in
Chapter 5: word overlap measures grounding, not truth. A faithful repeat of a retrieved but
contaminated fact counts as supported, because it is indeed grounded in the memory, even
though the memory is wrong.

## 3.8 Validity instrumentation

Most of the headline numbers depend, somewhere, on a language model's judgement: the
validator judges facts, and a judge estimates the natural error rate. So the pipeline's own
error processes are measured with three instruments, each checking a different blind spot.

The first is a natural contamination audit. Separate from the injected errors, every fact
the ExtractionAgent wrote during a run, 783 of them, is checked against the passage it came
from. The check is done by a judge built from the same model as the validator, using the
three error types as its labels. The audit answers two questions. It estimates how often the
models make these errors on their own, with nothing injected, which bears on the first
research question. And it checks whether the injected error types resemble the ones that
arise naturally, which bears on how realistic the injection is for the second.

The second instrument calibrates that audit against a human. A sample of 40 audited facts,
balanced between those the judge accepted and those it flagged and including every relation
flag, was labelled by hand against the source passages, without the labeller seeing the
judge's verdict. These human labels are the ground truth for how accurate the judge is, and
they are used to correct the audit's own rates. This step matters because an uncalibrated
judge can badly misstate the natural error rate, and Chapter 5 gives the size of the gap.

The third instrument measures a channel the audit cannot see. The audit checks whether a
fact was extracted faithfully from its source, but a fact can be faithfully extracted and
still be false in the world, and the audit would call it fine. The FEVER dataset carries a
ground-truth verdict for each of its claims: supported, refuted, or not enough information.
Mapping every FEVER-derived fact to its claim's verdict gives an exact, judge-free count of
how much false or unverifiable content enters the memory through this channel.

Taken together, these three instruments form a layered check. A language-model audit is
calibrated by a human, and both are backed by a ground-truth channel the audit cannot reach
on its own. The design is itself a small methodological contribution, because it shows, and
Chapter 5 confirms, that an uncalibrated language-model measurement of contamination can be
badly wrong. That is why the natural error rate reported later is the calibrated figure, not
the judge's raw count.

## 3.9 Assumptions, scope, and threats to validity

Every experimental design rests on choices that bound what its results can claim. This
section states the main assumptions behind the method, marks what falls inside and outside
its scope, and lists the threats to the validity of its conclusions, together with the steps
taken to limit each one.

The contamination studied here is non-adversarial. Errors enter because a model misreads
text, not because an attacker plants them, which sets this work apart from data-poisoning
attacks on retrieval systems, where a hostile party crafts inputs to force a chosen output
[16]. Assuming no attacker is the harder case to argue, because it shows that spread needs
no malice, only ordinary model error and a shared memory. It is also a limit: the results
say nothing about how the system behaves under deliberate attack, and a validator tuned for
honest mistakes may well fail against crafted ones.

The central metric, R₀, is borrowed from epidemiology and applied to facts rather than
people. This is an analogy, and it holds only as far as the mapping in Section 3.4 holds,
where a fact is either able to spread, already caught, or not yet reached, with no state in
between. Where the analogy strains, the number should be read as a summary of spread within
these runs, not as a fixed natural constant. Two of the answer-quality checks, Exact Match
and FEVER accuracy, move very little at the contamination levels reached here (Chapter 5),
so their flatness is expected and is not read as evidence that contamination is harmless.
The unsupported sentence ratio of Section 3.7 measures support, not truth, so a faithful
reuse of a contaminated fact counts as supported and the analysis treats it that way.

The main threat to internal validity, meaning whether the effect seen is really caused by
what was changed, is the language model's own randomness. A run's seed fixes where errors
are injected, but it does not fix what the models generate, so two runs with the same seed
still differ, and a small gap between single runs is read as noise, not as an effect. To
keep the measuring instrument steady, the judge model used for validation and auditing is
held fixed for the whole study, since changing it partway would confound a change in the
system with a change in the ruler. Because a full run is expensive on the hardware
available, most comparisons rest on the four seeds described in Section 3.6, so differences
in variance are reported as suggestive rather than settled, and every single-seed figure is
labelled as such.

Small samples are handled conservatively. A comparison between two groups reports both a
Welch t-test, which does not assume the groups have equal spread, and a Mann-Whitney U test,
which does not assume the values follow a normal distribution, and a difference is called
real only when both agree. Comparisons of counts in categories use Fisher's exact test,
which checks whether a split of counts across categories is more lopsided than chance alone
would give. Together with the noise rule of Section 3.6, these choices trade some ability to
detect small effects for caution, which suits a study where claiming an effect that is not
there would be worse than missing one.

The findings are bounded by the setup that produced them. Two open models are used, one for
extraction and one for judgement, both small enough to run on a single machine with no
graphics card, so behaviour on larger or commercial models may differ. The pre-loaded facts
are drawn from the long tail of a public knowledge base, entities the models are unlikely to
have memorised, which is the fair setting for studying extraction but may understate how
well a model resists an error about a famous entity it already knows well. The graph is kept
in one database engine and queried in one way, and the three datasets, though varied, do not
cover every kind of question. Where a result is expected to depend on these choices, and
where it is expected to survive them, the analysis says so plainly.

Finally, the study is built to be repeatable. Every run follows the same three-stage
procedure, loading a fresh graph, extracting into it, then injecting errors and letting them
spread, so that no state leaks from one run into the next. Seeds, configurations, and
per-run outputs are written to files, and the numbers reported in Chapter 5 are read back
from those files, not recalled from notes. This does not remove the model randomness
described above, but it makes every reported figure traceable to an archived run.
