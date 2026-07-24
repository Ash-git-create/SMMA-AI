# Chapter 5 — Evaluation & Results (Phase 2–4 sections)

> **Draft status (2026-07-12):** covers all completed Phase 2–3 experiments,
> including the mitigated multi-seed replication (task #14, seeds 42–45).
> Phase 4 (RQ3 sweeps) sections are not yet drafted. Figures marked `[FIG]`.

## 5.1 Unmitigated contamination dynamics (baseline, 4 seeds)

Forty-five injection attempts per run (15 per error type; RS realises 9–10
in active-pool placement) yield 39–40 index cases. Over 10 steps, baseline
runs across seeds 42–45 produced:

| Metric | Mean ± SD (n=4) | Range |
|---|---|---|
| Propagated errors | 17.8 ± 4.0 | 12–21 |
| Cumulative exposed contexts | 65.3 ± 8.3 | 56–75 |
| Reproduction per index case | 0.45 ± 0.10 | 0.31–0.54 |
| Probe contamination rate (step 10) | 0.717 ± 0.113 | 0.617–0.877 |
| Detection AUROC | 0.899 ± 0.007 | 0.891–0.905 |

Contamination spreads without any adversary: roughly one propagated error
for every two index cases within 10 steps, and directly probing an injected
fact reproduces the corrupted version ~72% of the time. All effect-size
claims in this chapter are assessed against this seed-noise envelope;
single-run differences under ~2 baseline SD are treated as within noise.

`[FIG] Trajectories of cumulative propagated/exposed per seed.`

## 5.2 Reach without harm: probes vs task metrics

In all four baseline seeds, task metrics were flat from step 0 to step 10
(HotpotQA EM unchanged; FEVER accuracy unchanged) while probe contamination
sat at 0.62–0.88. Contamination *reach* (what the KG believes) and *task
harm* (what the workload scores) decouple at this scale: the corrupted facts
are confidently served when asked about, but 45 corrupted facts among ~51,000
nodes are rarely load-bearing for a 50-question sample.

This is not a null result; it identifies the regime. Task-level damage is a
function of contamination *density in the queried region*, and at Phase 2–3
injection volumes the probes are the sensitive instrument. (A cross-run
comparability flaw — task questions originally sampled with the run seed —
was found and fixed during Phase 3; only within-seed flatness is claimed for
the affected runs. All runs from 2026-07-09 onward use a fixed evaluation
seed.)

## 5.3 Retrieval reachability is necessary for spread (control arm, RQ1)

The `control_random` arm replicates the baseline exactly except that index
cases are placed uniformly across the Susceptible KG rather than inside the
active retrieval subgraph (single seed, 42; 45/45 injections realised —
the full-KG pool always admits all RS candidates):

| Metric | Control (random placement) | Baseline (active placement) |
|---|---|---|
| Propagated | **0** | 17.8 ± 4.0 |
| Cumulative exposed | **0** | 65.3 ± 8.3 |
| Probe contamination (step 10) | **0.933** (probe_original = 0/45) | 0.717 ± 0.113 |
| Detection AUROC | **0.488** | 0.899 ± 0.007 |

Three findings follow:

1. **Reachability is effectively necessary for spread.** Agent working
   contexts contained a contaminated fact in 0 of 8 passages at every step;
   the errors sat inert for the whole run. Existence in shared memory is not
   a sufficient condition for cascading.
2. **Persistence and spread are distinct phenomena — and persistence is
   *worse* in sparse regions.** The probe rate *rose* to 0.933: a randomly
   placed error has no competing correct evidence in its neighbourhood, so
   when directly queried it is believed almost every time.
3. **Detectability is a property of the cascade, not the error.** The same
   detector that achieves 0.90 AUROC on baseline runs is at chance (0.488)
   here: its signal comes from propagated agent-written nodes and
   active-subgraph features, not from the seeded modifications themselves.
   The active subgraph is simultaneously the attack surface and the
   detection surface.

Limitation: single seed. The gap to baseline is ~4.5 SD and mechanistically
forced (contexts never sample the sparse region), so replication was
deprioritised; this is noted rather than glossed.

## 5.4 Mitigation: single mechanisms and the full Trio combination (RQ4)

Seed-42 four-arm comparison (identical clean-room state, identical
injections):

| Arm | Propagated | Exposed | Probe (s10) | Quarantined | Quarantine precision | AUROC |
|---|---|---|---|---|---|---|
| baseline | 21 | 62 | 0.667 | 0 | — | 0.891 |
| ablation_floor | 14 | 82 | 0.889 | 0 | — | 0.883 |
| ablation_validation | 26 | 72 | 0.567 | 42 | 0.143 | 0.884 |
| mitigated (full Trio) | **34** | **94** | 0.700 | 67 | **0.104** | 0.855 |

Single-seed reading, hedged against the Section 5.1 envelope: the floor's
spread reduction (14 vs 21) and both single-arm probe effects are *within*
baseline seed noise. Whether the seed-42 full-Trio result (34 propagated,
~4 SD above the baseline mean) generalises is answered by the replication
below.

### 5.4.1 Multi-seed replication of the full-Trio arm (seeds 42–45)

| Seed | Propagated | Exposed | Probe (s10) | AUROC | Quarantined | Quarantine precision |
|---|---|---|---|---|---|---|
| 42 | 34 | 94 | 0.700 | 0.855 | 67 | 0.104 |
| 43 | 6 | 44 | 0.761 | 0.873 | 66 | 0.030 |
| 44 | 10 | 67 | 0.720 | 0.843 | 55 | 0.073 |
| 45 | 10 | 37 | 0.780 | 0.864 | 50 | 0.020 |
| **mean ± SD** | **15.0 ± 12.8** | **60.5 ± 25.7** | **0.740 ± 0.037** | **0.859 ± 0.013** | 59.5 | **0.059 pooled** |
| baseline (n=4) | 17.8 ± 4.0 | 65.3 ± 8.1 | 0.717 ± 0.113 | 0.899 ± 0.007 | 0 | — |

Three statistical conclusions (Welch t and Mann–Whitney U, two-sided,
n = 4 vs 4):

1. **No reliable effect on spread.** Propagated (p = 0.71 / 0.31) and
   exposed (p = 0.74 / 0.69) means are indistinguishable from baseline, and
   probe contamination is likewise flat (p = 0.71). The seed-42
   "superadditive harm" reading is retracted as a point estimate: it is the
   upper tail of the mitigated arm's own distribution, not its centre.
2. **A ~10× variance amplification on spread metrics.** The mitigated arm's
   variance is 10.1× baseline for propagated and 10.0× for exposed
   (F(3,3) two-sided p ≈ 0.09 — suggestive, not conclusive, at n = 4; the
   direction is consistent across both spread metrics and with the
   quasi-random quarantine mechanism). Outcomes range from clearly better
   (6 propagated) to clearly worse (34) than anything baseline produces
   (12–21) under identical injection protocols.
3. **The only statistically significant effect of full Trio is negative:
   it degrades detection.** AUROC drops from 0.899 ± 0.007 to 0.859 ± 0.013
   (Welch p = 0.004; Mann–Whitney p = 0.029, perfect separation — every
   mitigated seed detects worse than every baseline seed). The mechanism is
   confidence laundering: validation passes raise surviving nodes'
   confidence toward 1.0, and quarantine removes mostly-clean nodes, so the
   contaminated nodes that survive sit in a cleaner-looking,
   higher-confidence population than in any unmitigated run.

The mechanism behind the variance is quarantine precision, now measured
across four seeds at **2–10% (pooled 5.9%, 14/238)**: which subtrees get
deprecated is a near-random draw, so run outcomes hinge on whether the
lottery happens to hit contaminated lineages (seed 43) or clean load-bearing
ones whose removal reshapes retrieval toward contaminated neighbours
(seed 42). Cascade deprecation multiplies each mistaken quarantine into the
loss of its whole descendant subtree. Section 5.6 independently measures the
same judge grade at 10% flag precision on a human-calibrated sample — the
validator is the bottleneck, and the architecture faithfully amplifies its
mistakes.

**Restated finding (RQ4, negative result):** with a validator at ~6–10%
quarantine precision, the full Trio stack does not mitigate. It leaves mean
spread unchanged, multiplies outcome variance roughly tenfold, degrades
error detectability — the one effect that replicates cleanly — and is never
dependably better than doing nothing. Provenance-aware retrieval is only as
good as the judgement that feeds it.

A replication note for transparency: an earlier partial run of seed 45
(killed at step 10 before evaluation) produced 12 propagated / 75
quarantined versus the completed run's 10 / 50 — same seed, same clean-room
protocol. The run seed fixes injection placement but not LLM generation, so
residual API nondeterminism contributes to within-configuration variance;
this strengthens rather than undermines the variance finding.

### 5.4.2 The oracle-validator arm: is it the judge or the architecture?

Section 5.4.1 leaves an attribution question open: do the full-Trio
pathologies come from the *architecture* (cascade deprecation amplifying
mistakes) or from the *judge* (6–10% quarantine precision feeding it)? The
oracle arm answers it with a single intervention: a run identical to the
mitigated configuration in every respect except that quarantine decisions
are read from the experimenter's ground-truth labels instead of the Llama-8B
judge. The architecture — targeted audits, quarantine, cascade deprecation,
confidence floor, write-time confidence propagation — is untouched; only
the judgement becomes perfect (and free: zero audit LLM calls).

| Metric | Oracle (seed 42) | Trio, 8B judge (n=4) | Baseline (n=4) |
|---|---|---|---|
| Propagated | 11 | 15.0 ± 12.8 | 17.8 ± 4.0 |
| Cumulative exposed | **44** | 60.5 ± 25.7 | 65.3 ± 8.1 |
| Probe contamination (s0 → s5 → s10) | 0.842 → 0.756 → **0.612** | 0.740 ± 0.037 (s10, flat) | 0.717 ± 0.113 (s10, flat) |
| Detection AUROC | **0.899** | 0.859 ± 0.013 | 0.899 ± 0.007 |
| Quarantined (contam / clean) | 48 (16 / 32) | ~60 (2–10% precision) | 0 |
| Fitted γ | **0.0360** | 0.0080 ± 0.0055 | 0 |
| **R₀ (seed 42)** | **0.79** | 4.46 ± 2.36 | — (γ = 0) |
| **R₀ (n = 4, seeds 42–45)** | **0.97 ± 0.21** (2/4 super-critical) | 4.46 ± 2.36 (4/4) | — (γ = 0) |

> **Retraction (seed replication, `phase42_oracle_s{43,44,45}`).** An
> earlier version of this section reported "R₀ = 0.79 — the only
> sub-critical configuration in this thesis" from the single seed-42 run.
> Replication to n = 4 dissolves that headline exactly as the seed-42
> full-Trio "harm" headline dissolved (§5.4.1): the perfect oracle's R₀ is
> **0.97 ± 0.21 across seeds 42–45 (0.79, 1.096, 1.197, 0.780), with 2 of
> 4 seeds super-critical.** The perfect oracle straddles the epidemic
> threshold like every noisy point (§5.4.4); the 0.79 was a favourable
> draw. The corrected finding is stated below. (Note: oracle seeds 43/44
> fit to R₀ identical to the p75 seeds — the false-alarm-rate difference is
> zero-vs-0.0168 and, at those seeds, never touched the sampled entities;
> §5.4.4's construction-insensitivity effect.)

Findings, in order of strength (corrected for the n = 4 envelope):

1. **Perfect judgement brings R₀ from the LLM judge's 4.46 ± 2.36 down to
   the epidemic threshold (~0.97 ± 0.21), not to comfortable containment.**
   A perfect judge lifts γ by ~4.5× over the 8B judge (0.036 vs 0.008) and
   removes most of the reproduction number — but the destination is R₀ ≈ 1,
   the boundary, with individual seeds landing on either side. The
   architecture *can* move the needle enormously; it cannot, even with a
   flawless judge on this audit budget, drive the cascade reliably
   sub-critical. This is the corrected RQ4 upper bound, and it is a stronger
   result than the retracted one: the ceiling of content-based validation in
   this architecture is *marginal* containment, which motivates the
   provenance-level direction (§5.7c) rather than "just get a better judge".
2. **The probe rate declines over the run (0.84 → 0.61) — no other arm in
   any configuration has ever shown a declining probe rate.** Quarantine
   that actually removes contaminated nodes converts direct probes from
   "contaminated" to "other" (probe_other rose 5 → 18); errors stop being
   *believed* because they stop being *retrievable*. Every other arm's
   probe rate is flat or rising. (Seed-42 figures; the qualitative decline
   is the claim, not the exact endpoint.)
3. **The AUROC degradation vanishes** (0.899, exactly the baseline mean vs
   0.859 under the 8B judge), confirming Section 5.4.1's confidence-
   laundering mechanism as a judge artifact: the oracle never re-scores
   surviving nodes, so nothing gets laundered. (Caveat: the oracle arm's
   AUROC is partially favourable by construction — caught nodes carry
   confidence 0. The claim is not that the oracle detects better, but that
   the *degradation below baseline* disappears with the judge.)
4. **The architecture's residual cost is measurable and modest: 32 clean
   nodes quarantined per 16 contaminated (≈2 : 1 collateral).** All 32 are
   cascade descendants of genuinely contaminated ancestors — exposed but
   uninfected derivations. Under the 8B judge the same architecture removed
   ~9 clean nodes per contaminated one. Perfect judgement does not eliminate
   collateral damage; it caps it at the lineage structure's own
   exposed-but-clean ratio.

**Attribution verdict (RQ4):** judge quality is the dominant factor, not the
Trio architecture — the same stack spans R₀ ≈ 4.5 (LLM judge) to ≈ 1.0
(perfect judge) with no other change. But the corrected upper bound reframes
the ceiling: perfect judgement reaches only the epidemic threshold, so the
dose–response between those endpoints, and specifically WHICH axis of judge
quality (precision vs recall) moves R₀, becomes the decisive question
(Sections 5.4.4 and 5.4.5). (Section 5.4.1's variance
mechanism predicts a noisy middle). Caveats: single seed (42); this run
realised 38 index cases (8/15 RS candidates in the seeding pool); propagated
count (11) alone is *not* distinguishable from the 8B-judge arm's wide
distribution — the sub-critical R₀, the declining probe rate, and the
restored AUROC are the discriminating evidence.

### 5.4.3 Can prompt engineering buy validator precision? (tuned-judge arm)

Sections 5.4.1–5.4.2 bracket the mitigation question between a ~6%-precision
judge (net harm) and a perfect one (sub-critical containment). The practical
question is where achievable improvements land on that axis. The cheapest
intervention — changing the judge's prompt while holding the model, the JSON
contract, and every threshold fixed — was tested offline first, on the 40
human-labeled rows from the judge-calibration study (§5.7b): four prompt
variants targeting the three documented failure modes (specificity mismatch,
world-knowledge leakage, flag-happy default).

| Variant | Flags | Flag precision | Recall (of 2) | False alarms (of 38) |
|---|---|---|---|---|
| v0 original judge | 19 | 0.053 | 1/2 | 18 (47%) |
| v1 quote gate (rules only) | 9 | 0.111 | 1/2 | 8 (21%) |
| **v2 quote-first (structural)** | 13 | **0.154** | **2/2** | 11 (29%) |
| v3 = v2 + base-rate prior | 11 | 0.091 | 1/2 | 10 (26%) |

(Archived in `phase39_validator_tuning.csv`; per-row detail in
`results/raw/`.) The structural fix wins: forcing the judge to produce the
contradicting evidence *before* the verdict (v2) is the only variant that
catches both true errors, at three times the original precision, and it
beats both the rule-only gate (v1 — fewest false alarms, but at half the
recall) and an explicit base-rate prior (v3 — telling the model that >90% of
triplets are faithful helped less than making it look first). Benchmark
caveats: n=40 with only two positives, so recall is measured on n=2; all 40
rows were used for selection (no held-out split at this n), so v2's numbers
are optimistically biased; and the benchmark judges triplets against source
passages, whereas the in-run validator judges against retrieved KG evidence
— the prompt was adapted accordingly (the quote gate becomes an
evidence-quote gate, and absence of evidence is explicitly UNCERTAIN rather
than UNSUPPORTED, which under the 0.4 quarantine threshold is the rule that
stops sparse-evidence pristine nodes from being quarantined).

Offline precision of 0.154 is still an order of magnitude from the oracle
regime, and quarantine precision is base-rate-bound: halving the false-alarm
rate at doubled sensitivity projects to roughly 15–20% in-run precision, up
from the pooled 5.9% but nowhere near the regime the oracle arm shows is
sufficient. The confirmatory test is therefore not this benchmark but a full
mitigated rerun with the tuned judge.

**The confirmatory run refutes the projection outright** (single seed 42,
labelled as such; archived in `phase39_mitigated_tuned_{manifest,trajectory}`
and `phase39_sir_fit_mitigated_tuned.csv`):

| Metric | Tuned judge (seed 42) | Default judge (n=4) | Oracle (seed 42) | Baseline (n=4) |
|---|---|---|---|---|
| Propagated / exposed | 14 / 63 | 15.0 ± 12.8 / 60.5 ± 25.7 | 11 / 44 | 17.8 ± 4.0 / 65.3 ± 8.1 |
| Quarantined (contam / clean) | 27 (**0** / 27) | ~60 (5.9% pooled precision) | 48 (16 / 32) | 0 |
| Probe contamination (s0 → s10) | 0.850 → 0.796 (flat) | flat | 0.842 → 0.612 (declining) | flat |
| Detection AUROC | **0.804** | 0.859 ± 0.013 | 0.899 | 0.899 ± 0.007 |
| Fitted γ / R₀ | **0.0000** / undefined | 0.0080 / 4.46 ± 2.36 | 0.0360 / 0.79 | 0 / — |

The tuned judge did exactly what it was instructed to do — quarantine volume
collapsed from ~60 to 27 nodes and the flag-happy quarantining of pristine
nodes stopped (steps 1–5 quarantined nothing) — and in doing so it caught
*zero* contaminated nodes. In-run quarantine precision fell from 5.9% to
0/27, γ fell to exactly 0, and the arm became epidemiologically equivalent
to running no validation at all, while retaining the architecture's costs:
all 27 quarantined nodes were clean collateral, and detection AUROC fell to
0.804 — below even the default judge's 0.859 (≈ 13 baseline SD below the
0.899 envelope, though single-seed). The laundering mechanism intensified:
a judge that near-always answers SUPPORTED re-scores nearly every audited
survivor (contaminated ones included) to confidence 1.0, while the only
confidence-0 nodes it produces are clean — actively inverting the
detection signal.

The mechanism is structural, and it is the section's finding. The offline
benchmark judges a triplet against its *source passage*, where contradicting
text exists to be quoted. The in-run validator judges a triplet against
*retrieved KG evidence* — and a contaminated node is typically the only
assertion of its "fact" in the graph, because the corruption replaced the
ground truth rather than coexisting with it. There is no contradicting
evidence line to quote, so an evidence-gated judge can never fire on real
contamination; the default judge caught its few true positives only *by*
being flag-happy. Contradiction-gating therefore removes the false-alarm
mass and the accidental true positives together: offline flag precision and
in-run quarantine precision are not the same quantity, and optimising the
first drove the second to zero.

**Consequence for RQ4:** prompt engineering on the same 8B judge does not
move validator quality along the precision axis the oracle identified — it
trades one failure mode (indiscriminate flagging) for another (structural
blindness). Self-consistency checking against the contaminated memory
itself cannot detect contamination that arrived by replacement; detection
needs an information channel the KG does not contain (source passages,
provenance verdicts, or ground truth). This elevates a controlled precision
sweep — an oracle validator with dialled-in sensitivity and false-alarm
rates — from robustness check to the primary dose–response evidence
(Section 5.4.4), and it independently corroborates the
Section 5.7c conclusion that provenance-level defences, not content
validation, are the viable direction.

### 5.4.4 The noisy-oracle precision sweep: recall raises the containment floor, but is not a hard guarantee

Section 5.4.3 leaves the dose–response curve between ~6% and 100%
validator precision unmeasured by any real judge — no achievable prompt
change reaches it. This section measures the curve directly, holding the
architecture and the judge's *recall* fixed at the oracle's ceiling
(`oracle_sensitivity = 1.0`: every genuinely contaminated audited node is
flagged) while inducing false positives at a controlled rate
(`oracle_false_alarm`), so that only *precision* varies. A false positive
receives the identical quarantine + cascade treatment a real judge's false
positive would — the same collateral-damage channel, at a dialled-in rate
(Section 4.3.3's noisy-oracle mechanism; `experiments/configs/
contamination_oracle_p{75,50,25,10}.yaml`). Target audit-level precision
was derived from the perfect-oracle run's measured audited-candidate
contamination prevalence (4.8%; `phase38_oracle`), not assumed; realized
final precision (`det_R_contam / (det_R_contam + det_R_clean)`, cascade
collateral included — the same definition used everywhere else in this
chapter) is what is reported below, and it is consistently lower than the
design target because cascade deprecation dilutes precision beyond the
audit-level flag rate.

**The investigation went through three rounds of retraction before landing
on a stable reading — all are kept in the record rather than only
reporting the final table** (thesis discipline rule 5): a first pass across
four precision points (p75/p50/p25/p10, single seed 42 each) suggested a
monotone R₀-vs-precision relationship; adding a p10 seed replicate
immediately broke that monotonicity (p10's R₀ came in *below* p25's despite
lower precision) and the trend claim was withdrawn the same session. A
second pass, noting that all five single-seed points (p75/p50/p25/p10 plus
the perfect oracle) were sub-critical despite realized precision spanning a
>5× range, proposed a stronger claim — that perfect recall makes
containment robustly precision-independent. Further p10 seed replicates
(43–45, chosen because p10 is closest to the LLM-judge arms' realized
precision) refuted that too: one of the four seeds (44) came back
*super-critical* (R₀ = 1.105). A third pass then replicated p75 — the
*highest*-precision sweep point, whose single seed had looked most
comfortably sub-critical (0.699) — and then p50, to check whether
higher-precision points were more stable than p10. They were not: p75's
seeds 43 and 44 were *both* super-critical (1.096, 1.197; n=4 mean 0.928 ±
0.256, 2/4 super-critical); p50 landed closer to p10 (n=4 mean 0.870 ±
0.173, 1/4 super-critical, seed 44 again).

**Final table, three of four sweep points now n=4**
(`phase40_oracle_noisy_p{75,50,25,10}_*`,
`phase40_sir_fit_oracle_noisy_p{75,50,25,10}[_s{43,44,45}].csv`):

| Arm | Realized precision | n | R₀ (mean ± SD) | Super-critical seeds |
|---|---|---|---|---|
| p50 (noisy oracle) | 20.2% | **4** | **0.870 ± 0.173** | 1/4 |
| p10 (noisy oracle) | 6.6–9.1% | **4** | **0.911 ± 0.158** | 1/4 |
| p75 (noisy oracle) | 26.2% | **4** | **0.928 ± 0.256** | 2/4 |
| p25 (noisy oracle) | 10.5% | 1 | 0.823 | — |
| oracle, perfect (§5.4.2) | 33.3% | 1 | 0.79 | — |
| mitigated, 8B judge (§5.4.1) | 5.9% pooled | 4 | 4.46 ± 2.36 | 4/4 |
| mitigated_tuned, 8B judge (§5.4.3) | 0% | 1 | undefined (γ = 0) | — |

**A construction-level caveat, discovered while cross-checking the fits
for a possible bug, changes how this table should be read.** Comparing
`phase40_oracle_noisy_p50_s44_trajectory.csv` against
`phase40_oracle_noisy_p10_s44_trajectory.csv` — same seed, different
sweep point — their fitted (β, γ, R₀) came back numerically identical to
13 significant figures, despite the two trajectory files genuinely
differing in every quarantine-related column (`quarantined`, `cascaded`,
final `det_R_clean` 55 vs. 241). A `diff` against `phase40_oracle_noisy_
p75_s45_trajectory.csv` and `..._p50_s45_...` found the same exact-match
pattern at seed 45. The cause is structural, not a bug: `fit_sir.py`'s
epidemic-curve reconstruction (§3.4, §4.6.4) uses only `gt_total` and
`det_R_contam` — **`det_R_clean`, the column the `oracle_false_alarm` knob
actually drives, never enters the reconstruction.** Two noisy-oracle
configs sharing a seed and `oracle_sensitivity = 1.0` will therefore fit
to *identical* R₀ whenever their induced false alarms happen not to touch
the handful of entities (12 per step) the pipeline actively samples for
extraction that run — which, at the lower false-alarm rates in this
sweep (p75: 1.68%, p50: 5.04%), turned out to happen often. (It is not a
universal identity: p75 seed 44 and p10 seed 44 — same seed, same
sensitivity — produced *different* R₀, 1.197 vs. 1.105, because that
seed's collateral damage did happen to intersect the sampled entities.)

**Consequence for the reading below: recall enters the R₀ calculation
directly, through `det_R_contam`; precision (via induced false alarms)
only reaches R₀ indirectly, through an inconsistent retrieval-feedback
path that this design frequently fails to exercise.** The tight clustering
of all three n=4 points in a 0.87–0.93 mean band despite a 4× precision
spread is therefore not unambiguous evidence that precision is causally
inert for containment — part of it is that this experimental design's R₀
metric has limited *sensitivity* to precision by construction. A cleaner
test would use a metric that is a direct function of `det_R_clean`, or
redraw induced false alarms from the actively-retrieved pool rather than
the full audit-candidate pool to guarantee retrieval feedback; neither was
undertaken here (time-boxed against the 2026-07-31 implementation
deadline).

**Reading, revised with the caveat in place.** What survives the caveat:
recall is doing large, unambiguous work. Every noisy-oracle point's mean
sits at 0.7–0.93 and no noisy-oracle seed (12 runs total across the three
replicated points) has approached the LLM-judge arms' 4.46 ± 2.36 (all 4
*their* seeds badly super-critical; §5.4.1) — recall is the one parameter
that differs between the noisy-oracle family and the LLM-judge arms
(perfect vs. structurally blind to replacement-type contamination,
§5.4.3), and that difference alone separates comfortably-contained from
badly-uncontained outcomes. What does NOT survive the caveat as a clean
empirical claim: that precision is irrelevant once recall is saturated.
The sweep is consistent with that hypothesis but cannot distinguish it
from "this R₀ metric mostly can't see the precision knob" — both predict
the observed clustering. **Recall raises the containment floor, and is
not a hard per-run guarantee (roughly a third of replicated runs crossed
the threshold regardless of precision); whether precision provides any
*additional* margin beyond perfect recall remains open**, pending either a
redesigned noisy-oracle mechanism or a metric that is directly sensitive
to collateral damage. What is not in question is `det_R_clean` itself:
false alarms visibly and monotonically increase collateral quarantine of
clean facts (32 at the perfect oracle → 253 at p10), so precision still
matters for the architecture's cost, independent of this R₀-sensitivity
question.

`[PHASE-4]` p25 remains single-seed. Given the construction-insensitivity
finding, replicating it to n=4 would likely reproduce the same clustering
without resolving the open question above — a redesigned false-alarm
mechanism (drawn from the retrieved pool) is the higher-value next step
if RQ4's precision-vs-recall attribution needs to be sharpened further.

### 5.4.5 The recall dose–response: the clean axis the precision sweep could not measure

Section 5.4.4 left one question open by construction: the precision sweep
could not cleanly move R₀ because its knob (`oracle_false_alarm`) drives
only `det_R_clean`, which the SIR reconstruction excludes. The complementary
sweep closes it. Here recall is varied (`oracle_sensitivity` ∈ {0.25, 0.50,
0.75, 1.0}) with false alarms held at zero, so the only thing changing is
the probability that a genuinely contaminated audited node is caught — which
feeds `det_R_contam` and therefore γ *directly*
(`experiments/configs/contamination_oracle_sens{25,50,75}.yaml`;
`phase42_oracle_sens*`).

Across four seeds (42–45) at each sensitivity, false alarms held at zero so
the recall axis is clean (`phase42_oracle_sens*`; the perfect-recall row is
the §5.4.2 oracle n = 4):

| Sensitivity (recall) | mean γ | mean R₀ ± SD | super-crit | R₀ per seed (42/43/44/45) |
|---|---|---|---|---|
| 1.00 (perfect) | 0.0375 | **0.97 ± 0.21** | 2/4 | 0.79 / 1.10 / 1.20 / 0.78 |
| 0.75 | 0.0291 | **1.45 ± 0.53** | 3/4 | 0.83 / 1.19 / 1.95 / 1.83 |
| 0.50 | 0.0223 | **1.87 ± 0.62** | 3/4 | 0.95 / 2.09 / 2.15 / 2.30 |
| 0.25 | 0.0138 | **3.78 ± 1.86** | 4/4 | 1.07 / 5.13 / 4.12 / 4.81 |

**R₀ rises monotonically in the mean as recall falls — from ~1.0 at perfect
recall to ~3.8 at 25% recall — and the trend is statistically supported:
Spearman ρ(sensitivity, R₀) = −0.67 (p = 0.005, n = 16 runs).** Mean γ
declines in lockstep (0.038 → 0.029 → 0.022 → 0.014), which is the
mechanism: the recall knob determines which contaminated nodes are caught,
so it moves `det_R_contam` and therefore γ *directly*, and R₀ = β/γ climbs.
This is the dose–response the precision sweep (§5.4.4) structurally could
not produce — there the knob moved only the excluded `det_R_clean`.
**Recall is the causal containment lever; precision governs collateral cost,
not the reproduction number.** (Adjacent sensitivity levels do not each
separate individually — the seed-42 draw is consistently the lowest at
every level, so 4-vs-4 rank tests sit at p = 0.20 — but the trend across the
full axis is unambiguous and significant; per-level SD inflates toward low
recall because a near-zero γ makes β/γ variance explode.)

**The dose–response extrapolates cleanly into the LLM-judge arms, closing
the loop.** The 8B judge's realized in-run recall, measured directly from
the archived trajectories (`phase41_judge_recall.csv`; end-of-run
`det_R_contam / gt_total`), is **6.0 ± 3.5% (default prompt, n = 4) and 0%
(tuned prompt)** — far below the lowest swept sensitivity (0.25). That
sensitivity-0.25 point already reaches R₀ = 3.78, adjacent to the mitigated
arm's independently-fitted 4.46 ± 2.36 (§5.4.1). So the LLM-judge failure
is not a separate phenomenon needing its own explanation: the judge arms
sit at the bottom of this recall axis, exactly where the oracle
dose–response predicts super-critical R₀, and the §5.4.3 prompt-tuning
attempt failed because it moved precision while leaving recall pinned near
zero. The whole RQ4 result collapses onto one axis: **validator recall sets
the reproduction number; precision, prompt, and the cascade architecture
are all second-order.**

## 5.5 Epidemiological fit and R₀

Fitting the discrete SIR model to the empirical trajectories
(reconstructed I(t), R(t); Section 3.4):

| Arm | β | γ | R₀ | Fit RMSE |
|---|---|---|---|---|
| baseline (4 seeds) | 0.0437 ± 0.0101 | 0 | — (eff. repro 0.044/step) | 1.4–5.2 |
| ablation_floor | 0.0289 | 0 | — | 1.4 |
| ablation_validation | 0.0474 | 0.0066 | **7.19** | 1.5 |
| mitigated (4 seeds) | 0.0327 ± 0.0259 | 0.0080 ± 0.0055 | **4.46 ± 2.36** (range 2.4–7.6) | 0.5–1.6 |
| mitigated_tuned (Section 5.4.3) | 0.0323 | **0.0000** | undefined (γ = 0; eff. repro 0.032/step) | 1.1 |
| oracle, perfect (§5.4.2, seed 42) | 0.0283 | 0.0360 | 0.79 | 2.3 |
| oracle, perfect (§5.4.2, 4 seeds) | 0.0364 ± 0.0095 | 0.0375 ± 0.0015 | **0.97 ± 0.21** (2/4 super-crit) | 1.1–1.8 |
| oracle recall 0.75 (§5.4.5, 4 seeds) | 0.0388 ± 0.0107 | 0.0291 ± 0.0100 | **1.45 ± 0.53** | 0.9–1.9 |
| oracle recall 0.50 (§5.4.5, 4 seeds) | 0.0382 ± 0.0107 | 0.0223 ± 0.0085 | **1.87 ± 0.62** | 1.1–2.0 |
| oracle recall 0.25 (§5.4.5, 4 seeds) | 0.0377 ± 0.0095 | 0.0138 ± 0.0103 | **3.78 ± 1.86** | 1.0–5.1 |
| oracle_noisy_p75 (§5.4.4, 4 seeds) | 0.0376 ± 0.0084 | 0.0410 ± 0.0036 | **0.928 ± 0.256** | 1.09–1.77 |
| oracle_noisy_p50 (§5.4.4, 4 seeds) | 0.0393 ± 0.0089 | 0.0450 ± 0.0050 | **0.870 ± 0.173** | 1.09–2.01 |
| oracle_noisy_p25 (§5.4.4, n=1) | 0.0358 | 0.0436 | 0.823 | 1.40 |
| oracle_noisy_p10 (§5.4.4, 4 seeds) | 0.0413 ± 0.0087 | 0.0454 ± 0.0056 | **0.911 ± 0.158** | 1.24–1.79 |

Where validation runs with the 8B judge, R₀ lands at 2.4–7.6 — always well
above the containment threshold (R₀ < 1). The oracle arm is the exception
that proves the mechanism: perfect quarantine decisions raise γ ~4.5× and
bring R₀ to 0.79, the only sub-critical configuration observed. The tuned
arm is the degenerate case: its judge quarantined zero contaminated nodes,
so γ = 0 exactly — the recovery channel does not exist and the arm is
epidemiologically identical to running no validation at all (β matches the
mitigated mean; single seed). The multi-seed fit dissolves the
single-seed β story in the same way Section 5.4.1 dissolves the harm story:
seed 42's β of 0.0703 (~2.6 SD above baseline) sits next to seed 43's
0.0110, and the mitigated β mean (0.0327 ± 0.0259) is statistically
indistinguishable from baseline while carrying ~6.6× the variance. The full
Trio does not shift the transmission rate; it destabilises it. The floor arm
shows the intended β suppression (0.0289) but no γ (single seed).

The noisy-oracle sweep rows (Section 5.4.4 has the full precision-vs-R₀
narrative and its two retractions) show a materially smaller β/γ range than
either the 8B-judge arms or the baseline's own multi-seed spread — the
`oracle_noisy_p10` β SD (0.0087) is roughly a third of the mitigated arm's
(0.0259) on a comparable γ SD (0.0056 vs. 0.0055), yet still carries R₀
across the 1.0 threshold once. Fit RMSE for the noisy-oracle
arms (1.2–1.8) is comparable to the other single-seed arms and does not
flag these fits as unusually poor.

Scale caveat: with N ≈ 50,000 and |I| < 100, S never depletes; the SIR model
cannot reproduce late-trajectory plateaus, and the fits (RMSE up to ~5 nodes)
should be read as rate estimates, not full trajectory models.

`[FIG] Empirical vs fitted I(t) per arm; R₀ bar chart with the R₀=1 line.`

## 5.6 Error-type ranking (RQ2)

Model-free reproduction per index case, baseline arm (4 seeds):

| Error type | Reproduction/seed (mean ± SD) | Share of transmissions |
|---|---|---|
| Entity Disambiguation | **0.63 ± 0.27** | 51% |
| Qualifier Loss | 0.50 ± 0.04 | 44% |
| Relation Strengthening | 0.08 ± 0.05 | 5% |

ED and QL propagate; RS barely does. Under *both* validation-bearing arms,
ED becomes supercritical (1.4 transmissions per seed — 21 transmissions from
15 index cases on seed 42), meaning validation not only failed to contain
the most harmful type but coincided with its amplification. RS results carry
the 9–10/15 realised-seed caveat (Section 3.3).

## 5.7 How contaminated is the pipeline naturally? (RQ1 base rate)

Three instruments, layered (Section 3.8):

**(a) Fidelity audit, uncorrected.** The Llama-8B judge flagged 93/783
extraction-written triplets (11.9%): 56 ENTITY, 32 UNSUPPORTED, 5 RELATION,
0 QUALIFIER_LOSS, with FEVER-derived triplets flagged at 40.4% vs HotpotQA's
10.1%.

**(b) Human calibration overturns (a).** Blind labelling of 40 stratified
rows against the source passages measured the judge's flag precision at
**10% (2/20)** — ENTITY 0/10 confirmed, UNSUPPORTED 1/5, RELATION 1/5 (a
census of all RELATION flags; the single real one is actually a qualifier
loss, confirming the judge is QL-insensitive rather than QL being absent).
All 20 judge-SUPPORTED rows were clean. Extrapolating per-category precision
across the 93 flags leaves ≈7 true errors:

> **Corrected natural fidelity-error rate ≈ 0.9%** (wide CI; naive estimate
> 11.9% — off by an order of magnitude).

The FEVER-vs-HotpotQA gap is retracted as a judge artifact: 6/6 sampled
FEVER flags were false alarms in which the judge penalised world-false but
faithfully extracted claims — world-knowledge leakage into a fidelity task,
despite explicit prompt instruction against it. The judge's 10% flag
precision independently corroborates the 10–14% quarantine precision of the
same-grade ValidationAgent in Section 5.4.

**(c) The truth channel (ground truth, no LLM).** Mapping every FEVER-derived
triplet to its claim's FEVER verdict: **9 known-false triplets** sit in the
KG as facts (from 8 REFUTED claims); 26 more derive from unverifiable (NEI)
claims. As a share of all extraction-written triplets: ~1.2% known-false and
~3.3% unverifiable — the truth channel *dominates* the corrected fidelity
channel (~0.9%), and it is invisible to any fidelity validator by
construction, since faithful extraction of a false claim is exactly what
fidelity endorses.

A secondary finding: the extractor partially self-censors on false content.
REFUTED claims yielded triplets in 8/18 units versus 27/32 for
SUPPORTS/NEI (0.50 vs 1.09–1.24 triplets/unit; Fisher exact p = 0.0085,
OR = 0.15, small n). The same world-knowledge leakage that breaks the judge
as a fidelity instrument acts as a partial defence at extraction time.

**Synthesis for RQ1.** Natural, non-adversarial contamination enters at a
few percent (mostly via ingestion of false/unverifiable source content, not
extraction infidelity), persists indefinitely once written (Section 5.3
probes), and cascades only where it is retrieval-reachable — where it
reproduces at R₀ ≫ 1 against a validator that cannot reliably distinguish
contaminated from clean nodes.

## 5.8 Statistical treatment

Given n = 4 seeds per arm, the analysis reports means ± SD with explicit
range, treats <2 SD single-run differences as within noise, and uses exact
tests where applicable (Fisher exact for the self-censoring contrast). For
the baseline-vs-mitigated comparison (n = 4 vs 4), *both* Welch t and
Mann–Whitney U are reported: the mitigated arm's ~10× variance ratio
violates equal-variance assumptions (hence Welch), and n = 4 is small enough
that the rank test serves as a robustness check — the two agree on every
metric (both null for spread and probe; both significant for AUROC, where
Mann–Whitney's p = 0.029 is the smallest value attainable at this n, i.e.
perfect separation). Variance amplification is reported with a two-sided
F(3,3) test and flagged as suggestive (p ≈ 0.09) rather than conclusive,
since n = 4 gives the F test very little power; the claim rests on the
consistency of the direction across both spread metrics and the mechanism.
All claims flagged as single-seed are labelled as such in text.

## 5.9 Contamination velocity and reach under graph conditions (RQ3)

RQ3 asks how three operational knobs — memory write frequency, retrieval
density, and seed reachability — move contamination *velocity* (the SIR
transmission rate β) and *reach* (cumulative exposure). Each knob is a
single-parameter diff against the seed-42 baseline on the unmitigated
substrate (γ = 0, no validator), so β is isolated from any recovery channel.
Graph density is treated separately in Section 5.9.4 because it is a
load-stage property, not a run parameter.

Every arm is replicated to **n=4 (seeds 42–45)**; the per-axis n=4 tables and
tests are in §5.9.1–5.9.4 and `phase45_rq3_replication_n4.csv`. The primary
velocity measure is the **model-free reproduction per index case**
(propagated ÷ seeded, as in Section 5.6), read against the 4-seed baseline
envelope (0.452 ± 0.088 reproduction; β 0.0437 ± 0.0087; Sections 5.1, 5.5);
the fitted β is reported alongside as SIR-consistent corroboration. The
seed-42 pass (below) is retained for the reach columns (propagated, exposed,
probe) it uniquely reports — but its single-seed reproduction/β values are
superseded by the n=4 means in the subsections, and two of them (wf24 β,
structural density) proved to be seed-42 tail values (§5.9.2, §5.9.4).

| Arm (seed 42) | knob | Propagated | Exposed | Reproduction | β | Probe (s10) | AUROC |
|---|---|---|---|---|---|---|---|
| khop1 | seed 1 hop out | **0** | **0** | **0.000** | 0.0000 | 0.677 | 0.485 |
| khop2 | seed 2 hops out | **0** | **0** | **0.000** | 0.0000 | 0.886 | 0.491 |
| khop3 | seed 3 hops out | **0** | **0** | **0.000** | 0.0000 | 0.750 | 0.490 |
| wf6 | writes ÷2 (eps 6) | 7 | 36 | 0.175 | 0.0193 | 0.809 | 0.879 |
| rd3 | retrieval 3 | 10 | 32 | 0.250 | 0.0259 | 0.800 | 0.890 |
| **baseline** | eps 12, ctx 5, k 0 | 21 | 62 | 0.538 | 0.0550 | 0.667 | 0.891 |
| wf24 | writes ×2 (eps 24) | 27 | 143 | 0.675 | 0.0557 | 0.650 | 0.915 |
| rd10 | retrieval 10 | 28 | 116 | 0.700 | 0.0626 | 0.650 | 0.913 |

Archived: `results/summaries/phase43_rq3_sir_fit.csv` (seed 42),
`phase45_rq3_replication_n4.csv` (n=4); trajectories in
`results/raw/contamination_{arm}[_s43..45]_*`.

### 5.9.1 Reachability is a hard threshold, not a gradient (k-hop)

The k-hop arms place index cases an exact BFS distance k from the active
retrieval subgraph, intended as a graded relaxation of the Section 5.3 binary
control. Empirically there is no gradient: **at k = 1, 2, and 3 alike,
propagation and exposure are exactly zero — across all four seeds (42–45)**,
and the mechanism is confirmed directly: the count of contaminated facts
served into any agent context across all ten steps is 0 in every one of the
twelve runs. This settles the one boundary question the graded design raised —
whether a k=1 seed, sitting exactly one hop out, might be pulled in as the
active subgraph grows over the run. It is not, on any seed. A seed one hop
outside the retrieval horizon is as inert as one placed randomly across the
whole KG (Section 5.3). Reachability is therefore a step function at the
retrieval boundary, not a distance-decaying quantity: the retrieved set, not
graph proximity to it, determines whether an error can transmit. All twelve
AUROC values sit at chance (~0.49), reproducing the Section 5.3 finding that
detectability is a property of the cascade rather than of the seeded node —
with no cascade, the detector has no signal — now shown seed-robustly across
three placements.

### 5.9.2 Write frequency: a monotone increase in both velocity and reach (n=4)

Each level replicated to n=4 (seeds 42–45; `phase45_rq3_replication_n4.csv`).
Reproduction is monotone and cleanly separated at both ends:

| entities/step | Reproduction (n=4) | β (n=4) |
|---|---|---|
| wf6 (÷2) | 0.176 ± 0.051 | 0.0161 ± 0.0047 |
| baseline | 0.452 ± 0.088 | 0.0437 ± 0.0087 |
| wf24 (×2) | 0.915 ± 0.209 | 0.0688 ± 0.0092 |

Neither adjacent pair's reproduction distributions overlap (wf6 max 0.25 <
baseline min 0.308; baseline max 0.538 < wf24 min 0.675), and β rises
monotonically 0.016 → 0.044 → 0.069 (wf24 is ~2.9 baseline-SD above). Write
frequency raises *both* the per-contact transmission rate and total reach.

**Retraction (single-seed → n=4; discipline rule 5).** The seed-42-only
analysis reported here in an earlier draft claimed write-frequency *velocity
saturates* above baseline — that seed's wf24 β (0.056) sat flat against
baseline (0.055) while only reach climbed. The n=4 fit dissolves that
saturation: seed 42's flat β was the low tail of the wf24 β distribution
(0.056 vs the 0.069 mean), and across four seeds β increases monotonically.
The "velocity saturates, reach climbs" story does not survive replication and
is withdrawn; the honest result is a monotone dose–response in both
estimators. wf24's seed-44 run reaches reproduction 1.24 (super-critical),
consistent with the seed-44 super-criticality seen across arms (§5.4.1) and
the source of the wider wf24 SD.

### 5.9.3 Retrieval density: the clean monotone dose–response (n=4)

Retrieval density (context_limit, the number of KG facts served per
synthesis/extraction unit) is the cleanest and best-replicated of the three
knobs, monotone in *both* estimators at n=4:

| context_limit | Reproduction (n=4) | β (n=4) |
|---|---|---|
| rd3 = 3 | 0.277 ± 0.070 | 0.0252 ± 0.0041 |
| baseline = 5 | 0.452 ± 0.088 | 0.0437 ± 0.0087 |
| rd10 = 10 | 0.743 ± 0.139 | 0.0589 ± 0.0110 |

The extreme contrast is statistically supported despite n=4: rd3 vs rd10 on
reproduction gives Welch t p=0.005 and Mann–Whitney U p=0.029 (the smallest
value attainable at this n, i.e. perfect rank separation; both tests per
discipline rule 4). More facts retrieved per unit means more opportunities to
pull a contaminated fact into a working context, and the effect does not
saturate across the tested range. This is the operationalization of "density"
that behaves as RQ3's hypothesis expects — and, as the next subsection shows,
it is the *only* density axis whose effect survives replication.

### 5.9.4 Structural graph density: no effect that survives replication

Structural density — mean entity degree, manipulated at load time via
`--density` (`src/graph/density.py`) — was intended to span 0.5× to 2.0× the
baseline. It cannot, on this KG. The loaded T-REx graph has mean entity
degree **1.66** (median 1.0, p90 2.0): it is a near-forest, so sparsification
is blocked almost immediately by the coverage-preservation rule (nearly every
triplet is some entity's only triplet) and densification by restriction runs
out of hub concentration. The realized achievable range is hard-capped at
**[0.86×, 1.26×]** regardless of the requested factor (any request ≤ 0.7
realizes 0.86, any ≥ 2.0 realizes 1.26; the live `--density 0.5` load realized
0.8611, matching the offline figure exactly).

Over that narrow achievable range, and at n=4 (seeds 42–45), there is **no
structural-density effect distinguishable from noise:**

| Structural density | Mean degree | Reproduction (n=4) | β (n=4) |
|---|---|---|---|
| density 0.5 (realized 0.86×) | 1.43 | 0.517 ± 0.212 | 0.0450 ± 0.0168 |
| baseline (1.00×) | 1.66 | 0.452 ± 0.088 | 0.0437 ± 0.0087 |
| density 2.0 (realized 1.26×) | 2.10 | 0.375 ± 0.153 | 0.0325 ± 0.0125 |

The means trend weakly inverse, but every pairwise test is null: sparse vs
dense Welch t p=0.384 / Mann–Whitney U p=0.686; sparse vs baseline p=0.65 /
0.69; dense vs baseline p=0.48 / 0.69. The sparse–dense reproduction gap is
1.6 baseline SD — inside the 2-SD noise band (discipline rule 3). Archived:
`results/summaries/phase45_rq3_replication_n4.csv`.

**Retraction (single-seed → n=4; discipline rule 5).** An earlier draft of
this subsection reported a *large inverse* structural-density effect — "denser
graphs suppress contamination, sparser graphs amplify it," a ~6× reproduction
swing (0.842 → 0.135) with both endpoints >3 baseline-SD out — and built a
mechanistic account of the two density knobs as a "matched pair" moving β in
opposite directions through the retrieval bottleneck. That entire finding
rested on seed 42, which turns out to be the extreme of *both* replication
distributions: seed 42's sparse reproduction (0.842) is the maximum of
[0.842, 0.568, 0.316, 0.342] and its dense value (0.135) is the minimum of
[0.135, 0.526, 0.351, 0.486]. Seeds 43–45 sit near or across baseline in both
arms. The dramatic swing was seed noise amplified by the two endpoints landing
at opposite tails. The inverse effect, its 6× magnitude, and the "matched
pair" mechanism are all **withdrawn**; the replicated result is a null over
the achievable range.

The dilution intuition (a contaminated fact competes with more clean facts in
a denser neighbourhood) may still be directionally correct — the means do lean
that way — but it is not supported at the density contrast this KG permits,
and it is emphatically *not* the large effect seed 42 suggested. Testing it
would require a source graph dense enough to push structural density well
beyond 1.26×, which T-REx cannot provide. The clean density result RQ3 does
establish is the **retrieval**-density axis (§5.9.3), which is robust at n=4;
the structural axis is reported here as a bounded null with its retraction
recorded.

### 5.9.5 Scope and limitations

Every arm in this section was replicated to **n=4 (seeds 42–45)**;
`phase45_rq3_replication_n4.csv` holds the per-arm reproduction and β with SD.
The replication was decisive in both directions. It **confirmed** the
write-frequency and retrieval-density dose–responses (both monotone in
reproduction *and* β, with the retrieval-density extreme reaching Welch
p=0.005 / MWU p=0.029) and the k-hop hard-threshold null (β=0 at every
distance, all four seeds; §5.9.1). It **overturned** two single-seed claims,
both now retracted in place (rule 5): write-frequency β "saturation" (§5.9.2,
in fact monotone at n=4) and the large inverse structural-density effect
(§5.9.4, in fact a null over the achievable range). Both over-claims traced to
seed 42 sitting at a distribution tail — the precise failure mode the
single-seed discipline rules exist to catch, here caught before the claims
entered the thesis as headlines.

The replication runs were executed Groq-free (`--no-eval`); the SIR/reach/β
metrics do not depend on the task-eval or probe path, so the probe (§5.9's
persistence column) remains n=1 for the replication seeds and is reported at
seed 42 only — a deliberate, cost-motivated omission, not a gap in the
dose–response evidence. The validation-interval component of RQ3 (audit
cadence) is addressed epidemiologically through the γ-bearing arms of
Section 5.4 rather than as a separate β-substrate sweep; a dedicated
audit-cadence axis is noted as deferred.
