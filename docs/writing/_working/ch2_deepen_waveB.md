# Ch2 deepening Wave B (2.1.2 info cascades bridge + 2.1.3 SIR assumptions/SEIR) — awaiting gates

## Append to end of 2.1.2 (after "...Section 5.4.3 names the mechanism.") — bridges to 2.1.3

**C1.**
Once an error is written into shared memory, the question becomes how far it travels, and
the spread of information through a population is itself well studied. When one person
passes a claim to others who pass it on again, the result is an information cascade, and
false claims cascade as readily as true ones. A large study of news spreading on social
media found that false stories reached more people and spread faster than true ones, partly
because they were more novel and drew stronger reactions [32].

**C2.**
Researchers separate two ways things spread. In simple contagion a single exposure is
enough to pass something on, as with a cold or a simple rumour. In complex contagion a
person takes something up only after several contacts have, which is common for beliefs and
habits [33]. The contamination this thesis studies behaves like simple contagion: one
retrieval of a wrong fact is enough for an agent to reuse it, because the agent treats
whatever it retrieves as trustworthy without waiting for a second source to confirm it.
That single-exposure behaviour is what makes the epidemic model of the next section a good
fit.

## Insert in 2.1.3 AFTER the equations-prose paragraph ("...produces about β/γ new cases before it recovers.") and BEFORE the network paragraph ("The basic model assumes everyone mixes...")

**D1.**
The basic SIR model rests on assumptions worth stating. It treats the population as closed,
with no members entering or leaving during the outbreak, and it assumes homogeneous mixing,
meaning every member is equally likely to meet every other. It also collapses the whole
course of an infection into a single infected state. These assumptions make the model
simple to fit, and they are reasonable for the short, closed runs this thesis studies,
though homogeneous mixing is the one most worth revisiting, as the next paragraphs do.

**D2.**
Where an infection has a latent period, during which a member is infected but not yet
infectious, a fourth compartment is added between Susceptible and Infected, giving the SEIR
model, with E for exposed [34]. Other variants let recovered members lose immunity and turn
susceptible again. This thesis keeps the plain SIR form, because a contaminated fact is
either able to spread or has been quarantined, with no meaningful latent stage, and because
the simpler model has fewer parameters to fit from short runs. Section 3.4 states how the
model is fitted here.
