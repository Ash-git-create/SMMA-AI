# Chapter 2 — Literature Review

> **Draft status (2026-07-24):** first full draft, written after Chapters 3–5
> were substantially drafted so that the review can be positioned precisely
> against what the thesis actually measures, rather than against a
> pre-registered guess at the results. All citations below were checked
> against a live search result (title, author list, venue/year) before being
> used; none are reconstructed from memory. Items that could not be pinned to
> a verifiable source are marked `[UNVERIFIED-CHECK]` rather than included as
> fact. Passages needing Ashwin's judgment are marked `[REVIEW]`.

## 2.0 Overview

This thesis sits at the intersection of four literatures that have, so far,
developed mostly independently: multi-agent LLM system design, adversarial
memory/RAG security, epidemiological modelling of diffusion processes, and
provenance-aware database theory. Sections 2.1–2.7 survey each in turn.
Section 2.8 draws the threads together into an explicit gap statement and a
comparison table, which is the argument the rest of the thesis is built to
support: that non-adversarial, retrieval-mediated error propagation in
shared-memory multi-agent systems is measurable with epidemiological tools,
that a Trio-style provenance mitigation is testable rather than merely
plausible, and that neither claim has been made with an empirical system
before.

## 2.1 Shared-memory multi-agent LLM systems

Coordinating multiple LLM-driven agents through a persistent, commonly
accessible store rather than through point-to-point messages is not a new
idea in software architecture — it is a direct descendant of the
**blackboard architecture** [Hayes-Roth, 1985], in which independent
"knowledge sources" read and write to a shared workspace and a separate
control component decides which source acts next. What has changed is the
knowledge source: where classical blackboard systems used hand-written
inference rules, current systems use LLM calls, and the blackboard has
become a vector store, a document, or — as in this thesis — a property
graph.

Recent surveys of LLM-agent memory converge on the same taxonomy the field
independently arrived at three decades earlier: per-agent local memory,
centralized shared memory (blackboard-style), and hybrid designs combining
private working memory with a shared, summarized world state [Luo et al.,
2026]. A companion survey frames the open engineering questions this
introduces once the knowledge sources are LLMs rather than rule engines —
whether access to another agent's memory is read-only or read-write, what
the unit of access is, and how consistency is maintained under concurrent
writes [Luo et al., 2026]. These are infrastructure questions. Neither
survey, nor the broader literature they summarize, treats the *epistemic*
question this thesis is built around: what happens to the shared store's
factual content, specifically, as ordinary agents write to it repeatedly.

A recurring observation across this literature, stated as an aside rather
than studied directly, is that shared memory concentrates risk: "one
compromised agent's erroneous output can propagate through shared memory
stores, internal messages, and tool parameters to infect other agents"
[synthesized from multi-agent memory security surveys, Section 2.2]. The
word "compromised" is doing a lot of work in that sentence — it presumes an
adversary. Section 2.2 examines the literature that studies this
propagation channel and shows that it is uniformly adversary-framed; Section
2.3 examines the (much smaller, mostly 2026) literature that studies
*error* propagation without an attacker, which is closer to this thesis but
still does not instrument a shared knowledge graph with ground-truth
provenance the way Chapter 4 does.

`[REVIEW]` The blackboard-architecture framing in §3.1 of this thesis
("agents coordinating through a persistent store rather than through direct
message passing") is a direct methodological callback to Hayes-Roth; Ashwin
may want to make that lineage more explicit in Chapter 3 as well, not only
here.

## 2.2 Adversarial memory and knowledge-base poisoning

The literature on deliberately corrupting an LLM system's external memory
is comparatively mature and growing quickly, but it is uniformly framed
around an attacker with intent.

**Retrieval poisoning.** PoisonedRAG [Zou et al., 2024/2025] formalizes the
attack as an optimization problem: given a target question and a
target (wrong) answer, find a small number of texts that, once injected
into the retrieval corpus, make the LLM produce the target answer with high
probability — achieving a 90% attack success rate with as few as five
injected texts against a corpus of millions. The attack is explicit about
its threat model: an adversary with corpus-write access and a chosen
target. This is architecturally the closest prior work to the mechanism
this thesis studies (a corrupted fact enters a retrieval store and is later
served as context) but differs on the axis the thesis is built to isolate:
PoisonedRAG's corruption is optimized and targeted; this thesis's is
incidental, produced by the same extraction pipeline that also writes the
correct 99%+ of triplets (Chapter 5, §5.7).

**Agent memory poisoning.** A newer strand targets persistent agent memory
specifically, rather than a static retrieval corpus. MINJA [Dong et al.,
2025/2026, NeurIPS 2025] shows that an attacker who only ever issues
queries — no direct memory-store access — can implant malicious records
that later hijack a *different* victim user's session, at a 98.2% injection
success rate, via a "bridging steps" technique that make the injected
content look like organic reasoning trace. Two 2026 surveys map this attack
family systematically: one organizes the whole agent stack into seven
attack-surface layers (Foundation through Governance) and explicitly names
Memory as one of them, noting that "in shared-memory deployments a
compromised agent can write adversarial entries into memory banks accessed
by peers, turning a single compromise into a multi-agent contamination
vector" [Chu, 2026]; the other proposes a "Memory Lifecycle Framework"
spanning six phases and argues that memory security "cannot be retrofitted
at retrieval or execution time alone, but must be anchored in storage-time
provenance, versioning, and policy-aware retention" [Lin et al., 2026] —
independently arriving at essentially the design principle this thesis
tests empirically as the Trio arm (Chapter 3, §3.5), but as an architectural
recommendation rather than a measured result.

**The gap.** Every source in this section studies contamination that
requires an adversary: a party who chooses what false content to inject,
where, and to what end. None of them ask what happens when *no one is
trying to break the system* — when the "attacker" is an off-the-shelf 12B
extraction model making its ordinary error rate of entity confusions,
dropped qualifiers, and over-confident relation upgrades. This is precisely
the gap the thesis's non-adversarial framing (Chapter 1; error taxonomy in
Chapter 3, §3.3) targets. It matters practically, not just conceptually:
Chapter 5's natural-contamination audit (§5.7) finds a genuine, unforced
error rate of roughly 1% of extraction-written triplets even with no
injected errors at all — a base rate the adversarial literature has no
mechanism to produce or measure, because its threat model starts from an
adversary who already wants the error to exist.

`[REVIEW]` The memory-security surveys cited here (Chu 2026; Lin et al.
2026) are single- or few-author arXiv preprints from within the last few
months, not yet peer-reviewed at the time of writing. They are cited for
their taxonomy and stated design principles, not as established empirical
results — flagged so this isn't read as more settled than it is.

## 2.3 Error propagation and cascades in AI pipelines

A distinct, newer strand studies error propagation in multi-agent LLM
systems *without* an adversary — closer in spirit to this thesis, though
none of it instruments a persistent shared knowledge store with
ground-truth provenance the way Chapter 4 does.

"Hallucination Cascade" [Jamshidi et al., 2026] tracks factual
inconsistencies as they move through sequential agent chains (GPT-class,
DeepSeek-V3, LLaMA-3-70B), decomposing responses into atomic claims and
scoring them with a mix of rule-based grounding and LLM-based semantic
validation across 500 cascade runs in 10 domains. Its central finding is
counter-intuitive on its face: a normalized hallucination score *falls*
from 0.422 at the first agent to 0.272 by the third in a 3-agent chain —
later agents partially soften or reframe earlier errors even as they also
sometimes amplify or transform them. The authors read this as a trade-off
between fluency-driven correction and factual accuracy, not as evidence
that cascades are self-healing. "From Spark to Fire" [Xie et al., 2026]
takes a more architectural angle: minor per-agent errors "gradually
solidify into system-level false consensus through iteration," and the
authors propose a *propagation dynamics model* to classify vulnerability
types, then a message-layer governance intervention that suppresses final
"infection" in at least 89% of runs without touching the underlying
collaboration architecture. The infection/consensus vocabulary here
anticipates the epidemiological framing this thesis makes explicit and
quantitative (Section 2.4) — but "From Spark to Fire" studies transient
consensus within a single reasoning episode (agents converging on a wrong
answer together), not persistent contamination written into a store that
outlives the episode and is retrieved by unrelated future tasks, which is
the object Chapter 3's SIR formulation measures.

A structurally adjacent phenomenon, studied on a different axis (training
rather than inference-time memory), is **model collapse**: when a model is
trained recursively on its own or another model's synthetic output, "tails
of the original content distribution disappear" and successive generations
converge toward a low-variance point estimate that cannot be recovered by
further training on human data [Shumailov et al., 2023]. The mechanism is
not the one this thesis studies — there is no retrieval-and-belief step,
and the corrupted signal is statistical drift in a training distribution
rather than a discrete false fact in a graph — but the *diagnosis* is the
same shape: an ordinary, non-adversarial process (training on the
ecosystem's own recent output) that degrades a shared resource through
repeated reuse, with no attacker required. A 2026 preprint makes the
kinship explicit by modelling model collapse itself with a two-population
SIR-type system (Section 2.4).

**Assessment.** This is the thinnest area directly relevant to the thesis's
central mechanism. The two 2026 multi-agent papers above study *transient*
error propagation within a single collaborative episode, evaluated by an
LLM-based semantic judge over 3–10 step chains; neither instruments a
persistent, externally queryable shared memory with ground-truth
provenance, and neither applies a formal epidemic model to fit transmission
and recovery rates from the resulting trajectories. That combination —
persistent store, ground-truth injected error taxonomy, and a fitted
SIR/R₀ model — is the specific contribution Chapters 3–5 make.

## 2.4 Epidemiological models of information spread

Applying compartment models from mathematical epidemiology to the spread of
*information* rather than disease has a long history, predating
LLM-based systems by six decades. Two lineages matter here.

The first is the direct descendant of Kermack and McKendrick's
[1927] original SIR compartment model, whose central result — a threshold
population density below which no epidemic can take hold — is the
conceptual ancestor of the R₀ = 1 containment threshold this thesis reports
against throughout Chapter 5. The second, purpose-built for information
rather than disease, is the Daley–Kendall rumour model [Daley & Kendall,
1964], which replaces Susceptible/Infected/Recovered with
Ignorant/Spreader/Stifler and changes the *transition rule*: unlike disease
transmission, a spreader who meets another spreader (rather than becoming
infected further) becomes a stifler — the interaction that ends rumour
transmission is spreader-to-spreader contact "wearing out" the rumour's
novelty, not a recovery process external to the transmission dynamic
itself. This is a substantive fork in the modelling tradition: SIR-style
models assume an independent recovery process (this thesis's γ, the
ValidationAgent's audit rate — an external intervention, exactly SIR's
structure, not Daley–Kendall's endogenous stifling), while
Daley–Kendall-style models assume the population stifles itself through
saturation.

Modern applications to *digital* misinformation mostly extend SIR rather
than Daley–Kendall, adding states for psychological or platform-specific
dynamics: one 2024 model adds a "Doubt" and a "Restrained" compartment atop
the conventional infected state to capture rumour sentiment and correction
behaviour on social platforms [Govindankutty & Gopalan, 2024]. This
confirms the base SIR machinery transfers to information-spread contexts
with only moderate adaptation — useful precedent for this thesis's own
adaptation (KG nodes as individuals, retrieval as contact, extraction
confidence as susceptibility) — but the object being modelled is still
human belief propagating through a social network, not machine-written
facts propagating through a queryable knowledge store.

The closest work found to this thesis's actual mechanism is a 2026
preprint that models **model collapse** — not multi-agent memory
contamination — with a bilayer, two-population SIR/SIRS system coupling a
data-corpus layer and a model layer, each with its own S/I/R (or S/I/R/S,
allowing waning immunity) compartments, cross-contaminating through
retraining cycles [Wang, 2026]. This is the only source located that
applies a fitted compartment model, with an explicit R₀-style vocabulary,
to an AI-ecosystem contamination process rather than to human social
networks. It targets a different layer of the stack (training-data
corpora across a model ecosystem, mean-field / phenomenological, not fit
against measured per-node trajectories from a running system) and a
different phenomenon (statistical drift from synthetic-data reuse, not
discrete false triplets written by an extraction pipeline and validated —
or not — by a downstream audit agent). No source located applies a fitted,
empirically-grounded SIR model with a measured β (retrieval-driven
transmission) and γ (validation-driven recovery) to node-level
contamination inside a live, running multi-agent knowledge-graph pipeline,
which is precisely Chapter 3 §3.4's construction and Chapter 5 §5.5's
fitting exercise.

`[REVIEW]` A brief search for peer-reviewed, non-preprint applications of
epidemic models to *any* AI-system failure-propagation phenomenon (not just
misinformation-on-social-media) came back essentially empty outside the two
2026 preprints above — this looks like a genuinely new intersection rather
than a gap in the search, but it's worth a second pass before the thesis
claims priority outright.

## 2.5 Provenance and uncertainty-lineage databases

The mitigation this thesis tests (Chapter 3, §3.5; Chapter 4, §4.2.2) is an
explicit adaptation of the **Trio** project, Stanford's system for managing
data together with its uncertainty and lineage as first-class properties
[Widom, 2005]. Trio's data model — the **ULDB** (Uncertainty-Lineage
Database) — extends the relational model so that every tuple is an
*x-tuple*: a set of possible values, each carrying a confidence and a
lineage formula recording which base tuples it was derived from
[Benjelloun et al., 2008]. The system paper demonstrates the model with a
working prototype and its query language, TriQL, an SQL extension with
constructs for querying confidence and lineage directly [Agrawal et al.,
2006]. This thesis's provenance schema (Chapter 4, §4.2.2 — value,
confidence, and a DNF lineage formula over ancestor triplet ids, with
materialized `DERIVED_FROM` edges enabling transitive traversal) is a
direct, named implementation of the x-tuple concept, adapted from
relational tuples to knowledge-graph triplets and from a static database to
a live multi-agent write path.

A closely related, more general theory is the **provenance semiring**
framework [Green, Karvounarakis, & Tannen, 2007], which shows that
confidence computation, why-provenance, and several other
previously-separate notions of "where did this answer come from" are all
instances of evaluating a query over a semiring of annotated facts and
propagating the annotations algebraically through the query. This thesis's
confidence-propagation mechanism (Chapter 3, §3.5 item 3: a derived
triplet's confidence computed from its parents' confidences by
"arithmetization of the lineage formula") is the semiring-provenance
technique applied to a specific case — a conjunctive lineage formula and a
confidence semiring — rather than a novel derivation; Chapter 4, §4.2.2
notes candidly that the disjunctive/noisy-or arithmetization is implemented
but never exercised by the actual write path, since the pipeline only ever
produces conjunctive ("derived from all of these") lineage.

**What this literature does not do.** Trio and provenance semirings are
database theory: they specify *how* to represent and compute over
uncertainty and lineage, not what happens when the mechanism is deployed
in front of agents whose *judgement* about what to quarantine is itself
unreliable. Neither literature has an analogue of this thesis's central
empirical finding (Chapter 5, §5.4.1–§5.4.3): that a syntactically correct
provenance-and-cascade-deprecation mechanism, fed a low-precision judge,
does not merely fail to help — it launders confidence (quarantine removes
mostly-clean nodes, leaving contaminated survivors in a cleaner-looking
population) and amplifies outcome variance roughly tenfold. The database
literature's implicit assumption is that lineage and confidence are
computed faithfully once and queried; this thesis's setting has confidence
being *re-estimated* repeatedly by a fallible LLM judge, which is a
different failure mode than anything ULDB theory anticipates.

## 2.6 Knowledge-graph quality and error detection

The standard reference for identifying and correcting errors in a
knowledge graph is Paulheim's survey of **KG refinement**, which frames the
whole field around two complementary goals — *completion* (adding missing
facts) and *error detection* (removing or flagging wrong ones) — and
catalogues the approaches and evaluation protocols used for each
[Paulheim, 2017]. Concretely, error-detection methods in this tradition are
almost uniformly *post-hoc and static*: they take a KG as a fixed input and
score its existing triples for plausibility, typically via embedding-based
methods. A representative recent example, TripleNet, builds a graph over
triples themselves (connected via shared entities) and combines local and
global triple representations to flag likely-noisy triples [Liu, Zhang,
Du, Huang, & Hu, 2023].

This body of work targets a different problem than the one Chapter 5
measures. Static KG error detection asks "is this triple, as stored,
statistically consistent with the rest of the graph?" — a question that can
be answered without knowing *who wrote the triple, when, or from what
evidence*. This thesis's ValidationAgent instead has to answer "was this
triple faithfully derived from what was retrieved?", using exactly the
provenance the pipeline attaches at write time (Chapter 3, §3.2). The two
questions turn out to diverge sharply for the error type that matters most
here: Chapter 5, §5.4.3 finds that a KG produced by *replacement*
contamination (a corrupted fact overwrites, rather than coexists with, the
true one) leaves *no statistical or evidentiary trace* for a
consistency-style or evidence-quoting detector to find, because there is no
contradicting assertion left anywhere in the graph to be inconsistent
with. Embedding-based static detectors, which rely on exactly this kind of
structural inconsistency signal (a triple that doesn't fit the pattern of
its neighbours), would be expected to face the same blind spot for
replacement-type errors, though this thesis did not run one against its KG
to confirm it directly — noted here as an untested but literature-motivated
prediction.

`[REVIEW]` Testing whether an off-the-shelf embedding-based KG error
detector (e.g., TripleNet-style) also fails on this thesis's
replacement-contamination cases would be a clean, cheap robustness check
for the "structural blindness" finding (Chapter 5, §5.4.3) if time in Phase
4/5 allows — it would show the blindness is a property of the contamination
mechanism, not an artifact of using an LLM judge specifically.

## 2.7 LLM-as-judge reliability

This thesis's ValidationAgent, and the calibration study built around it
(Chapter 3, §3.8; Chapter 5, §5.6), are an instance of the broader
**LLM-as-a-judge** paradigm: using one LLM to evaluate another's output (or,
here, to evaluate the fidelity of a stored triple) in place of exhaustive
human annotation. The paradigm's foundational study introduces MT-Bench and
Chatbot Arena specifically to check whether strong LLM judges agree with
human preference judgments, and reports that frontier judges reach roughly
80%+ agreement with humans on open-ended chat quality — while explicitly
cataloguing the biases that limit this: position bias (favouring
whichever answer is shown first), verbosity bias (favouring longer
answers regardless of quality), and self-enhancement bias (a judge
favouring text generated by its own model family) [Zheng et al., 2023].

Two things are worth flagging about how this literature's headline numbers
translate to this thesis's setting. First, the 80%+ agreement figures are
overwhelmingly measured on *preference* judgments (which of two responses
is better) rather than *binary fidelity* judgments against a specific
source (is this triple faithfully derived from this passage/evidence) —
the task types are not interchangeable, and preference-agreement rates give
no direct estimate of fidelity-judgment precision. Second, and more
consequentially for Chapter 5's findings: the LLM-as-judge literature
generally reports *agreement* or *accuracy* as a single aggregate number,
without decomposing it into precision and recall against a specific,
minority-class positive condition — which is exactly the decomposition
Chapter 5 needed once the ValidationAgent's flags turned out to be right
only 10% of the time (§5.6) while its downstream quarantine decisions
inherited the same low precision (§5.4.1, pooled 5.9%). The thesis's
own methodological layering — an LLM audit, a human-labelled calibration
sample used to correct the audit's aggregate rate, and (where available) an
independent ground-truth channel the audit cannot see (Chapter 3, §3.8) —
is one answer to a gap the broader LLM-judge literature leaves open: most
judge-reliability studies validate a judge once, in general, rather than
per-deployment, against the specific low-base-rate condition (here, ~1–12%
depending on channel; Chapter 5, §5.7) the judge will actually be asked to
detect. Base-rate sensitivity of this kind is a known statistical hazard
(a 10%-precision judge at a 1% true base rate is a very different
instrument than the same judge at a 50% base rate) that this thesis's
calibration design addresses empirically rather than assumes away, but
which the general LLM-judge literature surveyed here does not foreground.

`[REVIEW]` A more exhaustive pass specifically on precision/recall-style
(rather than agreement-style) LLM-judge evaluations, and on any existing
work about judges as *contamination or anomaly detectors* specifically
(rather than as quality/preference scorers), would be worth another search
pass if this section needs to carry more weight — it currently rests on one
foundational paper plus the thesis's own findings, which is thin for a
whole subsection.

## 2.8 Synthesis: the gap this thesis fills

Table 2.1 makes the positioning explicit. "Adversarial?" asks whether the
work assumes an attacker choosing what to corrupt. "Shared memory?" asks
whether contamination is studied as it moves through a persistent store
accessed by multiple independent agents (as opposed to within one episode,
one model, or one training run). "Epidemiological quantification?" asks
whether the work fits a compartment model (or equivalent — R₀, transmission
and recovery rates) to the propagation dynamics, rather than only reporting
attack success rate or aggregate degradation. "Provenance mitigation
(tested)?" asks whether a lineage/provenance-aware defence is empirically
run and measured, not just proposed. "Empirical (real system)?" asks
whether the claims come from a running pipeline rather than a simulation,
theoretical model, or offline benchmark alone.

**Table 2.1 — Positioning against related work**

| Work | Adversarial? | Shared memory? | Epidemiological quantification? | Provenance mitigation (tested)? | Empirical (real system)? |
|---|---|---|---|---|---|
| PoisonedRAG [Zou et al., 2024/2025] | Yes | Partial (static retrieval corpus) | No | No | Yes |
| MINJA [Dong et al., 2025/2026] | Yes | Yes (agent memory bank) | No | No | Yes |
| Memory-security surveys [Chu, 2026; Lin et al., 2026] | Yes (surveyed attacks) | Yes | No | Proposed, not tested | No (survey) |
| Hallucination Cascade [Jamshidi et al., 2026] | No | No (single episode, transient) | No | No | Yes |
| From Spark to Fire [Xie et al., 2026] | No | No (single episode) | Partial (propagation dynamics model, not SIR) | Partial (message-layer governance, not lineage-based) | Yes |
| Curse of Recursion [Shumailov et al., 2023] | No | No (training data, not agent memory) | No | No | Yes (simulation) |
| Epidemiology of Model Collapse [Wang, 2026] | No | No (model/corpus ecosystem, not agent KG) | Yes (bilayer SIR) | No | No (phenomenological model) |
| Trio / ULDB [Widom, 2005; Benjelloun et al., 2008] | N/A (database theory) | N/A | No | Yes (mechanism defined) | Yes (prototype DBMS) |
| KG refinement / error detection [Paulheim, 2017; Liu et al., 2023] | No | No (static graph) | No | No | Yes |
| **This thesis** | **No** | **Yes** | **Yes (fitted SIR, R₀)** | **Yes (Trio-inspired, ablated)** | **Yes** |

No located work combines all five columns. The nearest neighbours each
share exactly one or two: MINJA and the memory-poisoning literature share
the shared-memory setting but require an adversary by construction; "From
Spark to Fire" studies non-adversarial propagation but not in a persistent
store, and its "propagation dynamics model" is not a fitted epidemic model
with a reported R₀; the Trio/ULDB literature supplies the mitigation
mechanism this thesis tests but never tests it against a fallible judge in
a live pipeline; and the bilayer-SIR model-collapse preprint is the only
other source to apply epidemic quantification to AI-system contamination,
but at the training-corpus level, not to knowledge-graph nodes in an agent
pipeline, and without an empirically fitted β/γ against measured
trajectories.

**The thesis's specific contribution, restated against this table.** It is
not any one of adversary-free framing, epidemiological quantification, or
Trio-style provenance mitigation in isolation — each has a partial
precedent above. It is running all three together against a real
multi-agent pipeline, which forces empirical questions none of the partial
precedents had to answer: what R₀ actually comes out when β and γ are
fitted to a running system rather than assumed (Chapter 5, §5.5); whether a
provenance mechanism that is theoretically sound (Section 2.5) survives
contact with a judge whose precision is empirically ~6–10%, rather than
the perfect oracle implicit in the database-theory literature (Chapter 5,
§5.4.1–§5.4.2); and whether error detection built on internal
self-consistency — the dominant strategy in both the KG-refinement
literature (Section 2.6) and, implicitly, in the ValidationAgent's own
design — has a structural blind spot for the specific contamination
mechanism (replacement, not addition) that this thesis's error taxonomy
turns out to produce (Chapter 5, §5.4.3). None of the surveyed literature
poses that last question, because none of it is built around a
*replacement*-based, non-adversarial error model in the first place — most
adversarial memory-poisoning work injects *additional* malicious content
rather than silently overwriting the correct fact in place, which is
exactly why it does not anticipate the detection asymmetry Chapter 5
reports.

---

## References

Agrawal, P., Benjelloun, O., Das Sarma, A., Hayworth, C., Nabar, S.,
Sugihara, T., & Widom, J. (2006). Trio: A System for Data, Uncertainty, and
Lineage. *Proceedings of the 32nd International Conference on Very Large
Data Bases (VLDB 2006)*, Seoul, Korea.
https://www.vldb.org/conf/2006/p1151-agrawal.pdf

Benjelloun, O., Das Sarma, A., Halevy, A., Theobald, M., & Widom, J.
(2008). Databases with uncertainty and lineage. *The VLDB Journal*, 17(2),
243–264. https://link.springer.com/article/10.1007/s00778-007-0080-z

Chu, K. (2026). A Systematic Survey of Security Threats and Defenses in
LLM-Based AI Agents: A Layered Attack Surface Framework. arXiv:2604.23338.
https://arxiv.org/abs/2604.23338

Daley, D. J., & Kendall, D. G. (1964). Epidemics and Rumours. *Nature*,
204, 1118. https://www.nature.com/articles/2041118a0

Dong, S., Xu, S., He, P., Li, Y., Tang, J., Liu, T., Liu, H., & Xiang, Z.
(2025/2026). Memory Injection Attacks on LLM Agents via Query-Only
Interaction. *NeurIPS 2025*; arXiv:2503.03704.
https://arxiv.org/abs/2503.03704

Govindankutty, S., & Gopalan, S. P. (2024). Epidemic modeling for
misinformation spread in digital networks through a social intelligence
approach. *Scientific Reports*, 14.
https://www.nature.com/articles/s41598-024-69657-0

Green, T. J., Karvounarakis, G., & Tannen, V. (2007). Provenance Semirings.
*Proceedings of the 26th ACM SIGMOD-SIGACT-SIGART Symposium on Principles
of Database Systems (PODS 2007)*, Beijing, China.
https://web.cs.ucdavis.edu/~green/papers/pods07.pdf

Hayes-Roth, B. (1985). A blackboard architecture for control. *Artificial
Intelligence*, 26(3), 251–321.
https://doi.org/10.1016/0004-3702(85)90063-3

Jamshidi, S., Dakhel, A. M., Nafi, K. W., & Khomh, F. (2026). Hallucination
Cascade: Analyzing Error Propagation in Multi-Agent LLM Systems.
arXiv:2606.07937. https://arxiv.org/abs/2606.07937

Kermack, W. O., & McKendrick, A. G. (1927). A Contribution to the
Mathematical Theory of Epidemics. *Proceedings of the Royal Society of
London, Series A*, 115(772), 700–721.
https://royalsocietypublishing.org/rspa/article/115/772/700/2165

Lin, Z., Hao, X., Fu, R., Cui, S., Chen, K., Li, C., Li, Z., & Xiong, F.
(2026). A Survey on Long-Term Memory Security in LLM Agents: Attacks,
Defenses, and Governance Across the Memory Lifecycle. arXiv:2604.16548.
https://arxiv.org/abs/2604.16548

Liu, Y., Zhang, Q., Du, M., Huang, X., & Hu, X. (2023). Error Detection on
Knowledge Graphs with Triple Embedding. *31st European Signal Processing
Conference (EUSIPCO 2023)*. IEEE. https://ieeexplore.ieee.org/document/10289852/

Luo, J., Tian, Y., Cao, C., Luo, Z., Lin, H., Li, K., Kong, C., Yang, R., &
Ma, J. (2026). A Survey on the Evolution of LLM Agent Memory.
arXiv:2605.06716. https://arxiv.org/abs/2605.06716

Paulheim, H. (2017). Knowledge graph refinement: A survey of approaches and
evaluation methods. *Semantic Web*, 8(3), 489–508.
https://doi.org/10.3233/SW-160218

Shumailov, I., Shumaylov, Z., Zhao, Y., Gal, Y., Papernot, N., & Anderson,
R. (2023). The Curse of Recursion: Training on Generated Data Makes Models
Forget. arXiv:2305.17493. https://arxiv.org/abs/2305.17493

Wang, X. (2026). Epidemiology of Model Collapse: Modeling Synthetic Data
Contamination via Bilayer SIR Dynamics. arXiv:2606.05168.
https://arxiv.org/abs/2606.05168

Widom, J. (2005). Trio: A System for Integrated Management of Data,
Accuracy, and Lineage. *Proceedings of the 2nd Biennial Conference on
Innovative Data Systems Research (CIDR 2005)*, Asilomar, CA.
http://ilpubs.stanford.edu:8090/843/

Xie, Y., Zhu, C., Zhang, X., Zhu, T., Ye, D., Qi, M., Chen, H., & Zhou, W.
(2026). From Spark to Fire: Modeling and Mitigating Error Cascades in
LLM-Based Multi-Agent Collaboration. arXiv:2603.04474.
https://arxiv.org/abs/2603.04474

Zheng, L., Chiang, W.-L., Sheng, Y., Zhuang, S., Wu, Z., Zhuang, Y., Lin,
Z., Li, Z., Li, D., Xing, E. P., Zhang, H., Gonzalez, J. E., & Stoica, I.
(2023). Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena. *Advances
in Neural Information Processing Systems 36 (NeurIPS 2023), Datasets and
Benchmarks Track*.
https://papers.nips.cc/paper_files/paper/2023/hash/91f18a1287b398d378ef22505bf41832-Abstract-Datasets_and_Benchmarks.html

Zou, W., Geng, R., Wang, B., & Jia, J. (2024/2025). PoisonedRAG: Knowledge
Corruption Attacks to Retrieval-Augmented Generation of Large Language
Models. *34th USENIX Security Symposium (USENIX Security 2025)*;
arXiv:2402.07867. https://arxiv.org/abs/2402.07867
