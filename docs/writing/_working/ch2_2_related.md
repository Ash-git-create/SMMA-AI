# 2.2 Related Work (working draft — awaiting gates; strict paragraph approval)

**P1 (lead-in + adversarial strand).**
Three strands of recent work touch this thesis: attacks on agent memory, models of how
errors spread between agents, and attempts to contain that spread. This section describes
each strand, and Section 2.3 sets out where this thesis sits against it. The first strand
is adversarial. Recent work shows that an attacker can poison a shared memory by feeding
it crafted inputs, so that later retrievals return the attacker's content [16]. This work
matters, but it assumes an attacker with intent. The errors this thesis studies have no
attacker behind them.

**P2 (error-spread models).**
The second strand models how errors move between agents once they are present. Niu et al.
[5] adapt a compartmental epidemic model to a network of language-model agents and derive
the conditions under which errors invade the network. Jamshidi et al. [17] track factual
errors as they pass down a chain of agents and find, on their setup, that the errors
shrink rather than grow. Liu [18] studies how the preferences of a language model acting
as an evaluator spread to other agents. These works share this thesis's view of error
spread as a contagion, but they place the contagion on the agents and the messages
between them.

**P3 (containment attempts).**
The third strand tries to contain the spread. Xie et al. [6] inject a single error into a
group of collaborating agents and add a governance layer that tracks each message's
ancestry. They report that it stops the error from taking over in most runs. Margalit et
al. [19] name the failure modes of shared agent memory, including the loss of provenance,
and propose provenance tracking and governed sharing as the fix. Itkin [20] studies the
timing of validation and finds that correcting too late, or too aggressively, can
destabilise the agents' shared belief rather than settle it. The first two propose or
assume that provenance-like machinery will contain the spread.

**P4 (lead-out to 2.3).**
These three strands give the immediate context for this thesis. Section 2.3 compares them
with the present work point by point and states what it adds.
