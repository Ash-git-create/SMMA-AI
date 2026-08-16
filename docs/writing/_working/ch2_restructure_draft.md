# Chapter 2 restructure — FINAL (gated), awaiting Ashwin's approval to integrate

Style gate: applied all sentence-splits + padding cut. Fact+originality gate: all 4 paper
characterizations TRUE; Gu softened to "roughly a million"; Margalit 2.3.3 sentence
reworded away from source wording.

New refs (verified):
[42] T. Ju, Y. Wang, X. Ma, P. Cheng, H. Zhao, Y. Wang, L. Liu, J. Xie, Z. Zhang, and
     G. Liu, "Flooding Spread of Manipulated Knowledge in LLM-Based Multi-Agent
     Communities," arXiv:2407.07791, 2024. Available: https://arxiv.org/abs/2407.07791
[43] X. Gu, X. Zheng, T. Pang, C. Du, Q. Liu, Y. Wang, J. Jiang, and M. Lin, "Agent Smith:
     A Single Image Can Jailbreak One Million Multimodal LLM Agents Exponentially Fast," in
     Proc. 41st Int. Conf. on Machine Learning (ICML), 2024. Available: https://arxiv.org/abs/2402.08567
[44] X. Shen, Y. Liu, Y. Dai, Y. Wang, R. Miao, Y. Tan, S. Pan, and X. Wang, "Understanding
     the Information Propagation Effects of Communication Topologies in LLM-based Multi-Agent
     Systems," in Proc. Conf. on Empirical Methods in Natural Language Processing (EMNLP),
     2025. Available: https://doi.org/10.18653/v1/2025.emnlp-main.623

================================================================================
## 2.2 Related Work

Three strands of recent work touch this thesis: attacks on agent memory, models of how
errors spread between agents, and attempts to contain that spread. This section takes each
in turn, and Section 2.3 sets out where this thesis sits against it.

### 2.2.1 Attacks on agent memory

The first strand is adversarial. Recent work shows that an attacker can poison a shared
memory by feeding it crafted inputs, so that later retrievals return the attacker's
content [16]. Ju et al. [42] go further and follow what happens after the first agent is
fooled: manipulated knowledge introduced by a two-stage attack spreads through a community
of language-model agents and stays in circulation as the agents retrieve and reuse it,
rather than remaining with the agent that was first misled. Both results matter here,
because they show a shared memory can carry a corrupted fact from one agent to many. They
also differ from this thesis in one basic way: they assume an attacker who chooses the
false content and intends the harm, while the errors studied here have no attacker behind
them.

### 2.2.2 Models of how errors spread

The second strand models how errors move once they are present. Niu et al. [5] adapt a
compartmental epidemic model to a network of language-model agents and derive the
conditions under which errors invade the network. Jamshidi et al. [17] track factual
errors as they pass down a chain of agents and find, on their setup, that the errors
shrink rather than grow. Liu [18] studies how the preferences of a language model acting
as an evaluator spread to other agents. Two further results mark the edges of this space.
Gu et al. [43] show an extreme case. A single crafted input sets off a self-propagating
failure that reaches roughly a million simulated agents and grows exponentially. This is
the scale-limit of what unchecked spread can reach. Shen et al. [44] inject errors into
multi-agent systems wired together in different shapes. They compare each run against a
matched run without the injected error, to measure how much the network's shape changes
how far the error travels. These works share this thesis's view of error spread as a
contagion, but they place the contagion on the agents and the messages between them, not
on the facts in a shared memory.

### 2.2.3 Attempts to contain the spread

The third strand tries to contain the spread. Xie et al. [6] inject a single error into a
group of collaborating agents, then add a governance layer that tracks each message's
ancestry. They report that it stops the error from taking over in most runs. Margalit et
al. [19] name the failure modes of shared agent memory, including the loss of provenance.
They build and measure provenance tracking and governed sharing as the fix, but test it
under ordinary operation rather than under a spreading error. Itkin [20] studies the
timing of validation and finds that correcting too late, or too aggressively, can
destabilise the agents' shared belief rather than settle it. The first two build or assume
that provenance-like machinery will contain the spread, which is exactly the claim this
thesis puts to the test.

Section 2.3 compares these three strands with the present work, point by point, and states
what it adds.

================================================================================
## OPTIONAL — add at the end of §2.3.3 (convergent evidence; rests on one industry preprint)

One recent result converges on this thesis's mechanism from a different direction.
Margalit et al. [19], reporting on a production memory service, describe a case where their
duplicate filter runs before their contradiction check. A correcting fact that looks
similar to the one it is meant to fix can then be dropped as a duplicate before anything
compares what it actually says. That is structurally the same problem this thesis finds
from the non-adversarial side: an error that overwrites its own supporting evidence leaves
a later check nothing to catch it with (Chapter 5). That two systems, built for different
purposes, hit the same wall is weak but real evidence that the wall belongs to
provenance-governed shared memory itself, and not to one implementation. The point is
tempered by its source, a single industry report that has not been independently
reproduced.
