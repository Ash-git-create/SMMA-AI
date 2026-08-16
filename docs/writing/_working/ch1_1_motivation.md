# 1.1 Motivation (working draft — revised after gates, awaiting approval)

**P1.** (revised)
A large language model, or LLM, produces text by repeatedly predicting the next word.
That is enough to answer a question or summarise a document, but the model predicts
likely text, not checked facts, and that gap is where this thesis begins. On its own
an LLM handles one task at a time. Over the last few years developers have started
wiring several of them together, giving each model a narrow role such as searching for
sources, pulling facts out of a document, or writing the final answer, and letting the
models pass work to each other to finish a larger job. A setup like this is a
multi-agent system, and each model inside it is an agent. Frameworks such as AutoGen
[1] and MetaGPT [2] made these systems easier to build.

**P2.** (revised)
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

**P3.** (unchanged — passed all gates)
That shared notebook is also the weak point. LLMs make mistakes even when nobody is
trying to trick them. They state facts that their input never supported, attach a fact
to the wrong name, or drop a detail such as a date that changes what the fact means.
This behaviour is usually called hallucination [4]. When one model works alone, a
wrong answer stays a local problem: the user reads it and moves on. In a shared-memory
system it does not stay local. Once a wrong fact is written into the graph, the next
agent that reads it has no easy way to tell it apart from a correct one, because it
came from the same trusted store. That agent can then build on the wrong fact and
write new, also wrong, facts back into the graph.

**P4.** (revised)
This is the situation the thesis studies. As more systems place several LLMs around
one shared memory, the cost of a single bad write no longer stops at one answer. It
can pass to other agents and grow. Work on LLM safety has mostly checked one model or
one output at a time, which can miss an error that only causes damage after it travels
through a shared store; Chapter 2 looks at that gap in detail. The thesis asks how far
such errors spread, what makes them spread, and whether a memory that records where
each fact came from can hold them back.

---
Gate outcomes: Style = minor fixes applied (cut uncited "spread quickly", trimmed KG
triad, hedged "most safety work"). Originality = clean on web spot-check; P1/P2
reworded off generic-definition cadence. Fact = citations [1][2][3] real but author
lists corrected; [3] rescoped to what GraphRAG actually supports; [4] cleared.
