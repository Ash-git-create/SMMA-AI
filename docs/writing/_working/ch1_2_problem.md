# 1.2 Problem Statement (working draft — revised after gates, awaiting approval)

**P1.** (minor tweak)
The failure this thesis is built around has a specific shape. In a shared-memory
multi-agent system, one agent's wrong fact does not stay a single wrong answer. It gets
written into the shared graph, retrieved by other agents as if it were true, used to
derive new facts, and written back. The error reproduces and spreads. This thesis calls
that pattern cascading knowledge contamination. It needs no attacker. It runs on the
ordinary mechanics of extraction, retrieval, and reuse that make shared memory useful
in the first place.

**P2.** (revised: gloss "coupled system", reword off a matched phrase, drop the
"coin flip" genre idiom)
The reason a cascade is worth worrying about is that errors in a chain multiply rather
than add. Here is a simple illustration. If every step in a ten-step pipeline were
correct 95% of the time, and each step depended on the step before it, the whole chain
would be correct about 60% of the time, because 0.95 to the tenth power is 0.599. A
system built from reliable parts is wrong about four times in ten. The real systems
studied in this thesis are far more reliable per step than 95%, so this number
illustrates the mechanism rather than measuring the thesis. The narrow point still
holds: in a system where each step depends on the last, a per-step error rate that
looks tiny on its own stops being tiny once errors can feed each other.

**P3.** (revised: hedge the third gap to match current literature)
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

**P4.** (revised: split the overloaded sentence, cite the existence claim, tighten
the close)
So the problem this thesis takes on has two halves: to show how non-adversarial
contamination spreads through a shared-memory system, and to measure that spread in a
way a designer can use before deployment rather than only explain after the fact. This
matters because such systems are already being built with frameworks like the ones
named above [1], [2]. A design that quietly amplifies its own errors is most dangerous
in the settings these systems are aimed at, such as research assistants or clinical and
financial tools, where a wrong fact carries real cost. Measuring the spread lets designs
be compared, so a design that contains contamination can be told apart from one that
does not.
