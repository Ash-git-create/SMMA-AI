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

## 2026-07-09 (afternoon) — Judge calibration (task #17 DONE): the 11.9% natural rate does not survive

**Method fix first:** the v1 blind sheet lacked the source passages (my
generation error), so Ashwin's first pass could only judge world-truth —
preserved as `phase34_world_plausibility_labels.csv` (side finding: 17/20
judge-flagged errors are world-plausible, so plausibility review cannot
substitute for provenance). Regenerated as
`phase34_judge_calibration_blind_v2.csv` with passages; Ashwin relabeled
all 40 rows blind against the 5-label taxonomy. Scoring in
`phase34_judge_calibration_results.csv` + `_summary.json`.

**Headline: the Llama 3.1 8B judge's flag precision is 10% (2/20).**

- Exact-label agreement 21/40; binary 22/40. All 20 judge-SUPPORTED rows
  human-confirmed (0 missed errors in that stratum); of 20 judge-flagged
  errors, 18 are false alarms.
- Per category: ENTITY_ERROR 0/10 confirmed; UNSUPPORTED 1/5;
  RELATION_ERROR 1/5 — and the RELATION stratum is a census (all 5 flags
  in the whole audit), so exactly 1 real error there, which the human
  labels QUALIFIER_LOSS (the judge is QL-insensitive, confirmed: 0 QL
  calls in 783, misfiles the one real QL as RELATION).
- **Corrected natural error rate ≈ 0.9%** (56×0.0 + 32×0.2 + 1 ≈ 7.4 true
  errors / 783), an order of magnitude below the naive 11.9%. Wide CI
  (ENTITY 0/10 upper bound ~26%), but the direction is unambiguous.
- **The FEVER 40.4% vs HotpotQA 10.1% gap is largely a judge artifact:**
  6/6 FEVER flags in the sample are false alarms, including the three
  world-false claims (Aarhus south of London, "198 musicians", CONCACAF
  South America) that were extracted faithfully — the judge leaked world
  knowledge into a fidelity task, exactly what its system prompt forbade.
  The "context richness as RQ1 condition" framing is retracted; reframe
  as: fidelity judging of counterfactual claims defeats an 8B judge.
- **Convergent mechanism for the Trio net-harm result:** flag precision
  10% here ≈ ValidationAgent quarantine precision 8–10% in the mitigated
  runs — two independent measurements of the same phenomenon. The full
  Trio arm hurts because its validator is this judge grade: it mostly
  flags good nodes, and cascade deprecation amplifies those mistakes.
  Strengthens the case for #15 and makes "judge quality is the mitigation
  bottleneck" a first-class RQ4 discussion point.

**Write-up consequences:** (1) natural extraction fidelity errors are
rare (~1%) → contamination is not extraction noise; the amplification
machinery is the story — sharpens RQ1 alongside today's control arm.
(2) The RQ2 realism claim ("natural mix mirrors propagation ranking")
must be hedged: the natural mix was judge-artifact-dominated.
(3) Detection AUROC numbers (different feature-based detector) are
unaffected. Limitations: single rater (author), blind but post-hoc;
optional Haiku second rater parked.

## 2026-07-09 (late) — Truth-channel quantification (task #19 DONE, token-free)

**Method:** every FEVER-derived triplet in the natural-audit population
(same manifest pair, 783 triplets) mapped to its claim's ground-truth
verdict via `scripts/analyze_truth_channel.py` — zero LLM calls. Outputs:
`phase34_truth_channel.csv` (per-triplet) + `_summary.json`.

**Findings:**

- **9 known-false triplets sit in the KG as facts** (from 8 REFUTED
  claims): "2016 Tour de France had 198 musicians", "The Beach released
  in 2001", "Harris Jayaraj from Hyderabad", "The Daily Show described
  as credible news program", etc. Upper bound 9 / lower bound 8 (a
  REFUTED claim can carry true sub-facts — e.g. Bethany Hamilton's
  autobiography WAS adapted into a film).
- **74.5% of FEVER-derived KG content is false-or-unverifiable** (9
  REFUTES + 26 NEI of 47 triplets). NEI content enters with the same
  confidence as verified fact. As a share of all extraction triplets:
  known-false 1.15%, unverifiable another 3.3%.
- **Replacement headline for the retracted 11.9%:** natural contamination
  ≈ 0.9% extraction infidelity (#17-corrected) + ~1.2% known-false
  ingestion + ~3.3% unverifiable ingestion. The truth channel dominates
  the fidelity channel — and NO fidelity validator can see it, because
  faithful extraction of a false claim is exactly what fidelity endorses.
  Motivates provenance-level defenses (source verdicts/trust) over
  content validation — direct RQ4 ammunition.
- **Extractor self-censoring (new finding):** REFUTED claims yield
  triplets at less than half the rate of other claims — 8/18 units vs
  27/32, triplets/unit 0.50 vs 1.09 (SUPPORTS) / 1.24 (NEI), Fisher exact
  p=0.0085, OR 0.15. Mistral Nemo's world knowledge partially resists
  extracting claims it "knows" are false. Elegant symmetry with #17: the
  SAME world-knowledge leakage is protective in the extractor
  (self-censoring) and harmful in the judge (false alarms). Small n (50
  units) — quote the CI/p, don't oversell.
- Fidelity-judge cross-tab: 7/9 known-false triplets were judged
  SUPPORTED — as designed (fidelity ≠ truth), now with ground truth
  attached.

## 2026-07-09 (evening) — Chapter drafting started (task #22) while #14 crawls the TPD cap

Drafted `docs/chapters/ch3_methodology.md` (full Chapter 3: architecture
as-run [Mistral API + Groq, not the original Ollama plan], KG/provenance
schema, taxonomy + seed-placement-as-variable, SIR formulation +
measurement mapping, Trio mechanisms as separable levers, clean-room
protocol + arm table + replication policy, metrics, and the 3-layer
validity instrumentation) and `docs/chapters/ch5_results_phase23.md`
(Sections 5.1–5.8: baseline envelope, reach-vs-harm, control arm,
mitigation 4-arm with the seed-43 divergence flagged `[PENDING-#14]`,
SIR fit/R₀, RQ2 ranking, the three-instrument natural-contamination
story with the corrected ~0.9% + truth channel, statistical treatment).
All retractions/hedges from today's entries are baked in. Figures marked
`[FIG]`; Phase-4-dependent parts marked.

**#14 interim:** seed 43 mitigated = 6 propagated / 44 exposed / probe
0.76 / AUROC 0.873 — BELOW baseline mean, vs seed-42 mitigated 34/94.
Full-Trio harm may be high-variance rather than robustly harmful;
ch5 §5.4 already drafted with the conditional restatement. Seed 44
mid-run against the TPD cap; seed 45 expected tomorrow.

## 2026-07-11 — USR decision (task #16): KEEP, mechanical form

Decided with Ashwin: USR stays, implemented mechanically (sentence-level
entity/string overlap against the question's retrieved high-confidence
triplets — no LLM judge). Reasons: it is the suite's only answer-side
grounding metric; EM/F1/FEVER have been flat in every run, leaving Phase 4
without a sensitive answer-quality instrument for RQ4's "preserving answer
quality" clause; it is the metric positioned to expose the confidence
floor's retrieval-shrinkage cost; and the mechanical form is deterministic
and immune to the judge-precision problem (#17). Lexical-matching
crudeness to be documented as a limitation. To be wired into the task-eval
path before Phase 4 (~2026-07-30). ch3 §3.7's [PHASE-4] USR note to be
updated when implemented.

Also this morning: planned power-off will kill the seed-45 mitigated run
mid-flight (batch relaunch script ready; cache makes the rerun cheap).
Seeds 43/44 complete: 6/44 and 10/67 propagated/exposed — full-Trio harm
is emerging as HIGH-VARIANCE rather than robust (42: 34, 43: 6, 44: 10,
45: ~24 through step 9).


---

## 2026-07-12 — Mitigated multi-seed complete: full-Trio "harm" dissolves into variance + detection degradation (task #14 DONE)

**Done:** seed-45 mitigated run completed after two external process kills
(rerun was near-free: LLM cache fast-forwarded the whole trajectory; only
the step-10 eval battery was fresh). 4-seed mitigated table assembled,
formal stats vs baseline (n=4 vs 4), ch5 §5.4/§5.5/§5.8 finalised, ch3
replication note updated. Archives: `phase37_mitigated_multiseed.csv`,
`phase37_mitigated_multiseed_stats.json`, `phase37_sir_fit_mitigated_seeds.csv`,
per-seed manifests/trajectories (s43–s45) in `results/summaries/`.

**Final 4-seed mitigated results** (propagated / exposed / probe / AUROC /
quarantine precision): 42: 34/94/0.700/0.855/10.4% · 43: 6/44/0.761/0.873/3.0%
· 44: 10/67/0.720/0.843/7.3% · 45: 10/37/0.780/0.864/2.0%.
Mean 15.0±12.8 propagated, 60.5±25.7 exposed vs baseline 17.8±4.0, 65.3±8.1.

**Three statistical conclusions (Welch t + Mann-Whitney, two-sided):**
1. NO reliable effect on spread or probe rate (all p ≥ 0.31). The seed-42
   "superadditive harm" headline is RETRACTED as a point estimate — it is
   the upper tail of the mitigated arm's own distribution.
2. ~10× VARIANCE amplification on both spread metrics (F(3,3) two-sided
   p ≈ 0.09, suggestive at n=4; direction consistent, mechanism known).
3. The ONLY significant effect is negative: detection AUROC 0.859±0.013 vs
   0.899±0.007 (Welch p = 0.004, MW p = 0.029 = perfect separation).
   Mechanism: confidence laundering — validation raises survivors to
   conf ≈ 1.0 and quarantine removes mostly-clean nodes, so surviving
   contamination hides in a cleaner-looking population.

**Quarantine precision across 4 seeds: 2–10%, pooled 5.9% (14/238)** —
worse than the earlier 8–10% estimate, and the engine of the variance:
which lineages get cascade-deprecated is a near-random lottery.

**SIR multi-seed:** β_mitigated 0.0327±0.0259 (vs baseline 0.0437±0.0101 —
indistinguishable mean, ~6.6× variance), γ 0.0080±0.0055, R₀ 2.4–7.6, all
≫ 1. Seed-42's β=0.0703 sits next to seed-43's β=0.0110: Trio does not
shift the transmission rate, it destabilises it.

**Restated RQ4 finding:** with a ~6–10%-precision validator, full Trio does
not mitigate — mean spread unchanged, outcome variance ×10, detectability
degraded (the one clean replication), never dependably better than nothing.
Provenance-aware retrieval is only as good as the judgement that feeds it.

**Honest replication note:** the killed seed-45 partial reached step 10
with 12 propagated / 75 quarantined; the completed rerun produced 10 / 50.
Same seed, same protocol — the run seed fixes injection placement, not LLM
generation. Residual API nondeterminism contributes within-config variance;
recorded in §5.4.1. Also: two background-process kills today with no script
error (13:39 and Thursday 19:06) — long runs are now launched with the
relaunch script kept ready; reruns are cheap by design.

**Next:** #18 oracle-validator arm (isolates architecture-vs-judge blame
for the AUROC degradation and variance — now the sharpest open question),
then #20 prompt-tuned validator, #15 ancestor-excluded ablation, #16
mechanical USR before Phase 4.


---

## 2026-07-12 (afternoon) — Oracle-validator arm: R₀ = 0.79, the first sub-critical configuration (task #18 DONE)

**Done:** implemented `ValidationAgent(oracle=True)` (ground-truth quarantine
verdicts via `error_type`, zero audit LLM calls; no re-scoring of clean
nodes, so the confidence-laundering channel is structurally absent),
`--oracle-validation` runner flag, `contamination_oracle.yaml` (identical to
mitigated except the judge). Clean-room run, seed 42, completed in ~45 min
(all 250 audit calls free). Archives: `phase38_oracle_{manifest,trajectory}`,
`phase38_sir_fit_oracle.csv`. ch5 §5.4.2 written; ch3 arm table updated.

**Results (oracle vs Trio-8B n=4 vs baseline n=4):**
- Propagated 11 / exposed 44 (38 index cases realised; RS 8/15 in pool).
- **R₀ = 0.79** — γ = 0.0360, ~4.5× the 8B judge's 0.0080. Only arm ever
  below the epidemic threshold. The architecture CAN mitigate.
- **Probe rate DECLINES 0.842 → 0.756 → 0.612** — the only declining probe
  trajectory in any run; quarantine that actually removes contamination
  makes errors unretrievable, hence unbelieved (probe_other 5 → 18).
- **AUROC degradation vanishes: 0.899** (= baseline mean; 8B judge arm
  0.859). Confirms confidence laundering as a judge artifact — the oracle
  never re-scores survivors. Caveat noted: oracle AUROC partly favourable
  by construction (caught nodes carry conf 0); the claim is the
  disappearance of the DEGRADATION, not superior detection.
- **Architecture residual cost: 2:1 collateral** — 32 clean quarantined per
  16 contaminated, all cascade descendants (exposed-but-clean derivations).
  Perfect judgement caps collateral at the lineage structure's own ratio;
  the 8B judge was ~9:1.

**Attribution verdict (RQ4):** judge precision is the bottleneck, not the
Trio architecture. Same stack, no other change: 6-10% precision → R₀ ≈ 4.5;
100% precision → R₀ = 0.79. Mitigation quality is monotone in validator
precision → motivates #20 (prompt-tuned validator) as a dose-response point
between the endpoints, and reframes #15: circular validation matters only
insofar as it depresses effective precision.

**Caveats:** single seed; 38 index cases (seeding-pool RS shortfall);
propagated count alone (11) is NOT distinguishable from the 8B arm's wide
distribution — the discriminating evidence is R₀ < 1 + declining probes +
restored AUROC.

**Next:** #20 prompt-tuned validator (offline iteration on the 40 human
labels, then one mitigated rerun if precision jumps), #15, #16 mechanical
USR before Phase 4.


---

## 2026-07-12 (evening) — Mechanical USR implemented in the task-eval path (task #16 DONE)

**Done:** implemented the 2026-07-11 USR decision. `src/evaluation/metrics.py`
gains `answer_traceable()` (span-level: normalized answer appears inside a
retrieved fact field or vice versa, word-boundary matched; None for
abstentions/booleans), `sentence_supported()`/`sentence_usr()`
(sentence-level, both-endpoint rule, abbreviation-safe splitter) — all pure
functions, no LLM, no DB. `eval_hotpotqa` now emits per-row `traceable` and
summary `usr`/`usr_n`/`abstain_rate`; `run_contamination.run_task_eval` maps
them into trajectory columns (`hotpot_usr`, `hotpot_usr_n`,
`hotpot_abstain`). Zero LLM calls added, zero prompt changes — cache
comparability with all archived runs preserved. FEVER excluded (its answer
is a class label, not a groundable span).

**Validation:** unit tests (span + sentence + splitter edge cases) all pass.
End-to-end replay of the oracle arm's archived step-10 answers against the
live KG (retrieval only, zero tokens): **abstain rate 0.64** under the 0.5
retrieval floor — the shrinkage cost USR was kept to expose — and **USR 4/17
= 0.24**: the QA agent answered e.g. "Heathrow" with no such fact retrieved,
i.e. parametric world knowledge leaking past the "facts only" instruction.
Both signals invisible to EM/F1 (flat everywhere). Replay numbers are
indicative (questions truncated to 120 chars in archived CSVs); canonical
values come from Phase 4 runs where USR is computed in-run.

**Design note recorded in ch3 §3.7:** USR measures grounding, not truth — a
faithful reproduction of a retrieved contaminated fact is traceable BY
DESIGN (the truth channel, §5.7c, owns the truth axis). String overlap ≠
semantic support, documented as the limitation.

**Meanwhile:** #20 validator-tuning benchmark still crawling the exhausted
Groq TPD window (~1 call/1-4 min; today's three runs consumed the 500K
budget). Every completed judgement is durable; ETA this evening. Side
finding recorded: the Excel cp1252 re-save of the blind sheet altered
passage bytes, so even v0_original misses the LLM cache — all 160 tuning
calls are paid.


---

## 2026-07-12 (night) — CORRECTION: the LLM response cache was never enabled

**Finding:** while diagnosing why a killed tuning run did not fast-forward on
relaunch, discovered that `LLM_CACHE_DIR` was never set (not in env, not in
.env). The llm_client only caches when it is set, so **every run in this
project to date executed with caching disabled** — all reruns were full
fresh generations.

**Corrections to the record (discipline rule 5):**
- The 2026-07-12 morning entry's claim that the seed-45 rerun was "near-free:
  LLM cache fast-forwarded the whole trajectory" is WRONG. The rerun re-paid
  every call; it was fast because the TPD window happened to have room. This
  is also why the token budget exhausted by mid-afternoon.
- All other "cache fast-forward" narrations in session notes are likewise
  wrong. No archived RESULT is affected — this is a cost/narrative
  correction, not a data correction.
- Silver lining: same-seed reruns being independent generations makes the
  seed-45 divergence observation (12 vs 10 propagated, §5.4.1 replication
  note) a cleaner statement about API nondeterminism at temperature 0.

**Fix:** `LLM_CACHE_DIR=<project>\results\raw\llm_cache` appended to .env
(git-ignored path, no repo change). From now on, identical calls at
temperature 0 replay from disk — kills and reruns become genuinely
near-free. Note for interpretation: enabling the cache does NOT change
model behaviour (it returns the same response an identical call already
produced); it only removes re-generation cost. Runs that must be
independent replications (different seeds/tags) produce different prompts
and are unaffected.

**Also tonight:** the #20 tuning run was externally killed twice more
(21:10 mid-v2, 21:14 shortly after relaunch) — third and fourth such kills,
still no script error. Relaunched with cache enabled; v0/v1 results survive
in the log (v0: precision 0.05, FP 19/38; v1_quote_gate: precision 0.11,
FP 8/38 — false alarms halved at equal recall).


---

## 2026-07-13 — Validator-prompt tuning complete: quote-first wins offline; confirmatory in-run test launched (task #20)

**Offline benchmark done** (fresh TPD window, ~13 min, zero parse errors).
Canonical numbers from `results/summaries/phase39_validator_tuning.csv`
(per-row detail in `results/raw/phase39_validator_tuning_rows.csv`):

| variant | flags | flag precision | recall (of 2) | false alarms (of 38) | binary agreement |
|---|---|---|---|---|---|
| v0_original | 19 | 0.053 | 1/2 | 18 (47%) | 0.525 |
| v1_quote_gate | 9 | 0.111 | 1/2 | 8 (21%) | 0.775 |
| **v2_quote_first** | 13 | **0.154** | **2/2** | 11 (29%) | 0.725 |
| v3_prior | 11 | 0.091 | 1/2 | 10 (26%) | 0.725 |

**Winner: v2_quote_first** — the only variant catching both human-labeled
errors, at 3× the original's precision with false alarms cut 47%→29%. The
structural fix (produce the evidence quote BEFORE the verdict) beats both
the softer rule-only gate (v1: fewest false alarms but half the recall)
and the explicit base-rate prior (v3: strictly worse than v2 — telling the
model "90% are faithful" helped less than forcing it to look first).
Note: the regenerated v0 differs by one row from the pre-cache interim
(18 vs 19 FP) — API nondeterminism at temperature 0, as documented in
§5.4.1; the archived CSV is the record.

**Honest ceiling:** offline flag precision 0.154 is still far from the
oracle regime. Back-of-envelope, halving the false-alarm rate at doubled
sensitivity moves in-run quarantine precision from ~6% to only ~15-20%
(precision is base-rate-bound). Expectation going in: the tuned arm should
*soften* the mitigated pathologies, not reach sub-critical R₀ — either
outcome is informative for the dose-response story (#23).

**Caveats (recorded before the confirmatory run):** n=40 with 2 positives —
recall is measured on n=2 and precision estimates are coarse; all 40 rows
were used for selection (no held-out split), so the offline numbers are
optimistically biased for v2; the confirmatory test is the in-run rerun,
not this benchmark. The offline benchmark judges triplet-vs-passage;
in-run the judge sees triplet-vs-KG-evidence — the prompt was adapted
(passage_quote → evidence_quote), carrying over the two portable fixes:
evidence-then-verdict ordering, and absence-of-evidence = UNCERTAIN,
never UNSUPPORTED (under the 0.4 quarantine threshold, the second rule is
what stops sparse-evidence pristine nodes being quarantined).

**Wiring:** `OrchestrationAgent(validator_prompt="tuned")` selects the new
`_TUNED_SYSTEM_PROMPT` (same model, same JSON verdict/confidence/reason
contract, same thresholds — only the judgement rules change);
`ValidationAgent` passes it through; `run_contamination.py` exposes
`--validator-prompt {default,tuned}`; new config
`contamination_mitigated_tuned.yaml` = mitigated arm + `validator_prompt:
tuned`, tag `mitigated_tuned`, seed 42. Offline smoke tests pass (prompt
selection, invalid-value rejection, config load).

**Confirmatory run LAUNCHED** (clean-room, seed 42): the dose-response
middle point mitigated(8B default, pooled quarantine precision 5.9%, R₀
4.46±2.36) → mitigated(8B tuned, this run) → oracle (R₀ 0.79). Primary
readouts: in-run quarantine precision, R₀, AUROC (does the confidence-
laundering degradation soften?), probe trajectory. Single seed — will be
labelled as such per discipline rule 2.


---

## 2026-07-13 (afternoon) — Confirmatory run REFUTES the projection: tuned judge catches nothing (task #20 DONE)

**Run completed** (launched 11:27, finished 13:11; TPD cap hit 12:20, final
eval battery crawled on retries, zero failed calls). Archives:
`phase39_mitigated_tuned_{manifest.json,trajectory.csv}`,
`phase39_sir_fit_mitigated_tuned.csv` in `results/summaries/`.

**Results (single seed 42):** propagated 14 / exposed 63 (mid-range of the
default arm's 15.0±12.8 / 60.5±25.7); quarantined 27 nodes — **0
contaminated, 27 clean → in-run quarantine precision 0/27 = 0%** (steps 1–5
quarantined nothing at all); **fitted γ = 0.0000, R₀ undefined** — the arm
is epidemiologically identical to running no validation; probe rate flat
0.850→0.796; **detection AUROC 0.804**, below even the default judge's
0.859±0.013 (~13 baseline SD under the 0.899 envelope; single seed). The
laundering intensified: a judge that near-always says SUPPORTED boosts
audited survivors (contaminated included) to conf 1.0 while its only
conf-0 nodes are clean — the detection signal actively inverts.

**The finding (structural, the real yield of task #20):** offline flag
precision and in-run quarantine precision are DIFFERENT QUANTITIES. Offline,
the judge sees the source passage — contradicting text exists to be quoted.
In-run, the judge sees retrieved KG evidence, and a contaminated node is
typically the graph's ONLY assertion of its "fact" (corruption by
replacement, not coexistence) — there is nothing contradicting to quote, so
an evidence-gated judge structurally cannot fire on real contamination. The
default judge's few true positives came from being flag-happy;
contradiction-gating removed the false-alarm mass and the accidental true
positives together. Self-consistency checking against the contaminated
memory cannot detect replacement contamination; detection needs a channel
the KG does not contain (source passages, provenance verdicts, ground
truth). Converges with the #19 truth-channel conclusion: provenance-level
defences over content validation.

**Decisions:** task #20 CLOSED with "prompt engineering cannot reach the
required precision regime — it trades indiscriminate flagging for
structural blindness" as the recorded finding. #23 (noisy-oracle precision
sweep) PROMOTED to primary RQ4 dose-response evidence, as pre-registered
this morning. #15 (ancestor-excluded validation) stays demoted — the
blindness mechanism is upstream of circular validation and #15 cannot
rescue judge sensitivity.

**Side yield:** first in-run USR numbers ever recorded (the #16 columns
work end-to-end): hotpot_usr 0.27→0.33, abstain rate 0.54→0.58 across the
run — replicating the oracle-arm replay's ~0.6 abstention under the 0.5
retrieval floor, now measured in-run.

**ch5 §5.4.3 finalised** (no [PENDING-#20-RUN] remains; carries the
single-seed label and the AUROC-construction caveats); §5.5 SIR table +
prose gain the γ=0 row; ch3 §3.6 arm table already had the row from this
morning.
