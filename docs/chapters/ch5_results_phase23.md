# Chapter 5 — Evaluation & Results (Phase 2–3 sections)

> **Draft status (2026-07-09):** covers all completed Phase 2–3 experiments.
> `[PENDING-#14]` marks the mitigated multi-seed replication in flight;
> Section 5.4's conclusions are provisional until it lands. Phase 4 (RQ3
> sweeps) sections are not yet drafted. Figures marked `[FIG]`.

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
baseline seed noise. The full-Trio result is not: 34 propagated is ~4 SD
above the baseline mean, and 94 exposed ~3.5 SD. On seed 42, the full
combination is superadditively harmful — worse than either mechanism alone
and worse than doing nothing.

The mechanism is quarantine precision. Only 10–14% of quarantined nodes were
actually contaminated; the rest were clean nodes removed from retrieval,
whose absence reshaped retrieval toward remaining (disproportionately
contaminated) neighbours, while cascade deprecation amplified each mistaken
quarantine into the removal of its whole descendant subtree. Section 5.6
independently measures the same judge grade at 10% flag precision on a
human-calibrated sample — the validator is the bottleneck, and the
architecture faithfully amplifies its mistakes.

`[PENDING-#14]` Multi-seed replication of the mitigated arm (seeds 43–45) is
in flight. The first replicate (seed 43) produced 6 propagated / 44 exposed —
*below* the baseline mean — indicating that the mitigated arm's outcome
variance is large and the seed-42 harm result may not be robust as a point
estimate. If the remaining seeds confirm high variance, the claim will be
restated as: **a low-precision validator makes mitigation outcomes
high-variance and unreliable — sometimes harmful, never dependably better
than baseline** — which is consistent with the quasi-random quarantine
mechanism and remains a negative result for the full-Trio configuration.
This section will be finalised when the batch completes.

## 5.5 Epidemiological fit and R₀

Fitting the discrete SIR model to the empirical trajectories
(reconstructed I(t), R(t); Section 3.4):

| Arm | β | γ | R₀ | Fit RMSE |
|---|---|---|---|---|
| baseline (4 seeds) | 0.0437 ± 0.0101 | 0 | — (eff. repro 0.044/step) | 1.4–5.2 |
| ablation_floor | 0.0289 | 0 | — | 1.4 |
| ablation_validation | 0.0474 | 0.0066 | **7.19** | 1.5 |
| mitigated | 0.0703 | 0.0143 | **4.92** | 1.6 |

Where validation gives a non-zero γ, R₀ lands at 5–7 — an order of magnitude
above the containment threshold (R₀ < 1). Notably, the mitigated arm's
fitted β (0.0703) is ~2.6 SD above the baseline mean: on seed 42 the full
Trio *raised* the transmission rate, consistent with Section 5.4's account.
The floor arm shows the intended β suppression (0.0289) but no γ.

Scale caveat: with N ≈ 50,000 and |I| < 100, S never depletes; the SIR model
cannot reproduce late-trajectory plateaus, and the fits (RMSE up to ~5 nodes)
should be read as rate estimates, not full trajectory models.
`[PENDING-#14]` mitigated multi-seed will put error bars on β_mitigated.

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

Given n = 4 baseline seeds (mitigated n pending), the analysis reports means
± SD with explicit range, treats <2 SD single-run differences as within
noise, uses exact tests where applicable (Fisher exact for the
self-censoring contrast), and reserves formal two-sample tests for the
completed multi-seed pairs `[PENDING-#14: baseline (n=4) vs mitigated (n=4)
comparison — Welch t or Mann-Whitney to be selected after inspecting
mitigated variance]`. All claims flagged as single-seed are labelled as such
in text.
