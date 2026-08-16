# 3.6 Experimental design (working draft — awaiting gates)

**P1.**
Every run starts from an identical state, a clean-room protocol that keeps the arms
comparable. Before each run the graph is cleared and reloaded with the pristine T-REx
snapshot, the extraction pipeline is replayed with a fixed seed and the same set of
documents, and only then does the contamination run begin. Because this starting point is
the same every time, two runs differ only in the things the experiment means to change:
their configuration file and, within a repeated run, the random seed that places the
errors.

[TBL]Table 3.4: The experiment arms. Floor is the retrieval confidence threshold; Audits is the validation sampling per step; Prop. is write-time confidence propagation.

| Arm | Floor | Audits | Prop. | Purpose |
|---|---|---|---|---|
| baseline | off | off | off | unmitigated spread |
| ablation_floor | 0.5 | off | on | the retrieval floor alone |
| ablation_validation | off | 25/step | off | the validation channel alone |
| mitigated | 0.5 | 25/step | on | the full Trio combination |
| control_random | off | off | off | baseline with random error placement (RQ1 control) |
| oracle | 0.5 | 25/step, ground truth | on | full Trio with a perfect judge (RQ4 upper bound) |
| mitigated_tuned | 0.5 | 25/step, tuned prompt | on | full Trio with a prompt-tuned judge |

**P2.**
Two of these arms need a word of explanation. The oracle arm replaces the validator's
judgement with the experiment's own ground-truth labels, while leaving everything else about
validation the same. It shows the best the architecture could do with a perfect judge, and
by design it cannot exist outside the laboratory, because a real system has no ground-truth
channel to consult. The tuned arm changes only the judge's instructions, keeping the model,
the response format, and the thresholds fixed; its prompt was chosen beforehand on a set of
hand-labelled examples. Together the two arms bracket the validator: the oracle shows the
ceiling, the tuned arm a realistic middle.

**P3.**
Beyond these core arms, several sweeps vary one factor at a time to answer the third and
fourth research questions: how often the memory is checked, how far the index cases sit from
the region agents retrieve, and how accurate the validator is. Each sweep is described where
its results appear in Chapter 5.

**P4.**
The baseline and the full mitigated arm were each run across four random seeds, 42 to 45:
the baseline to fix how much results vary from seed to seed, the mitigated arm to test
whether its result holds across seeds. A single-run difference smaller than about twice the
baseline's standard deviation is treated as within that seed-to-seed noise and is hedged
accordingly. The random-placement control is a single seed by design, because its effect is
forced by the setup rather than being a statistical average, and this is noted as a
limitation rather than repeated.

**P5.**
Two controls keep the numbers comparable and stable. The questions used to measure task
quality are drawn with a fixed seed of their own, separate from the seed that places the
errors, so task scores can be compared across runs; the contamination probes use the run's
seed. And every call to a language model goes through a caching layer that waits and retries
when a rate limit is hit, so a rate-limited run takes longer in wall-clock time but produces
the same result. No completed run lost a call this way.
