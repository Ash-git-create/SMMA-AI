# Chapter 6 — Deviations from the Research Proposal

> **Draft status (2026-07-25):** first draft for the limitations chapter.
> Every number below is cross-checked against an archived file in
> `results/summaries/` or against the corresponding section of Chapters 3–5
> as drafted to date. The audit-cadence sweep that row 2 previously left
> pending has landed (`phase48_interval_*`, ch5 §5.4.6); no markers remain
> open.

This section states, without softening, where the delivered thesis diverges
from the approved exposé (25.03.2026). Six months of empirical work
surfaced constraints — hardware, API economics, and the KG's own structural
properties — that the proposal could not have anticipated, and produced at
least one outright reversal of the exposé's central hypothesis. The
discipline applied throughout the results chapters (numbers from archives
only, single-seed claims labelled, retractions recorded rather than
overwritten) is applied here as well: each row states the commitment as
written, what was actually built or measured, and where in the delivered
chapters the consequence is visible. Nothing here is a confession of failure
in the ordinary sense — several of the deviations (rows 4 and 6 especially)
are where the thesis found its strongest and most publishable results
precisely *because* the original plan did not survive contact with the
system.

## 6.1 Summary table

| # | Exposé commitment (§ ref) | What was delivered | Where addressed |
|---|---|---|---|
| 1 | §1.2 (RQ1): vary "graph density, agent count, and memory write frequency" | Agent count was never varied — no `agent_count` parameter exists in the codebase. Argued (not run): in this shared-memory architecture, agent count acts on contamination only through KG write frequency and retrieval frequency, both of which were varied directly. | ch3 §3.1; ch5 §5.9.2–§5.9.3 |
| 2 | §1.2 (RQ3): "validation intervals" as a swept design parameter | Addressed on two axes. Validation-*quality* sweeps (precision, then recall) identified recall as the causal lever; a literal audit-*cadence* sweep (validate every 2/5/10 steps, seeds 42–44, perfect oracle, coverage held constant) then closed the exposé's exact commitment — in-run cadence is second-order but end-only deferral collapses containment (R₀ 2.25 ± 0.21, 3/3 super-critical). | ch5 §5.4.4, §5.4.5, **§5.4.6**, §5.9.5 |
| 3 | §1.3: "strictly utilizing localized infrastructure ... to eliminate ... API constraints" | Violated. CPU-only local hardware could not run full-scale experiments; the system pivoted to hosted APIs (Mistral API, Groq API). Free-tier token ceilings then shaped the science: n=4 as standard replication depth, capped audit samples, paced runs. | ch3 §3.1; ch4 §4.1, §4.9; ch5 §5.8 |
| 4 | §3 (Expected Outcomes): Trio-style provenance solutions will be "highly effective" | Largely refuted. Full Trio shows no mean spread benefit at n=4, pooled quarantine precision 5.9%, and the only statistically significant effect is AUROC *degradation* (confidence laundering). The oracle upper bound reaches only the epidemic threshold, not comfortable containment. | ch5 §5.4.1, §5.4.2, §5.4.5 |
| 5 | §4.1: x-tuples as "one or more mutually exclusive alternatives" per data point | Implemented as a (value, confidence, lineage) singleton per triplet. The disjunctive/alternatives machinery exists in code but is exercised by no pipeline path. Consistently labelled "Trio-*inspired*" rather than a full x-relation implementation. | ch4 §4.2.2 |
| 6 | §1.2 (RQ2), §5: HotpotQA EM / FEVER accuracy as the primary per-error-type degradation instrument | EM and FEVER accuracy proved flat at feasible injection densities in all four baseline seeds. The KG-side probe metric substituted as the sensitive instrument; the flatness itself became the reach-vs-harm decoupling finding. | ch5 §5.1, §5.2 |
| 7 | §1.2: motivating arithmetic (95%/step → 59% over 10 steps); implicit assumption that characterized cascades arise from natural model error | All characterized cascades are seeded by controlled injection. The measured *natural* fidelity-error rate is ≈0.9% (an earlier 11.9% naive figure is retracted in place). The 95%→59% compounding curve motivates but was never directly measured. Delivered claims are conditional: *given* an error enters the retrieval-reachable region. | ch5 §5.1, §5.7 |
| 8 | §2.1: "semantic geometric co-evolution," Ollivier–Ricci curvature, agent-level superspreader framing | Not implemented at any level — zero references to Ricci curvature or agent-communication-graph centrality in the codebase. Superspreader/topology framing was realized only at the KG-node level (k-hop distance, entity-degree density), never at the agent-communication level the literature review describes. | ch5 §5.9.1, §5.9.4 |
| 9 | §1.3: "highly controlled, reproducible simulation environment" | Reproducibility is protocol-level, not trajectory-level: the run seed fixes injection placement but not LLM generation, so same-seed reruns produce different step-by-step numbers under an identical clean-room protocol. | ch5 §5.4.1 |

## 6.2 Row-by-row

### 6.2.1 RQ1's "agent count" axis was argued, not run

The exposé's first research question commits to "systematically varying
graph density, agent count, and memory write frequency" (§1.2). No
`agent_count` parameter exists anywhere in the codebase, in any experiment
config, or in any runner script — grepping the repository for the term
returns nothing. Every experiment in this thesis runs the same fixed
three-agent architecture (ExtractionAgent, OrchestrationAgent,
ValidationAgent; ch3 §3.1). The commitment was not fulfilled as a literal
sweep.

The resolution taken instead is architectural, not procedural: in a
shared-memory design where "the retrieval channel is the transmission
vector" (ch3 §3.1), the number of distinct agent processes has no direct
causal path to contamination velocity. What matters is how much new content
enters the graph per unit time and how much of the graph is pulled into any
one synthesis context — i.e., write frequency and retrieval frequency —
regardless of how many agent instances perform those writes and reads. RQ3's
dose-response sweeps vary exactly those two channels directly and find
clean, monotone, n=4-replicated effects: reproduction per index case rises
from 0.176 ± 0.051 (half write frequency, `wf6`) through the 0.452 ± 0.088
baseline to 0.915 ± 0.209 (double write frequency, `wf24`), and from
0.277 ± 0.070 (`context_limit`=3) through baseline to 0.743 ± 0.139
(`context_limit`=10), the latter contrast significant at Welch t p=0.005 /
Mann–Whitney U p=0.029 (`results/summaries/phase45_rq3_replication_n4.csv`;
ch5 §5.9.2–§5.9.3). This is a substitution argument, not a proof: a literal
agent-count sweep with genuinely concurrent writers could introduce
contention or race dynamics that scaling per-step write volume alone does
not capture, and that possibility is not ruled out here — only argued to be
a second-order concern relative to the two channels that were measured.

### 6.2.2 RQ3's "validation intervals" became a validation-*quality* axis

The same research question also commits to varying "validation intervals"
(§1.2) as one of three systemic design choices affecting contamination
velocity and reach. An early methodology note recorded the intent to answer
this "simulation-first" (SIR-fit calibrated, then swept in the model rather
than empirically) because "full empirical sweeps do not fit the Phase 4
budget" (`docs/thesis_log.md`, entry preceding 2026-07-09's audit sprint).
What was actually delivered diverges further still: instead of varying
*how often* validation runs, the thesis varies *how good* validation is at
a fixed audit budget — first along the precision axis (the noisy-oracle
sweep, ch5 §5.4.4: realized precision 6.6%–33.3% at perfect recall, R₀
clustering 0.87–0.93 across three n=4 sweep points, `phase40_oracle_noisy_
p{75,50,10}_*` and `phase40_sir_fit_oracle_noisy_p{75,50,10}[_s43-45].csv`),
then along the recall axis (ch5 §5.4.5: sensitivity 1.00 → 0.25 drives mean
R₀ from 0.97 ± 0.21 to 3.78 ± 1.86, Spearman ρ = −0.67, p = 0.005, n = 16
runs; `phase42_oracle_sens*`). This substitution is explicit in the record
rather than concealed: ch5 §5.9.5 states plainly that "the validation-interval
component of RQ3 (audit cadence) is addressed epidemiologically through the
γ-bearing arms of Section 5.4 rather than as a separate β-substrate sweep; a
dedicated audit-cadence axis is noted as deferred."

That gap is now closed. A literal audit-cadence sweep — the oracle validator
invoked every 2, 5, or 10 steps instead of every step, with recall and
precision held perfect and *total coverage held constant* (skipped steps'
audit candidates accumulate and are swept in full at the next validation
step), seeds 42–44 — was run as the direct instrument for isolating cadence
from judgement quality (`experiments/configs/contamination_oracle_int{2,5,10}
_s{42,43,44}.yaml`; `results/summaries/phase48_interval_*`,
`phase48_sir_fit_interval.csv`, `phase48_interval_summary.csv`; analysed in
ch5 §5.4.6). The result is a threshold rather than a gradient: any in-run
cadence (every 1, 2, or 5 steps) holds mean R₀ at or below the epidemic
threshold with 0/3 arms super-critical at intervals 2 and 5, whereas
deferring all validation to a single end-of-run sweep drives R₀ to
2.25 ± 0.21 with all three seeds super-critical (interval-10 vs every-step
Welch t p = 0.0008; Mann–Whitney U p = 0.057, the n = 3-vs-4 floor). The
mechanism is model-free: at interval 10, `det_R_contam` is exactly 0 for
steps 1–9, so the system runs at the unmitigated reproduction number for the
entire propagating phase and the late sweep arrives after the epidemic. The
in-run intervals are not monotone (Spearman ρ = 0.36, p = 0.22) and n = 3
per interval keeps every cross-interval comparison suggestive rather than
significant — the robust, load-bearing claim is only the end-only collapse.
This substitution history — quality axis first, cadence axis second — is
recorded rather than smoothed over: the exposé asked one question about
"validation intervals," and the thesis answers it as two distinct levers
(how *good* the validator is, and *when* it runs), which is a richer result
than the single ablation the proposal envisioned.

### 6.2.3 The "localized infrastructure" commitment was violated by hardware, and the consequence propagated into the statistics

Section 1.3 of the exposé commits to "strictly utilizing localized
infrastructure to eliminate unpredictable latency and API constraints."
This did not hold. The local machine — a Ryzen 5 CPU, 16 GB RAM, and an RX
560X GPU with no ROCm support on Windows — cannot run a 12B-parameter model
at usable throughput: CPU-only Q4 inference is documented at a few tokens
per second, and a full 10-step contamination run with per-step evaluation
"would take days per arm" (ch4 §4.9). The system was pivoted to hosted APIs
during Phase 2 — Mistral's API for extraction, Groq's API for orchestration
and validation — preserving model families, sizes, prompts, and the
two-tier split, but abandoning the "localized infrastructure" and
"eliminate ... API constraints" commitments outright (ch3 §3.1, ch4 §4.1).

The consequence is not cosmetic. Both APIs are used on free tiers by
deliberate choice (paid upgrades were declined), and Groq's rolling
24-hour token budget caps throughput at roughly one to three full runs per
day (ch4 §4.9). This is the direct cause of several standing methodological
choices stated as project invariants: n = 4 seeds became the standard
replication depth rather than a larger number (ch5 §5.8; CLAUDE.md
discipline rule 3), audit samples are capped at 25 nodes per step, and
runs are paced and scheduled around exhausted rate-limit windows rather
than run back-to-back. The exposé's premise — that eliminating API
constraints would buy predictable, unconstrained experimental throughput —
is precisely the premise that failed, and the small-n statistical apparatus
built throughout Chapter 5 (paired Welch/Mann–Whitney tests, explicit
noise envelopes) exists largely to make defensible claims *despite* that
failure, not because n = 4 was ever the intended design.

### 6.2.4 The central hypothesis — "provenance solutions ... highly effective" — is largely refuted, and this is the thesis's strongest result

Section 3 of the exposé states the expected outcome plainly: "the thesis
will demonstrate that historical, mathematically proven solutions for data
provenance are highly effective at solving contemporary issues of context
degradation in LLMs." The delivered evidence does not support this claim as
stated, and states the refutation explicitly rather than reframing it.

At n = 4 (seeds 42–45), the full Trio arm shows no reliable mean effect on
spread relative to baseline (propagated Welch p = 0.71, Mann–Whitney
p = 0.31; exposed p = 0.74 / 0.69), a roughly tenfold variance amplification
on spread metrics (suggestive at F(3,3) p ≈ 0.09, not conclusive at this n),
and the *only* statistically significant effect across every metric tested
is a *degradation* in detection: AUROC falls from 0.899 ± 0.007 (baseline)
to 0.859 ± 0.013 (Welch p = 0.004; Mann–Whitney p = 0.029, perfect
separation), via a confidence-laundering mechanism — validation passes
raise surviving nodes' confidence toward 1.0 while quarantine removes
mostly-clean nodes (ch5 §5.4.1). Pooled quarantine precision across all four
seeds is 5.9% (14/238; `phase37_mitigated_multiseed.csv`,
`phase37_mitigated_s{43,44,45}_trajectory.csv`).

The upper bound the architecture can reach — replacing the 8B judge with a
perfect (ground-truth) oracle while leaving the architecture untouched —
does not rescue the exposé's claim either: R₀ falls to only the epidemic
threshold, 0.97 ± 0.21 across n = 4 seeds with 2 of 4 seeds landing
super-critical, not to comfortable sub-critical containment. This is stated
carrying its own retraction history rather than hidden: an earlier version
of this finding, based on the single seed-42 run, reported "R₀ = 0.79 — the
only sub-critical configuration in this thesis"; replication to n = 4
dissolved that headline in the same way the seed-42 "full-Trio harm"
headline dissolved, and the retraction is recorded in place in ch5 §5.4.2
rather than the earlier number being quietly dropped.

Framed honestly, this is an inversion of the exposé's hypothesis *with an
identified mechanism*, which is why it is treated as the thesis's strongest
result rather than a weakness to minimize: provenance-aware retrieval is
only as good as the judgement feeding it, judge *recall* (not precision, not
the cascade architecture) is the causal lever on R₀ (Spearman ρ = −0.67,
p = 0.005, n = 16 runs; ch5 §5.4.5), and even a perfect judge on this audit
budget cannot push the system reliably below the epidemic threshold. The
exposé predicted a solution; the delivered thesis characterizes precisely
why, and by how much, that class of solution falls short.

### 6.2.5 X-tuples: singleton value-confidence-lineage records, not mutually-exclusive alternatives

Section 4.1 of the exposé describes x-tuples as structures that "represent
one or more mutually exclusive alternatives for a specific data point,"
mirroring "the probabilistic nature of natural language generation." The
delivered implementation (`src/graph/provenance_schema.py`) stores exactly
one `(value, confidence, lineage_formula)` triple per KG triplet — a
singleton, not a set of alternatives. Chapter 4 documents this gap directly:
"the disjunctive form (and its arithmetization, `noisy_or` in
`src/mitigation/trio_framework.py`) is implemented but exercised by no
pipeline path — the write path never produces alternative derivations"
(ch4 §4.2.2). The machinery for genuine x-relations exists in code but was
never wired into an experimental path, because no agent in this pipeline
ever produces two competing candidate values for the same fact rather than
overwriting one with another.

This gap is why the codebase consistently labels the mitigation "Trio-*
inspired*" (see the module docstrings in `src/agents/extraction_agent.py`,
`src/mitigation/trio_framework.py`, and `src/graph/provenance_schema.py`)
rather than claiming a full ULDB-style implementation. The deviation is
scoping, not concealment: value-confidence-lineage tracking, the lineage
formula, and cascade deprecation are all implemented and evaluated; the
alternatives/uncertainty-set half of Trio's ULDB model is not.

### 6.2.6 The task-performance instrument (EM/FEVER) was insensitive at feasible densities; its flatness became a finding, not a gap

The exposé nominates HotpotQA Exact Match and FEVER Veracity Accuracy as the
metrics for measuring "the resulting degradation" from each error type
(§1.2, RQ2) and lists them as the primary "Task Performance" category in the
evaluation table (§5). In all four baseline seeds, both metrics were flat
from step 0 to step 10 of the run while the KG-side probe contamination rate
sat at 0.62–0.88 (mean 0.717 ± 0.113 at step 10, n = 4; ch5 §5.1). EM and
FEVER accuracy did not detect the contamination that was demonstrably
present and confidently served by the graph.

Rather than treating this as an instrument failure to be quietly worked
around, the delivered thesis reports the flatness itself as a substantive
result: contamination *reach* (what the KG believes) and task *harm* (what
the workload scores) decouple at Phase 2–3 injection volumes, because 45
corrupted facts among roughly 51,000 nodes are rarely load-bearing for a
50-question sample (ch5 §5.2). The KG-side probe — directly querying an
injected fact and checking whether the corrupted version is returned —
substituted as the primary sensitive instrument for the remainder of the
thesis. This is stated as a scope finding, not evidence of safety: task
metrics remain reported throughout, and their insensitivity at these
densities is an explicit interpretation trap the thesis flags rather than
one a reviewer would need to discover independently.

### 6.2.7 Injected, not natural, contamination characterizes every cascade in this thesis

The exposé's motivating paragraph (§1.2) offers a compounding-error
narrative — individual agents at "ninety five percent per step accuracy"
compounding to "fifty nine percent" cumulative success over ten steps — as
the mechanism this thesis investigates, with an implicit framing that the
measured cascades arise from the models' own natural error rate. What is
actually characterized throughout Chapters 5's SIR fits, R₀ estimates, and
error-type rankings is controlled injection: 45 injection attempts per
baseline run (15 per error type, RS realizing 9–10 in active-pool
placement), yielding 39–40 realized index cases (ch5 §5.1).

The natural (uninjected) fidelity-error rate was measured separately and is
small. A naive audit flagged 93 of 783 extraction-written triplets (11.9%;
`results/summaries/phase34_natural_audit_summary.json`), but blind human
calibration against the source passages found the judge's flag precision to
be only 10% (2/20; `results/summaries/phase34_judge_calibration_summary.
json`), extrapolating to a corrected natural fidelity-error rate of
approximately 0.9% (≈7.4/783, wide CI) — the naive 11.9% figure is retracted
in place, not deleted, in both the archive file and ch5 §5.7(a)-(b). At that
rate, the 95%→59% compounding arithmetic that opens the exposé's problem
statement was never directly demonstrated on this system's own natural error
rate; it motivates the injection design but is not itself an empirical
claim this thesis makes. What is delivered is conditional: *given* that an
error enters the retrieval-reachable region of the KG (by injection, or, at
the measured ≈0.9% natural rate, occasionally by extraction), it can
reproduce at R₀ well above 1 (up to 4.46 ± 2.36 under the default judge; ch5
§5.4.1, §5.5) — a dynamics claim, not a claim about how often such an error
arises unprompted.

### 6.2.8 Semantic-geometric co-evolution and Ollivier–Ricci curvature appear in the literature review only; topology framing was realized at the node level, never the agent level

Section 2.1 of the exposé's state-of-the-art review builds toward "semantic
geometric co-evolution" as the necessary lens for multi-agent auditing,
naming Ollivier–Ricci curvature as the discrete geometric measure for
characterizing "information redundancy" and "bottleneck formation" in
agent communication topologies, and frames highly central nodes as
potential "superspreaders" of contamination. None of this was implemented.
A search of the source tree for Ricci, Ollivier, superspreader, or
agent-communication centrality returns no matches anywhere in `src/`.

The topology-and-centrality framing that *was* built operates one level
down from what §2.1 describes: on KG nodes and entities, not on the
inter-agent communication graph. Two instruments were delivered — exact
BFS distance from the active retrieval subgraph (`k-hop`, ch5 §5.9.1: at
k = 1, 2, and 3, propagation and exposure are exactly zero across all four
seeds, establishing reachability as a hard threshold rather than a
distance-decaying quantity) and structural KG density via mean entity
degree (ch5 §5.9.4: the achievable range on this T-REx graph is hard-capped
at 0.86×–1.26× baseline, and no structural-density effect survives n = 4
replication — an earlier single-seed "large inverse effect" claim is
withdrawn in place). Both are genuine superspreader/topology-adjacent
findings, but they characterize *which facts* are vulnerable by their
position in the knowledge graph, not *which agents* are structurally
positioned to amplify or dampen contamination in the communication network
the exposé's literature review describes. That agent-level question was
never operationalized.

### 6.2.9 Reproducibility is protocol-level, not trajectory-level

Section 1.3 of the exposé describes the target as "a highly controlled,
reproducible simulation environment." What is delivered reproduces the
experimental *protocol* exactly — the same three-stage clean-room sequence
(`load_kg --clear` → `run_extraction` → `run_contamination`), the same
injection placement for a given seed, and the same configuration — but not
the exact numeric trajectory of a rerun. The run seed is documented to fix
*injection placement* only, not LLM generation; residual API
nondeterminism (both APIs are hosted, not locally pinned) means two runs
under an identical seed and protocol produce different step-by-step
numbers. This is evidenced directly: an earlier, killed partial run of
seed 45 (stopped at step 10 before evaluation) produced 12 propagated / 75
quarantined nodes, versus 10 propagated / 50 quarantined for the completed
run under the same seed and clean-room protocol (ch5 §5.4.1). The chapter
treats this as expected behaviour that strengthens rather than undermines
the variance findings, not as a bug — and CLAUDE.md's discipline rules
record the same invariant as a standing caveat against treating rerun
deltas as errors (discipline rule 6). The distinction matters for anyone
attempting to replicate this work: re-running the pipeline with the same
seed will reproduce *which* facts were corrupted and *where* they were
placed, but not the exact propagated/exposed counts of any single run.
