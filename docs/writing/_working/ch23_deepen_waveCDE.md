# Deepening batch Waves C/D/E — awaiting gates (no NEW references; reuse [9],[12],[16])

===========================================================================
## WAVE C — 2.1.2, ONE new paragraph (trimmed after style gate flagged E1/E2 as
## duplicating existing para 1). Insert AFTER the existing para 1 that ends
## "...it fills the gap with a plausible guess." and BEFORE "Researchers separate
## hallucinations along two lines."  Reuses [9]. New content only:
## compounding/snowballing + no-truth-check + extraction risk.
===========================================================================

**C-new.** [style-fixed]
Two further properties of these models matter for what follows. First, their errors tend to
compound: a model shown its own earlier output stays consistent with it, so an early mistake
is carried forward instead of corrected, and a short chain of steps can drift further from
the facts at each one [9]. Second, the same models have no built-in step that checks a
statement against a source of truth before writing it down, so nothing inside the model
stops a plausible-sounding error from being produced [9]. Extraction, the task at the centre
of this thesis, meets both conditions at once, because it asks the model to turn free text
into filled, structured slots at speed.

===========================================================================
## WAVE D — 2.1.3, TWO new paragraphs. Insert AFTER the KG-superspreader paragraph
## that ends "...why certain error placements spread much further than others." and
## BEFORE the final mapping paragraph ("In the shared-memory setting of this thesis...").
## Reuses [12]. New content: velocity vs reach (final size), herd-immunity threshold.
===========================================================================

**D-reach.** [fact-hedged + style]
It also helps to separate two things an outbreak can be measured by. One is how fast it
grows, which R₀ captures. The other is how far it eventually reaches, meaning the share of
the population infected by the time it stops, known as the final size. In the classic model
the two move together, since a higher R₀ produces a larger final size. They come apart when
new susceptible members keep arriving, because then even a slow-spreading process can build
up a large cumulative reach over many steps. The shared memory studied here is closer to
that second case, since fresh facts keep entering it, so this thesis measures both the speed
at which contamination spreads and the total number of facts it eventually touches, because
a design can do well on one and badly on the other.

**D-herd.** [style-fixed]
Epidemiology also gives a target for control. To stop an infection from growing, enough of
the population must already be immune that each new case reaches, on average, fewer than one
susceptible member. The fraction that must be protected for this to hold is 1 - 1/R₀, so a
faster-spreading infection, with a higher R₀, demands that a larger share be covered [12].
The same arithmetic applies to a contaminated knowledge graph. Once validation has already
protected part of the graph, the quantity that matters is the effective reproduction number,
meaning the same count measured when not everyone is still susceptible. Validation has to
reach enough of the graph to pull that number below one, and how much coverage that takes
rises with how readily errors spread. Chapter 5 examines how large that share has to be, and
what happens to the spread when it is not met.

===========================================================================
## WAVE E — NEW SECTION 3.9 (append at end of ch3, after 3.8). Standard thesis
## "assumptions/scope/threats to validity" content, NON-implementation, NON-results.
## Reuses [16]. States method assumptions and safeguards without stating findings.
===========================================================================

## 3.9 Assumptions, scope, and threats to validity

Every experimental design rests on choices that bound what its results can claim. This
section states the main assumptions behind the method, marks what falls inside and outside
its scope, and lists the threats to the validity of its conclusions, together with the steps
taken to limit each one.

The contamination studied here is non-adversarial. Errors enter because a model misreads
text, not because an attacker plants them, which sets this work apart from data-poisoning
attacks on retrieval systems, where a hostile party crafts inputs to force a chosen output
[16]. Assuming no attacker is the more demanding case to make interesting, because it shows
that spread needs no malice, only ordinary model error and a shared memory. It is also a
limit: the results say nothing about how the system behaves under deliberate attack, and a
validator tuned for honest mistakes may well fail against crafted ones.

The central metric, R₀, is borrowed from epidemiology and applied to facts rather than
people. This is an analogy, and it holds only as far as the mapping in Section 3.4 holds,
where a fact is either able to spread, already caught, or not yet reached, with no state in
between. Where the analogy strains, the number should be read as a summary of spread within
these runs, not as a fixed natural constant. Two of the answer-quality checks, exact match
and FEVER accuracy, are known to move very little at the contamination levels reached here,
so their flatness is expected and is not read as evidence that contamination is harmless.
The grounding metric measures whether an answer traces back to a high-confidence node, which
is a measure of support, not of truth: a faithful reuse of a contaminated fact is traceable
by design, and the analysis treats it that way.

The main threat to internal validity is the language model's own randomness. A run's seed
fixes where errors are injected, but it does not fix what the models generate, so two runs
with the same seed still differ, and a small gap between single runs is treated as noise
rather than an effect. To keep the measuring instrument steady, the judge model used for
validation and auditing is held fixed for the whole study, since changing it partway would
confound a change in the system with a change in the ruler. Because a full run is expensive
on the hardware available, most comparisons rest on four seeds, so differences in variance
are reported as suggestive rather than settled, and every single-seed figure is labelled as
such.

Small samples are handled conservatively. A comparison between two groups reports both a
Welch t-test, which does not assume the groups have equal spread, and a Mann-Whitney U test,
which does not assume the values follow a normal distribution, and a difference is called
real only when both agree. Comparisons of counts in categories use Fisher's exact test. A
working rule treats any single-run gap smaller than about twice the baseline spread as
within noise. These choices trade some ability to detect small effects for caution, which
suits a study where claiming an effect that is not there would be worse than missing one.

The findings are bounded by the setup that produced them. Two open models are used, one for
extraction and one for judgement, both small enough to run on a single machine with no
graphics card, so behaviour on larger or commercial models may differ. The pre-loaded facts
are drawn from the long tail of a public knowledge base, entities the models are unlikely to
have memorised, which is the fair setting for studying extraction but may understate how
well a model resists an error about a famous entity it already knows well. The graph is kept
in one database engine and queried in one way, and the three datasets, though varied, do not
cover every kind of question. Where a result is expected to depend on these choices, and
where it is expected to survive them, the analysis says so rather than leaving it implied.

Finally, the study is built to be repeatable. Every run follows the same three-stage
procedure, loading a fresh graph, extracting into it, then injecting errors and letting them
spread, so that no state leaks from one run into the next. Seeds, configurations, and
per-run outputs are written to files, and the numbers reported in Chapter 5 are read back
from those files rather than recalled from notes. This does not remove the model randomness
described above, but it makes every reported figure traceable to an archived run.
