# 3.4 Epidemiological formulation (working draft — awaiting gates)

**P1.**
Section 2.1.3 set out the SIR model in general. This section fixes what its three states
mean for this system and how its rates are measured. A fact is Susceptible while it is a
pristine T-REx fact, correct but not yet checked. It becomes Infected the moment it is
contaminated, either because it is an injected index case or because an agent wrote it
while a contaminated fact was in its context. It becomes Recovered when the ValidationAgent
quarantines it. The counts of facts in each state, step by step, are the raw material for
the model.

**P2.**
The transmission rate beta and the recovery rate gamma each stand for something concrete
here. Beta is the chance, per step, that a contaminated fact in an agent's context leads it
to write a new contaminated fact; it rises with how often the graph is read and with how
readily the model reuses what it reads. Gamma is how effectively the validation step
catches and quarantines contaminated facts. The reproduction number R0 = beta / gamma then
says whether one contaminated fact tends to produce more than one more. In arms that run no
validation, gamma is zero and R0 is undefined; those arms are described instead by their
per-step effective reproduction, the average number of new contaminated facts each
contaminated fact produces in one step.

**P3.**
The states are measured from the run's own bookkeeping. The Infected count at each step is
the number of facts marked contaminated so far, minus the contaminated ones that have since
been quarantined; the Recovered count is the number of contaminated facts quarantined. From
these step-by-step counts, beta and gamma are estimated after the run by fitting the SIR
difference equations to the measured trajectory: the equations are run forward with trial
values until the simulated curve matches the observed one as closely as possible, using
non-linear least squares. Section 5.5 reports the fits and how well they match.

**P4.**
Two things about this fit are stated plainly. First, the graph is large and the outbreak is
small: with about fifty thousand facts and fewer than a hundred ever infected, the
Susceptible pool never runs down, so the model cannot show the late flattening that a real
epidemic reaches when it runs out of susceptibles. The fit is therefore of the early,
growing phase, and its quality is reported alongside every estimate. Second, the fitted R0
is checked against a simpler measure that needs no model: the number of new contaminated
facts each index case produces, counted directly from the lineage bookkeeping. This
model-free count is reported overall and for each error type, which is how the second
research question, on which error type spreads most, is answered.
