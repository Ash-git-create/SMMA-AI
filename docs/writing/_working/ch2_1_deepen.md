# 2.1.3 and 2.1.4 deepened (NEW paragraphs only — awaiting gates)

## 2.1.3 new paragraph (difference equations), inserted after the beta/gamma/R0 paragraph

**NEW-A.**
The model is written as a set of update rules applied once per time step. Writing S, I,
and R for the counts in each group and N for the total, a discrete-time step is
S(t+1) = S(t) - beta*S(t)*I(t)/N; then I(t+1) = I(t) + beta*S(t)*I(t)/N - gamma*I(t); and
R(t+1) = R(t) + gamma*I(t). The first rule moves new infections out of the susceptible
group, the second adds them to the infected group and takes recoveries out of it, and the
third collects the recoveries. The reproduction number R0 = beta/gamma follows from these
rules: an infected member stays infectious for about 1/gamma steps and infects about beta
others per step while the population is still mostly susceptible, so it produces about
beta/gamma new cases before it recovers.

## 2.1.3 replacement for the final (mapping) paragraph, now referencing Figure 2.1

**NEW-B (replaces old P3).**
The same three states map onto the facts in a shared memory, shown in Figure 2.1. A
knowledge-graph fact is susceptible when it is correct but not yet checked, infected when
it has been contaminated by an error, and recovered when a validation step has caught and
quarantined it. Transmission happens when an agent retrieves a contaminated fact and
writes new contaminated facts from it, so beta stands for how often the graph is read and
how readily a model reuses what it reads. Recovery happens when a validation step catches
an error, so gamma stands for how good that checking is. Section 3.4 gives the exact form
of these rules used in the thesis and how R0 is fitted from a run.

FIGURE 2.1 here: fig_sir_compartments.png
Caption: "Figure 2.1: The SIR model mapped onto knowledge-graph facts. A fact moves from
Susceptible (clean, unchecked) to Infected (contaminated) at rate beta, and from Infected
to Recovered (quarantined) at rate gamma."

## 2.1.4 new paragraph (lineage formula and arithmetization), inserted after the ULDB paragraph

**NEW-C.**
The lineage formula is what makes the confidence numbers add up. It is a boolean
expression that records how a derived fact was built from earlier ones. If a fact was
concluded from two earlier facts that were both needed, its lineage is their AND; if it
could have come from either of two independent sources, its lineage is their OR.
Confidence is then read off this formula by turning the logic into arithmetic, a step
called arithmetization: an AND multiplies the confidences of its parts, because both
parts must hold, while an OR combines them so that two independent sources give more
confidence than either one alone. This lets the system work out a derived fact's
confidence directly from its ancestors' confidences, without re-checking the whole chain
by hand.
