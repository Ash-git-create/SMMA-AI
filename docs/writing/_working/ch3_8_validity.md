# 3.8 Validity instrumentation (working draft — awaiting gates)

**P1.**
Most of the headline numbers depend, somewhere, on a language model's judgement: the
validator judges facts, and a judge estimates the natural error rate. So the pipeline's own
error processes are measured with three instruments, each checking a different blind spot.

**P2.**
The first is a natural contamination audit. Separate from the injected errors, every fact
the ExtractionAgent wrote during a run, seven hundred and eighty-three of them, is checked
against the passage it came from by a judge of the same grade as the validator, using the
three error types as its labels. This estimates how often the models make these errors on
their own, without any injection, which speaks to the first research question, and it checks
whether the injected error types resemble the ones that arise naturally, which speaks to the
realism of the second.

**P3.**
The second instrument calibrates that audit against a human. A sample of forty audited
facts, balanced between those the judge accepted and those it flagged and including every
relation flag, was labelled by hand against the source passages, with the labeller blind to
the judge's verdict. These human labels are the ground truth for how accurate the judge is,
and the audit's own rates are corrected using the judge's measured accuracy. This step
matters because an uncalibrated judge can badly misstate the natural error rate, and
Chapter 5 gives the size of the gap.

**P4.**
The third instrument measures a channel the audit cannot see. The audit checks whether a
fact was extracted faithfully from its source, but a fact can be faithfully extracted and
still be false in the world, and the audit would call it fine. The FEVER dataset carries a
ground-truth verdict for each of its claims: supported, refuted, or not enough information.
Mapping every FEVER-derived fact to its claim's verdict gives an exact, judge-free count of
how much false or unverifiable content enters the memory through this channel.

**P5.**
Taken together, these three instruments form a layered check: a language-model audit, a
human calibration of that audit, and a ground-truth channel the audit cannot reach. The
design is itself a small methodological contribution, because it shows, and Chapter 5
confirms, that an uncalibrated language-model measurement of contamination can be wrong by a
wide margin. A thesis that measures contamination with language models has to measure its
own measuring first.
