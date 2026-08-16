# 3.1 System overview (revised after gates — corrected agent roles to match code)

**P1.**
The experimental system is a shared-memory multi-agent architecture: several agents
driven by language models read from and write to one central knowledge graph. This is
the pattern the thesis studies, chosen because the research questions concern exactly the
failure this architecture can cause. When many agents share one memory, an error written
by one of them becomes retrievable context for all the others. Figure 3.1 shows the whole
system.

**P2.**
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

**P3.**
Two different models are used, split by job. The ExtractionAgent runs the larger Mistral
Nemo 12B, which is stronger at pulling structured facts out of text, and this same model
also drives the step-by-step synthesis. The OrchestrationAgent and ValidationAgent run the
smaller and faster Llama 3.1 8B. This split, a stronger extractor and a faster judge, is
kept throughout. Section 4.1 describes how the models are hosted.

**P4.**
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

![Figure 3.1: The system architecture. The ExtractionAgent (Mistral Nemo 12B) both pulls facts from text and, in the propagation loop, synthesises new facts from retrieved ones, writing all of them into the shared Neo4j knowledge graph. The ValidationAgent (Llama 3.1 8B), using the OrchestrationAgent as its judge, audits the graph and quarantines unreliable facts. The ErrorInjector places controlled errors. Retrieval carries transmission (beta) and validation carries recovery (gamma).](docs/figures/fig_architecture.png)
