# 3.7 Evaluation metrics (working draft — awaiting gates)

**P1.**
The system is measured on two fronts at once, and keeping them apart is central to the
analysis. One front is task quality: whether the system still answers questions well. The
other is contamination: how much of the memory is corrupted, how far the corruption has
spread, and whether it can be detected. Table 3.5 lists the metrics under each front.

[TBL]Table 3.5: The evaluation metrics.

| Metric | What it measures | How |
|---|---|---|
| Exact Match and F1 | task quality | HotpotQA answers against the ground truth, at steps 0, 5, and 10, on a fixed set of fifty questions |
| Veracity Accuracy | task quality | FEVER claim classification against the ground truth, on a fixed sample |
| Probe contamination rate | persistence of an error | direct questions about the injected facts: the share whose answer gives the corrupted version |
| Propagated and exposed counts | spread | from the lineage bookkeeping: facts written under contaminated context, and agent contexts holding at least one contaminated fact |
| Detection AUROC | detectability | how well a simple classifier separates contaminated facts from clean ones |
| Quarantine precision | mitigation quality | the share of quarantined facts that were truly contaminated |
| R0 and effective reproduction | contagion velocity | the fitted rates from Section 3.4, plus the model-free per-seed count |

**P2.**
The probe contamination rate and the task metrics answer different questions, and this
thesis leans on the difference. A probe asks the system directly about a fact that was
injected and checks whether it now gives the corrupted answer, so it measures whether the
error persists and is believed. The task metrics measure whether the overall workload still
produces good answers. A memory can be badly contaminated on the probes while the task
scores barely move, and Chapter 5 shows this happening. Reporting only task metrics would
hide the contamination; reporting only probes would overstate the harm.

**P3.**
One more answer-side metric is included, the unsupported sentence ratio. It measures how
much of an answer can be traced back to a trustworthy fact in the memory. An answer sentence
counts as supported if its content overlaps, by a plain word match, with a retrieved fact;
the unsupported sentence ratio is the share of substantive answer sentences that no
retrieved fact supports. This check uses no language-model judge, on purpose, because the
judges are themselves under study and a metric that must stay trustworthy cannot depend on
them. It has one honest limit, stated here and returned to in Chapter 5: word overlap
measures grounding, not truth. A faithful repeat of a retrieved but contaminated fact counts
as supported, because it is indeed grounded in the memory, even though the memory is wrong.
