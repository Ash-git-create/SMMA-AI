# Chapter 5 — Evaluation & Results (Phase 2–3 sections)

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
| **R₀** | **0.79** | 4.46 ± 2.36 | — (γ = 0) |

Findings, in order of strength:

1. **The cascade is contained: R₀ = 0.79 — the only sub-critical
   configuration in this thesis.** A perfect judge lifts γ by ~4.5× over
   the 8B judge (0.036 vs 0.008) and drives the reproduction number below
   the epidemic threshold. The architecture *can* mitigate; nothing about
   cascade deprecation is inherently pathological.
2. **The probe rate declines over the run (0.84 → 0.61) — no other arm in
   any configuration has ever shown a declining probe rate.** Quarantine
   that actually removes contaminated nodes converts direct probes from
   "contaminated" to "other" (probe_other rose 5 → 18); errors stop being
   *believed* because they stop being *retrievable*. Every other arm's
   probe rate is flat or rising.
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

**Attribution verdict (RQ4):** judge precision is the bottleneck, not the
Trio architecture. The same stack spans R₀ ≈ 4.5 (6–10% precision) to
R₀ = 0.79 (100% precision) with no other change — mitigation quality is a
monotone function of validator precision, which motivates measuring the
dose–response curve between those endpoints (Section 5.4.1's variance
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
mitigated rerun with the tuned judge — the middle point of the
dose–response ladder R₀ 4.46 ± 2.36 (default prompt) → [PENDING-#20-RUN:
tuned-prompt R₀, quarantine precision, AUROC, probe trajectory; single
seed 42, to be labelled as such] → 0.79 (oracle).

## 5.5 Epidemiological fit and R₀

Fitting the discrete SIR model to the empirical trajectories
(reconstructed I(t), R(t); Section 3.4):

| Arm | β | γ | R₀ | Fit RMSE |
|---|---|---|---|---|
| baseline (4 seeds) | 0.0437 ± 0.0101 | 0 | — (eff. repro 0.044/step) | 1.4–5.2 |
| ablation_floor | 0.0289 | 0 | — | 1.4 |
| ablation_validation | 0.0474 | 0.0066 | **7.19** | 1.5 |
| mitigated (4 seeds) | 0.0327 ± 0.0259 | 0.0080 ± 0.0055 | **4.46 ± 2.36** (range 2.4–7.6) | 0.5–1.6 |
| oracle (Section 5.4.2) | 0.0283 | **0.0360** | **0.79** | 2.3 |

Where validation runs with the 8B judge, R₀ lands at 2.4–7.6 — always well
above the containment threshold (R₀ < 1). The oracle arm is the exception
that proves the mechanism: perfect quarantine decisions raise γ ~4.5× and
bring R₀ to 0.79, the only sub-critical configuration observed. The multi-seed fit dissolves the
single-seed β story in the same way Section 5.4.1 dissolves the harm story:
seed 42's β of 0.0703 (~2.6 SD above baseline) sits next to seed 43's
0.0110, and the mitigated β mean (0.0327 ± 0.0259) is statistically
indistinguishable from baseline while carrying ~6.6× the variance. The full
Trio does not shift the transmission rate; it destabilises it. The floor arm
shows the intended β suppression (0.0289) but no γ (single seed).

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
