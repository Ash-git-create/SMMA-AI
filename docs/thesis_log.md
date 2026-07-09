# Research Log — Decisions, Challenges, Findings

Chronological engineering journal for the thesis *Cascading Knowledge
Contamination in Shared Memory Multi-Agent AI Systems*. Each entry records
what was done, what went wrong, what was decided and **why** — raw material
for the Methods, Implementation, and Discussion chapters. Maintained
continuously; newest entries at the bottom.

---

## 2026-05-08 — Phase 1 infrastructure

**Done:** project structure, environment setup, dataset pipeline (T-REx,
HotpotQA, FEVER download + normalization to unified JSONL), Neo4j KG loader
(50,000 T-REx triplets as pristine baseline, state=S, confidence=1.0),
x-tuple provenance schema (source_id, agent_id, timestamp, confidence,
lineage formula, SIR state).

**Decision — architecture pivot: local Ollama → hosted APIs.** Original plan
ran Mistral Nemo 12B and Llama 3.1 8B locally via Ollama (CPU-only; RX 560X
has no ROCm support on Windows). Measured throughput ~3–5 tok/s for the 12B
model made experiment-scale runs infeasible. Pivoted to Mistral La Plateforme
(extraction) + Groq (orchestration/validation), keeping Ollama as an offline
fallback via a provider-routing LLM client. Same model weights (open models,
hosted) — so the DRAGON-benchmark justification for model choice is preserved.

## 2026-05-09 — Phase 1 agents & SIR module

**Done:** ExtractionAgent (text → SPO JSON → Neo4j with provenance),
OrchestrationAgent (evidence-based triplet validation, S→I transition below
confidence threshold), ValidationAgent (audit passes, quarantine to R,
cascade deprecation), discrete-time SIR model (forward Euler), R₀ calculator
(β = retrieval_rate × susceptibility, γ = validation_frequency × detection
accuracy), simulation runner, thesis figures (SIR scenario curves, R₀
sensitivity sweep). 18-check smoke test suite.

## 2026-07-02 — Repository reconstruction

**Challenge:** several Phase 1 files (LLM client router, provenance schema,
dataset scripts) were built on 2026-05-08 but never committed — the committed
agents imported an untracked dependency. Reconstructed the git history with
backdated commits reflecting actual work dates, pushed to
github.com/Ash-git-create/SMMA-AI.

**Lesson:** commit each unit of work immediately; the git log is part of the
thesis evidence.

## 2026-07-02 — Pre-Phase-2 validity audit

Full code review before any measurement runs. Findings split into two
categories — a distinction that matters methodologically:

**(a) Measurement-corrupting bugs — fixed silently before data collection**
(these are engineering defects, not findings; leaving them would have
invalidated Phase 2 data):

1. *LLM-failure fallback wrote confidence 0.5 to healthy nodes.* A transient
   API error (rate limit, timeout) was recorded as a validation verdict —
   infrastructure failures would masquerade as contamination. Fix: on LLM
   call/parse failure, skip the DB write entirely and mark the result errored.
2. *Validation evidence was arbitrary.* Context for "is this fact supported?"
   was padded with unrelated KG rows → truthful triplets would be quarantined
   en masse, inflating false-positive γ. Fix: evidence = triplets sharing an
   entity with the target, ordered by confidence.
3. *Non-random sampling.* Neo4j without ORDER BY returns the same rows every
   query — audit passes re-checked identical nodes each step and infection
   seeding was non-uniform, biasing all SIR estimates. Fix: `ORDER BY rand()`
   sampling + seeded Python RNG.
4. *No reproducibility controls.* Added temperature=0, bounded max_tokens,
   retry with exponential backoff (Groq/Mistral free-tier rate limits),
   full request/response audit log (JSONL), and an on-disk response cache
   keyed on (provider, model, temperature, system, prompt).
5. Misc: double-load crash in KG loader, stale requirements.txt (fresh
   install broke), YAML experiment config system so ablations are config
   switches rather than code edits.

**(b) Design decisions recorded (not bugs):**

- `retrieval_threshold` defaults to **0.0** — the Trio confidence floor is
  the Phase 3 mitigation variable (RQ4); the Phase 2 baseline runs without it.
- `state` records *detected* SIR status (written by agents);
  `error_type` records *ground-truth* contamination (written only by the
  ErrorInjector). Detection AUROC compares the two; conflating them would
  make the metric circular.
- Entity nodes are keyed by surface string — "Paris (France)" and
  "Paris (Texas)" collide. Documented limitation; also the substrate through
  which entity-disambiguation errors propagate.

## 2026-07-02 — Phase 2.1: extraction pipeline + first empirical finding

**Done:** document extraction pipeline (HotpotQA supporting-fact paragraphs,
FEVER claims → ExtractionAgent → KG). Implements the contamination write-back
loop: retrieve related KG facts for the document's entity (β: retrieval) →
show them to the LLM alongside the passage (β: susceptibility) → write
extracted triplets back with lineage formulas AND `DERIVED_FROM` graph edges
(making Phase 3 cascade deprecation walkable). Seeded document sampling,
per-run provenance manifest CSV.

**Finding — the extraction model fact-checks when it should record.**
Pilot run (30 units, 10 docs/dataset, seed 42): Mistral Nemo returned an
empty extraction for 13/30 units, concentrated in FEVER claims. Audit log
inspection showed the model refusing to extract assertions it judged false
or unverifiable — e.g. "Rafael Nadal is a female tennis player." → `[]`.
The extraction agent was acting as a truth filter, not a recorder.

Prompt intervention (explicit "record what the text asserts, not what is
true" rules + a worked false-claim example) re-run on the identical 30 units:
**empty results 13 → 2, triplets extracted 105 → 156.** One refusal class
survives: claims blatantly false about well-known entities.

**Thesis relevance:** even the unmitigated system has a nonzero implicit
immune response — the extraction LLM's own world knowledge partially filters
contamination before it reaches the KG. This (a) will suppress the measured
natural-contamination rate relative to a naive model of agent behavior, and
(b) is itself a mechanism worth discussing alongside the explicit Trio
mitigation. The residual refusal rate should be characterized in Phase 2.4.

**Verified live:** 105 triplets + 20 DERIVED_FROM edges in the KG from the
pilot write run; lineage chains queryable (extracted Lakers facts traceable
to the 4 retrieved parent triplets). Pilot data to be cleared
(`load_kg.py --clear`) before the measured Phase 2 runs.

## 2026-07-02 — Phase 2.2 (metrics) + 2.3 (ErrorInjector)

**Done:** evaluation module (SQuAD-style EM/F1 for HotpotQA, Veracity
Accuracy + confusion for FEVER, Detection AUROC, USR — all pure functions,
unit-tested), KG-grounded evaluation runner (LLM answers using ONLY retrieved
KG facts, so task performance is a function of KG state — the degradation
curve under contamination is the headline task metric), and the ErrorInjector
implementing the three-error taxonomy with full before/after manifests.

**Challenge — the KG predicates were semantically opaque.** A dry injection
run exposed that 92% of baseline triplets carried bare Wikidata PIDs
("P54", "P17") as predicates: the relbert/t_rex export uses PIDs, and the
original preprocessing only cleaned template-style relations. Consequences:
(a) validators/QA agents were shown edges like "(X) --[P54]--> (Y)" they
cannot reason about; (b) qualifier-loss and relation-strengthening
injections had almost nothing to operate on (0/100 and 1/100 injectable).
Fix: PID → English label mapping for the 80 most frequent PIDs (~93% of
PID-bearing records), applied at preprocessing; KG regenerated and reloaded.
After the fix + injector extensions (full-date → year truncation as temporal
precision loss; Wikidata-flavored strengthening pairs like "nominated for"
→ "winner of", "cast member" → "lead actor"): all three error types inject
at 25/25 in dry runs.

**Design decision — injections do not touch `confidence` or `state`.** An
undetected error must look exactly like a trusted fact; detection is the
agents' job, and AUROC compares their `state`/confidence judgments against
the injector's `error_type` ground truth.

**Design decision — extraction and evaluation sample the same documents.**
Smoke-testing the evaluator showed KG fact coverage is the binding
constraint (questions about unextracted documents retrieve ~0 facts). With
identical seed, split filter, and sample size, the extraction and eval
runners provably select the same documents, so the baseline KG contains the
facts the eval questions require. Verified programmatically.

**Smoke-tested live:** eval end-to-end on 3+3 tasks (zero parse failures;
correct REFUTES on "West Virginia borders Maine" using retrieved
'shares border with' facts — the PID relabeling paying off directly).

## 2026-07-02 — First full Phase 2 measurement sequence

Protocol executed: clean KG (50,000 T-REx) → extraction over the 100 eval
documents (804 new triplets, 236 DERIVED_FROM edges, 16/150 units empty —
consistent with the residual truth-filter rate) → baseline eval → 150
injections (50 per error type) → post-injection eval.

**Baseline task performance (n=50 per dataset, seed 42):**
HotpotQA EM 0.12 / F1 0.158 (avg 4.8 retrieved facts per question),
FEVER Veracity Accuracy 0.48, zero parse failures. Low absolute numbers
reflect the system's constraints (KG-grounded answering with an 8B judge and
partial fact coverage) — the thesis quantity is the *delta* under
contamination, not the absolute level.

**Finding — static random injection is task-invisible at low prevalence.**
Post-injection metrics were IDENTICAL to baseline. The LLM response cache
proved why: all 100 post-injection eval prompts were byte-identical to their
baseline versions (100/100 cache hits), i.e. none of the 150 corrupted
triplets (0.3% of a 50K-node KG) appeared in any question's retrieval
neighborhood. Random index cases in a large KG do not intersect the
task-relevant subgraph at meaningful probability.

**Implication for experimental design (and a thesis argument):** isolated
static errors are nearly harmless in a large shared memory — the threat is
*propagation*. Task degradation requires (a) contamination spread through
agent write-back cycles (the cascade Phase 2.4 measures — index cases
multiplying via DERIVED_FROM chains raise exposure probability), and/or
(b) injection targeted at the active subgraph (entities the agents actually
retrieve). This directly motivates the epidemiological framing: injections
are index cases; without transmission, prevalence stays at 0.3% and exposure
stays negligible. Phase 2.4 must therefore (1) seed injections inside the
active retrieval neighborhood and (2) run agent write-back steps between
measurements. Incidentally, the byte-identical cache hits are also a strong
reproducibility validation of the whole measurement pipeline.

## 2026-07-04 — Phase 2.4: contamination-over-time runner

**Done:** `scripts/run_contamination.py` — the cascade experiment the previous
finding dictated. Design:

- **Targeted index cases.** Seeding candidates are the union of retrieval
  neighborhoods of the entity keys in the extraction manifest (the *active
  subgraph*), not uniform-random over the KG. The ErrorInjector gained an
  explicit `pool` parameter for this; the uniform path is unchanged.
- **Transmission cycle = one write-back pass of a two-agent chain.** Per
  cycle, for a seeded sample of active entities: retrieve KG facts (possibly
  contaminated — the retrieval component of β) → a synthesis agent (Mistral
  Nemo, same model as extraction per the architecture) writes a 2–4-sentence
  passage from ONLY those facts (the susceptibility component — corruption
  crosses from graph to text here) → the ExtractionAgent extracts triplets
  from the passage with the same facts as context → written back with
  DERIVED_FROM edges to the parents. Corrupted facts thus spawn derived
  corrupted facts through the same pipeline that produces legitimate ones.
- **Ground-truth transmission bookkeeping.** A new triplet is *exposed* if a
  lineage parent carries a contamination payload; *infected* if its
  normalized text reproduces the payload's corrupted value (word-boundary
  match) without reproducing the original value. Infected nodes get
  `error_type = propagated_<root_type>` and carry the payload onward, so
  second-generation transmission is tracked. Like the injector, this is
  experimenter bookkeeping: `state`/`confidence` are never touched — the
  match heuristic is auditable from the manifest (every transmission event
  is logged with its payload).
- **Fixed-question degradation curve.** Task metrics (HotpotQA EM/F1, FEVER
  veracity) are re-measured on the *same* question sample (same seed) at
  step 0, every k-th step, and the final step. Questions whose retrieval
  neighborhoods are untouched replay from the deterministic LLM cache —
  per-step evaluation costs API calls only where the KG actually changed.
- **One runner for baseline AND mitigated runs.** γ (validation audits per
  step) and the Trio retrieval confidence floor are config parameters
  (0 / 0.0 in `contamination_baseline.yaml`); Phase 3 mitigated runs will be
  a config diff, not a code diff.
- **Clean-room guard.** The runner aborts if ground-truth-corrupted nodes
  already exist in the KG (stale injections from a previous sequence would
  confound the counts); protocol is reload → extraction replay → run. The
  extraction replay is nearly free: same seed + same clean KG state → the
  deterministic cache replays every extraction byte-identically.

**Smoke run findings (1-cycle micro run):** transmission-check unit tests
pass (8/8, incl. word-boundary edge cases like "led" not matching inside
"settled"); two defects caught and fixed — manifest auto-discovery used
alphabetical sort (picked an old pilot manifest; now newest-by-mtime), and
the final summary mislabeled pre-existing corrupted nodes as propagated.

**Run launched:** clean reload (50K) → extraction replay → 10 transmission
cycles, 12 entities/cycle, 45 index cases (15/type), evals at steps 0/5/10
with the same 50+50 questions as the Phase 2.2 baseline. Results next entry.

## 2026-07-04 — Phase 2.4 baseline run: THE CASCADE IS REAL

First measured contamination-over-time run (10 cycles, 39 distinct index
cases seeded in the active subgraph, γ = 0, no retrieval floor). Trajectory
and full manifest archived at `results/summaries/phase24_baseline_*`.

**Headline: propagation observed and documented.** 20 transmission events
auto-flagged; manual audit of all 20 against their payloads → **13 genuine
second-generation contaminated facts** (tracker precision 0.65, see below).
Textbook cascade examples, straight from the manifest:

- *Entity disambiguation spreads to NEW subjects:* a seeded wrong-location
  fact produced "(Stone Brewing Co.) --[headquartered_in]--> (Atwater,
  California)" — the brewery is in Escondido; the wrong city jumped from the
  corrupted parent onto a different entity entirely. Likewise "(Naval
  Submarine Base New London) --[located_in]--> (Agra)", derived TWICE
  (steps 4 and 5) — re-derivation multiplies prevalence, which is exactly
  the epidemiological mechanism.
- *Relation strengthening crosses agents:* seeded "cast member → lead actor"
  re-emerged as "(Bing Crosby) --[lead_actor_in]--> (Robin and the 7 Hoods)".
- *Qualifier loss propagates degraded precision:* "(Black Book (film))
  --[premiere_date]--> (2006)" — the stripped year, not the full date.

**Per-type propagation (RQ2, first evidence):** entity_disambiguation was
the most reliable propagator — 8/8 flagged events genuine (0.57 propagated
per seed over 10 cycles). qualifier_loss: 11 flagged but only 4 genuine.
relation_strengthening: 1/10 seeds propagated — predicate wording appears to
be re-normalized by each synthesis→extraction pass, giving it the lowest
transmissibility. Wrong ENTITIES survive agent processing verbatim; wrong
RELATION STRENGTH mostly does not.

**Methodological finding — the ground-truth tracker over-counts on common
substrings.** All 7 false positives came from one cluster: a qualifier-loss
payload "New Orleans" (stripped from a longer form) matched inside entity
NAMES ("New Orleans Pelicans compete_in NBA" is a true fact, flagged only
because the payload string occurs in the subject). The word-boundary
heuristic is precise when payloads are distinctive (entity swaps, strong
predicates) and noisy when the corrupted value is a common name fragment.
Thesis treatment: report auto-flagged counts alongside audited counts; the
manifest logs every event with its payload, so the audit is reproducible.
(Considered and rejected: field-position matching — derived triplets do not
map fields 1:1 to parents.)

**Task metrics were FLAT (EM 0.16 / F1 0.174 / FEVER 0.62 at steps 0, 5,
and 10)** despite 59 ground-truth-contaminated nodes by step 10. Two
mechanisms explain it, both thesis-relevant:
1. Prevalence is still tiny (59 / 51K ≈ 0.1%) and shallow cascades stay
   within the neighborhoods they started in.
2. **Confidence-ranked retrieval is itself a passive mitigation:** derived
   (agent-written) triplets enter at confidence 0.85, below pristine 1.0, so
   `ORDER BY confidence DESC` retrieval keeps serving pristine facts to the
   eval questions. Corruption accumulates in the low-confidence stratum the
   evaluator rarely sees at the current KG size. This foreshadows RQ4: the
   Trio confidence floor makes this implicit protection explicit — and
   suggests the dangerous regime is when derived facts CAN outrank or
   crowd out pristine ones (small/sparse KGs, higher write volumes, or
   validation that *raises* confidence of unvalidated derived facts).

**Reproducibility note:** within-run evals are byte-stable (steps 0/5/10
identical where the KG neighborhoods were unchanged), but step-0 metrics
differ from the Phase 2.2 baseline taken before the DB reload (EM 0.16 vs
0.12, FEVER 0.62 vs 0.48). Cause: Neo4j breaks confidence ties in arbitrary
order, so a reloaded-but-identical KG can return different top-5 fact sets.
Lesson recorded: **comparisons must be within-run** (same DB instance); the
runner's fixed-question design does this by construction.

**Defect found and fixed:** the injector marked corruption in the DB but not
in the caller's in-memory candidate pool, so one triplet received two
injections across error types (40 records, 39 distinct nodes). Pool dicts
are now updated in place after each applied injection.

**Phase 2 status: COMPLETE.** All four sub-phases done. Next: Phase 3 (Trio
mitigation) — the baseline runner already exposes `retrieval_threshold` and
`audits_per_step`, so mitigated runs are config diffs; what remains is the
trio_framework module (confidence propagation via lineage arithmetization,
cascade deprecation on detection) and the ablation configs.

## 2026-07-04 — Pre-Phase-3 instrumentation upgrade + canonical baseline rerun

Before building the mitigation, four measurement upgrades were applied so
both arms of the baseline-vs-mitigated comparison record identically
(changing instrumentation after the fact would have forced a rerun anyway):

1. **Deterministic retrieval** — `ORDER BY confidence DESC, t.id`: confidence
   ties were previously returned in arbitrary order that varied across DB
   reloads, making cross-run metric differences partly noise. Retrieval (and
   therefore every LLM prompt) is now byte-stable given identical KG content.
2. **β decomposition instrumented** — each cycle records how many retrieval
   contexts contained ≥1 contaminated fact and how many contaminated facts
   were served. β = P(retrieve contaminated) × P(reproduce | exposed) is now
   estimated from the run itself, which is what couples the empirical
   pipeline to the SIR model (calibration inputs for the simulation-first
   answer to RQ3).
3. **Field-aware transmission matching** — object payloads must equal the
   derived subject/object exactly (normalized); predicate payloads
   word-boundary match the derived predicate only. Kills all three
   false-positive classes from the run-1 audit (name fragments, years inside
   full dates, payloads appearing in the wrong field); 16/16 regression
   cases pass, including every genuine run-1 pattern. Counts are now
   conservative (paraphrases not counted) — a documented lower bound.
4. **Probe question set** — auto-generated from the corrupted nodes
   ("What is the '<predicate>' of <subject>?"), answered KG-grounded,
   answers scored against corrupted vs original values. Separates
   *reach* (do generic queries encounter contamination — the fixed task
   sample) from *harm* (does the system reproduce contamination when in
   scope — the probes).

**Canonical baseline rerun (10 cycles, 40 index cases, seed 42) — headline
result of Phase 2:**

- **Probe contamination rate 0.85 at step 0, 0.82 at step 10 (n=40→49):**
  when a corrupted fact is in scope of a question, the KG-grounded system
  reproduces the corruption in its answer >80% of the time. Only 2/49 probes
  recovered the original value. Meanwhile the generic task sample stayed
  flat (EM 0.18, F1 0.22, FEVER 0.60 at steps 0/5/10). Together: **at 0.1%
  prevalence contamination is invisible to aggregate metrics AND almost
  always harmful when encountered** — low reach, high harm. This
  reach-vs-harm decoupling is the central empirical statement of Phase 2.
- **β components measured:** 9/90 retrieval contexts (10%) contained ≥1
  contaminated fact; 11/376 facts served (2.9%) were contaminated;
  9 infections / 39 exposures → per-exposure reproduction ≈ 0.23.
- **Per-type propagation UNSTABLE at n=1:** this run qualifier_loss 7,
  entity_disambiguation 1, relation_strengthening 1 — run 1 (audited) had
  entity_disambiguation ahead. The deterministic-retrieval change altered
  which triplets were seeded and served, flipping the ranking. Honest
  conclusion: per-type transmissibility (RQ2) requires the planned
  multi-seed replication; a single trajectory ranks noise.
- Injector double-injection fix confirmed: 40 records, 40 distinct nodes.
- With the tie-break in place this run is the reference: future runs on
  identical KG content replay byte-identically.

**Plan adjustments recorded (thesis-direction review):**
- RQ3 (density/write-frequency/validation-interval sweeps) will be answered
  **simulation-first**: empirical runs calibrate β and γ, the SIR simulator
  sweeps the parameter space, 2–3 predicted points are validated
  empirically. Full empirical sweeps do not fit the Phase 4 budget.
- Headline metrics are the epidemiological ones (velocity, per-type R₀,
  probe harm rate); generic task metrics are reported as the reach story.
- Promoted to required before write-up: **natural contamination rate** —
  audit ~50 derived triplets against their source passages to quantify
  extraction/synthesis error without any injection (grounds the
  "non-adversarial" premise).
- Phase 3 must measure mitigation collateral damage (clean facts wrongly
  quarantined by cascade deprecation), not just contamination reduction.

## 2026-07-04 — Phase 3.1: Trio framework built

**Done:** `src/mitigation/trio_framework.py` — the three ULDB-inspired
mechanisms as a coherent module:
1. *Confidence propagation* (write time, ExtractionAgent flag): derived
   confidence = base × ∏(parent confidences) — arithmetized conjunction
   under an independence assumption (documented limitation). Pristine
   parents (1.0) leave the extractor's base 0.85 untouched; uncertainty
   compounds down derivation chains. With a 0.5 floor, a pure
   derived-from-derived chain is excluded at generation 5 (0.85⁵ ≈ 0.44).
   Without this mechanism every agent write lands at a flat default and the
   floor separates nothing — the floor and the propagation are one
   mitigation, not two.
2. *Retrieval confidence floor*: enforced via min_confidence at every
   retrieval site — transmission cycles, task evaluation, probes, and the
   validator's own evidence gathering. Confidence is the only visibility
   currency; quarantine works by zeroing it, not by a state check.
3. *Cascade deprecation*: the lineage walk moved into the Trio module
   (ValidationAgent delegates). Intentionally over-quarantines (a derived
   node may have had clean parents) — collateral damage is now measured
   every step via the state × error_type confusion
   (R_contam = true quarantines, R_clean = collateral).

**Design decision — targeted validation.** Uniform random audits are
statistically useless at KG scale: 50 audits/step over 51K nodes touch a
given corrupted node with p ≈ 0.001 per pass, so γ ≈ 0 no matter how good
the detector is. The mitigated runs audit *what agents read and wrote this
cycle* instead (`audit_targeted`), modeling read/write-time validation.
WHERE the validator looks is as much a design variable as HOW OFTEN it
runs — worth an explicit subsection in the mitigation chapter; uniform
mode is kept for ablation.

**Finding (smoke run) — circular validation can AMPLIFY contamination
confidence.** In the mitigated smoke test, the validator re-scored
generation-2 derived facts from Trio-propagated confidence 0.38 up to
0.95–1.00 with verdict SUPPORTED. Cause: the evidence retrieved for a
derived fact includes its own lineage parents — the very facts it was
synthesized from — so validation confirms the fact against its own source
and *undoes the Trio confidence decay*. If the parent is contaminated, a
corrupted derived fact gets validated back up to full trust: validation
acting as an infection amplifier, the exact "dangerous regime" predicted
in the 2026-07-04 baseline entry (validation raising confidence of
unvalidated derived facts). Kept as-is for the measured runs — it is a
real property of naive evidence-based validation in shared-memory systems,
and arguably a headline mechanism finding for RQ4's "under what conditions
does mitigation help" discussion. Candidate refinement (future ablation,
not silently patched): exclude a node's own lineage ancestors from its
validation evidence.

**Ablation configs (Phase 3.2):** `contamination_mitigated.yaml` (all
mechanisms), `contamination_ablation_floor.yaml` (floor + propagation, no
validation), `contamination_ablation_validation.yaml` (validation, no
floor). Each differs from baseline/mitigated by exactly one block — the
RQ4 comparison is a config diff by construction. Detection AUROC computed
at the final step of every run (0.5 expected in arms with no re-scoring).

## 2026-07-04 — First full-Trio run: mitigation did not mitigate

First measured mitigated run (floor 0.5, targeted audits 25/step,
confidence propagation, seed 42), same protocol as the canonical baseline.

**Within-run results (valid):**
- **Propagation not reduced:** 12 propagated infections vs baseline's 9;
  probe contamination rate ended at 0.81 — statistically identical to the
  unmitigated 0.82. The floor cannot filter what it cannot see: undetected
  index cases carry confidence 1.0 by construction, above any floor.
- **Detection is the bottleneck, and it is weak:** 72 nodes quarantined
  over 10 steps — quarantine precision 8.3% (6 true / 66 collateral),
  recall 11.5% (6 of 52 ground-truth-contaminated). Cascade deprecation
  amplified the damage (single audit passes cascading up to 28 clean
  descendants). The collateral is visible in the task metric: HotpotQA EM
  fell 0.16 → 0.14 *within the mitigated run* while the baseline stayed
  flat — the mitigation destroyed usable clean knowledge without removing
  contamination. Full-Trio-with-a-weak-detector is NET NEGATIVE.
- **Circular validation confirmed at scale:** the validator's evidence for
  a derived fact includes the fact's own lineage parents, so derived facts
  (clean and corrupted alike) get re-scored up to 0.9–1.0, erasing Trio
  confidence decay.
- **Detection AUROC 0.82** — with a caveat: much of the separation comes
  from propagated infections carrying decayed *derived* confidences, i.e.
  the score partly detects "agent-written", not "contaminated". Undetected
  seeds at 1.0 are indistinguishable from pristine facts by construction.

**RQ4 answer taking shape:** provenance machinery is only as good as the
detector feeding it. With a weak, circularly-validated detector, the
confidence floor is inert against index cases, cascade deprecation
destroys clean knowledge, and the system is better off unmitigated. The
interesting question the ablations now answer: which mechanism carries the
damage, and does any carry benefit alone?

**Residual nondeterminism found and fixed:** extracted triplets carried
random `uuid4` IDs while retrieval tie-breaks on `t.id` — confidence-tied
facts therefore ordered differently across otherwise-identical runs
(step-0 metrics differed slightly between arms; an interim "floor
backfired at step 0" reading was traced to this noise and retracted — at
step 0 the floor excludes nothing, as every confidence is ≥ 0.85).
ExtractionAgent now mints deterministic counter-derived UUIDv5 IDs: an
identical pipeline replay produces identical IDs, making arms
byte-comparable end to end.

**Phase 3.2 batch launched:** all four arms (baseline, floor-only,
validation-only, full Trio) rerun fresh from byte-identical starting
states under deterministic IDs — the definitive comparison set.

## 2026-07-06/07 — Phase 3.2 four-arm comparison complete (PHASE 3 DONE)

The batch interrupted by the Groq daily cap on 07-04 was resumed: the
three remaining arms (floor, validation, mitigated) rerun as clean-room
sequences (reload 50K pristine → extraction replay → contamination run)
against the completed 07-04 baseline arm. The mitigated arm hit the Groq
TPD cap again during step-9/10 measurement, but the server-stated-wait
retry logic carried it through overnight: 92 rate-limit hits, **zero
permanently failed LLM calls** — integrity verified by log audit (no
`attempt 3/3`, no tracebacks). All numbers are same-seed (42),
deterministic-ID, single-run; multi-seed replication is the named caveat.

**Four-arm results (step 10):**

| arm | mechanisms | propagated | exposed | probe contam rate | quarantine true/collateral | AUROC |
|---|---|---|---|---|---|---|
| baseline | none | 21 | 62 | 0.667 | — | 0.891 |
| floor | Trio decay + floor 0.5 | **14** | 82 | 0.889 | — | 0.883 |
| validation | targeted audits + cascade | 26 | 72 | **0.567** | 6 / 36 (14%) | 0.884 |
| mitigated | all of the above | **34** | **94** | 0.700 | 7 / 60 (10%) | 0.855 |

Archived: `results/summaries/phase32_*` (four trajectories + manifests,
step-10 probe CSVs, `phase32_arm_comparison.csv`).

**Findings:**

- **Mechanism decomposition (RQ4 core result):** the floor suppresses
  *spread* (14 propagated — the only arm below baseline) but not *harm*
  (probe rate 0.889, the worst: conf-1.0 index cases pass any floor, and
  filtering low-confidence clean derived facts hands them a larger share
  of the retrieval neighborhood). Validation suppresses *harm* (probe rate
  0.567, the only arm below baseline — quarantined facts leave probe
  scope) but not *spread* (26 propagated). Each mechanism helps on exactly
  one axis and hurts on the other.
- **The combination is superadditively bad:** full Trio is the worst arm
  on spread (34 propagated, +62% over baseline) and exposure (94, +52%),
  with probe harm *above* baseline (0.700 vs 0.667) and the worst
  quarantine precision (10%: 7 true, 60 clean facts destroyed). Mechanism:
  both components prune *clean* competition — the floor removes
  low-confidence clean derived facts, quarantine removes audited clean
  facts — while undetected conf-1.0 index cases survive both and dominate
  the thinned retrieval neighborhoods. Two half-blind defenses stack their
  collateral, not their protection.
- **Detection AUROC is flat across arms (0.85–0.89), including the
  unmitigated baseline** — confirming the 07-04 caveat: the confidence
  signal separates "agent-written derived" from "pristine", not
  "contaminated" from "clean". The mitigation machinery consumes this
  signal without improving it.
- **Task metrics flat everywhere** (EM 0.12–0.14, FEVER 0.60): the
  reach-vs-harm decoupling holds under every mitigation configuration.
- **RQ4 answer (single-seed):** Trio-style provenance mitigation fed by a
  weak detector is not merely ineffective but actively harmful, and its
  components interact in the harmful direction. Provenance machinery
  amplifies whatever detector feeds it — precise detection would propagate
  precision; weak detection propagates collateral. The known-broken
  circular validation (evidence includes the fact's own lineage parents)
  is the designed follow-up ablation: fix the detector, hold the machinery
  constant, measure whether the combination flips from harmful to helpful.

**Operational note:** the free-tier Groq TPD budget (500K/day) fits ~3
arms/day; future batches must span two days or move to the paid tier
(≈$1 total for all remaining thesis experiments at Llama 3.1 8B pricing —
recommended before Phase 4 scale-up and multi-seed replication).

---

## 2026-07-07 — Multi-seed baseline replication (task #8 DONE)

Decision: stay on free tiers (user declined paid upgrade; Claude-API switch
rejected on comparability grounds — all results are properties of the
Llama 3.1 8B + Mistral Nemo agent stack and remaining runs must stay on it).

Ran seeds 43/44/45 of the unmitigated baseline arm as full clean-room
sequences (load_kg --clear → extraction replay → contamination run),
identical to the Phase 3.2 procedure; only `--random-seed`/`--tag` varied.
Together with the 07-04 seed-42 run: **4 baseline replicates**. All three
new runs clean — 0 rate-limit hits, 0 failed LLM calls (never touched the
TPD cap; baseline arms are the cheap ones). Archived:
`results/summaries/phase33_baseline_s{43,44,45}_{trajectory.csv,manifest.json}`
+ `phase33_seed_variance.csv`.

| seed | seeded | propagated | exposed | probe rate (s10) | AUROC |
|---|---|---|---|---|---|
| 42 | 39 | 21 | 62 | 0.667 | 0.891 |
| 43 | 39 | 12 | 56 | 0.706 | 0.895 |
| 44 | 40 | 20 | 68 | 0.617 | 0.905 |
| 45 | 39 | 18 | 75 | 0.877 | 0.903 |
| **mean ± sd** | — | **17.8 ± 4.0** | **65.3 ± 8.3** | **0.717 ± 0.113** | **0.899 ± 0.007** |

### What the variance does to the Phase 3.2 claims

- **SURVIVES — full-Trio superadditive harm.** Mitigated propagated 34 is
  ~4 sd above the baseline mean (17.8 ± 4.0); exposed 94 is ~3.5 sd above
  (65.3 ± 8.3). No baseline seed comes close. The headline RQ4 finding is
  robust to seed noise.
- **SURVIVES — flat AUROC.** Baseline AUROC is extremely stable across
  seeds (0.891–0.905); the mitigated arm's 0.855 and the "confidence
  detects agent-written, not contaminated" interpretation stand.
- **SURVIVES — reach-vs-harm decoupling.** Task metrics are flat step
  0→10 *within every seed* (4/4 replicates). Cross-seed EM levels differ
  (0.00–0.12) because eval questions are sampled with the run seed —
  question-sample variance, not a contamination effect; comparable-question
  task comparisons remain the seed-42 four-arm table.
- **WEAKENED — floor cuts spread.** Floor arm's 14 propagated sits inside
  the baseline seed range (12–21, ~1 sd below mean). Single-seed evidence
  for "the floor reduces spread" is not distinguishable from seed noise.
- **WEAKENED — single-arm probe-rate effects.** Baseline probe rate spans
  0.617–0.877 across seeds (sd 0.11). Floor's 0.889 ("worst harm") is
  within ~1.5 sd of the baseline mean, and validation's 0.567 within
  ~1.3 sd. Both mechanism-decomposition directions remain plausible but
  are no longer strongly evidenced by one seed each; the *combined* arm's
  pattern (worst spread AND worst exposure AND 10% quarantine precision)
  is what carries the RQ4 conclusion.

**Write-up rule going forward:** every single-seed comparison must be
quoted against baseline seed-sd (propagated ±4, exposed ±8, probe ±0.11).
Differences smaller than ~2 sd get hedged language; only the full-Trio
harm result gets unhedged causal language. If time permits in Phase 4,
a 3-seed replicate of the *mitigated* arm would upgrade the superadditive
claim from "far outside baseline noise" to a proper two-sample comparison.

Next: #9 natural contamination audit, #10 random-seeding control
(~1 free-tier day each).

---

## 2026-07-07 (evening) — SIR fit + RQ2 analysis; eval-seed fix; audit launched

Gap audit against the CLAUDE.md promises found: (a) R₀ never fit to real
data (SIR modules only wired to the Phase 1 synthetic sim), (b) USR
implemented but never measured (now task #16), (c) task-eval questions
sampled with the run seed (cross-run task metrics compared different
question samples). Plan extended with tasks #11–#17.

**Eval-seed fix (#13 DONE):** `run_contamination.py` gains `--eval-seed`
(default 42 = the sample every four-arm run used) for task-eval question
sampling; probes stay on `--random-seed`. No completed run invalidated;
all future runs measure the same questions.

**SIR fit (#11 DONE — `scripts/fit_sir.py`, `phase35_sir_fit.csv`):**
Compartments reconstructed from ground truth (I = gt_total − det_R_contam;
the raw trajectory S/I/R columns are bookkeeping, not epidemic states);
least-squares fit forward-simulating `sir_model.py`.
- beta: baseline 0.044 ± 0.010 (4 seeds); floor 0.029; mitigated **0.070
  (~2.6 sd above baseline)** — the superadditive-harm claim in fitted-
  parameter form.
- **R₀ = beta/gamma ≈ 7.2 (validation) and 4.9 (mitigated)** — an order of
  magnitude above the R₀ < 1 containment threshold. gamma=0 arms report
  per-step effective reproduction instead (no classical R₀ without
  recovery).
- Caveat for write-up: at 50K-node scale S never depletes, so fixed-beta
  mass-action SIR cannot reproduce the observed late-run plateau (fit RMSE
  up to ~5 nodes) — scale mismatch to discuss, not a bug.

**RQ2 per-type analysis (#12 DONE — `scripts/analyze_error_types.py`,
`phase35_error_type_analysis.csv`):**
- Baseline reproduction per seed case: **entity_disambiguation 0.63 ± 0.27
  > qualifier_loss 0.50 ± 0.04 > relation_strengthening 0.08 ± 0.05**.
  RQ2 answered with multi-seed spread.
- Under BOTH validation arms, ED reproduction jumps to **1.4 (> 1,
  self-sustaining)** — 21 transmissions from 15 seeds — while QL/RS stay
  subcritical. The arms that audit are the arms where ED spreads
  super-linearly; consistent with circular-validation amplification.
- Methods note: injector found only 9–10 relation_strengthening candidates
  vs target 15 in every run (weak-predicate scarcity).

**#9 natural audit (running):** `scripts/audit_natural.py` — fidelity audit
of all 783 extraction-written triplets against source passages (gt-
contaminated IDs excluded two ways), judged by the validation-role LLM with
the injected taxonomy as labels. Interim at 250/783: **natural error rate
≈ 9.6%** — 12 entity errors, 12 unsupported, **0 qualifier_loss, 0
relation_strengthening**. Either natural errors are ED/hallucination-
dominated (validates ED as the realistic injected type) or the judge is
insensitive to subtle QL/RS — task #17 (human calibration of a 30–50
sample) distinguishes. Hit the TPD cap at 250; crawling overnight on the
server-stated-wait retry logic. Full rates tomorrow.

---

## 2026-07-08 — Natural contamination audit complete (task #9 DONE)

Full census of all 783 extraction-written triplets (29 gt-contaminated
excluded; crawled through the TPD cap over ~20h; 0 parse failures, 0
failed calls). Archived: `results/summaries/phase34_natural_audit.csv`
(+ summary JSON, + blind 40-row calibration sheet & answer key for #17).

**Natural error rate: 11.9%** (93/783) — the RQ1 base rate. The
contamination process needs NO adversary: roughly one in eight facts the
unmodified ExtractionAgent writes is already erroneous.

| label | n | share |
|---|---|---|
| SUPPORTED | 690 | 88.1% |
| ENTITY_ERROR | 56 | 7.2% |
| UNSUPPORTED (hallucination) | 32 | 4.1% |
| RELATION_ERROR | 5 | 0.6% |
| QUALIFIER_LOSS | 0 | 0% |

- **Natural errors are entity/hallucination-dominated, mirroring RQ2:**
  the error type that propagates most (entity_disambiguation, reproduction
  0.63 baseline / 1.4 under validation) is also the one extraction
  produces most naturally — injected ED errors are realistic, not a
  worst-case construct. Relation errors are rare naturally AND barely
  propagate. Zero qualifier-loss detections either mean QL is not a
  natural failure mode at this passage length or the Llama judge is
  insensitive to it — #17 (human calibration, blind sheet ready)
  distinguishes; until then QL claims stay hedged.
- **Source-context richness is an RQ1 condition: FEVER 40.4% (19/47) vs
  HotpotQA 10.1% (74/736).** Single-sentence claims give the extractor
  almost no disambiguating context → 4x the error rate of paragraph
  units. (FEVER n is small; quote the CI.)
- Fidelity ≠ truth caveat: a faithfully extracted false FEVER claim counts
  as SUPPORTED — ingestion of false claims is a separate (unmeasured)
  contamination channel; note in limitations.

**#10 prep (token-free, launch-ready):** `run_contamination.py` gains
`--seed-placement {active,random}` (injector already supported uniform
placement; compile-checked) + `experiments/configs/
contamination_control_random.yaml` (baseline diff: placement + fixed
eval_seed). Launches tomorrow on a fresh budget.

## 2026-07-09 — Random-seeding control arm (task #10 DONE)

**Run:** single clean-room sequence (load_kg --clear → extraction replay →
contamination), config `contamination_control_random.yaml` — identical to
baseline except `seed_placement: random` (index cases placed uniformly
across the Susceptible KG instead of inside the active retrieval subgraph).
Seed 42, eval_seed 42, tag `control_random`. Zero rate-limit hits, zero
failed LLM calls (~31 min run). Raw: `contamination_control_random_
20260709_115303_*`; archived to `results/summaries/phase36_control_random_
{trajectory.csv,manifest.json,summary.csv}`.

**Headline (RQ1): retrieval reachability is effectively necessary for
spread.**

- **Propagated 0, cum_exposed 0** (baseline mean 17.8±4.0 / 65.3±8.3 over
  seeds 42–45). Agent working contexts contained a contaminated fact in
  0/8 passages at every one of the 10 steps. The seeded errors sat in the
  KG untouched for the entire run.
- **Probe contamination rate 0.933, flat steps 0/5/10** — HIGHER than
  baseline step-10 mean 0.717±0.113, with probe_original = 0/45: when a
  randomly placed error IS directly queried, there is no competing correct
  evidence in its sparse neighbourhood, so the agent reproduces it almost
  every time. Persistence and spread are decoupled phenomena: existence in
  shared memory makes an error *locally believed*, but only placement in
  the retrieval-active subgraph makes it *epidemic*.
- **Detection AUROC 0.488 (chance)** vs baseline 0.899±0.007. The
  detector's signal in baseline runs evidently comes from propagated
  agent-written nodes and active-subgraph features, not from the seeded
  T-REx modifications themselves — randomly placed seeds are statistically
  invisible to it. Framing for the write-up: detectability is a property
  of the *cascade*, not the *error*.
- Task metrics flat (hotpot EM 0.10, FEVER 0.60 at steps 0/5/10),
  consistent with the reach-vs-harm decoupling in all baseline seeds; this
  run used the fixed eval_seed so these numbers are the first directly
  cross-run-comparable task metrics.
- Methods note: with the full Susceptible KG as the pool the injector
  seeded all 45 index cases (15 RS), confirming the 9–10/15 RS shortfall
  in baseline runs is a property of the *active pool*, not the injector.

**Interpretation for RQ1:** the three conditions for spread now have
evidence — (1) the error must be retrieval-reachable (this control:
0 vs 17.8 propagated), (2) extraction writes errors at an 11.9% natural
rate (task #9), (3) validation does not push R₀ below 1 (task #11,
R₀≈7.2). Mere existence in shared memory is insufficient AND
undetectable-at-chance; the active subgraph is both the attack surface
and the detection surface.

**Caveat for write-up:** single seed (42) for the control arm. The gap to
baseline is ~4.5 sd (0 vs 17.8±4.0) and mechanistically forced (contexts
never sampled the sparse region), so a multi-seed control replicate is low
priority — note it as such rather than claiming replication.
