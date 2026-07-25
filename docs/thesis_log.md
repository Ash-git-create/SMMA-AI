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

## 2026-07-23 — Timeline reset: implementation push before 2026-08-05 write-up start; task #23 built, ch4 drafted, figures produced

**Context.** Ashwin set a hard deadline: all implementation work complete by
end of July 2026 (2026-07-31), thesis writing begins 2026-08-05. Ten days
elapsed since the task #20 close-out (2026-07-13); the Groq TPD window is
fresh. Verified from the git snapshot that all four commits from that
session (A USR metrics, B validator wiring, C phase39 archives, D docs) had
already landed on `main` — the "VERIFY next session" item from that
session's memory is resolved, no re-commit needed.

**Parallel work dispatched** (per updated instruction to parallelize
non-dependent work across agents):

1. **Task #26 (figures) — DONE.** `scripts/make_figures.py` (matplotlib,
   Agg backend, reproducible from archived CSVs only) produces three
   figures to `docs/figures/`: baseline per-seed trajectories, empirical-
   vs-fitted I(t) small-multiples per arm, and the R₀-per-arm bar chart with
   the R₀=1 threshold line. The γ=0 arms (baseline, floor, mitigated_tuned)
   are annotated "undefined (γ=0)" rather than given fake bars — verified
   visually. Both `[FIG]` markers in ch5 §5.1/§5.5 are now satisfied; no
   other `[FIG]` markers exist in ch5.
2. **Ch4 (implementation chapter) — DRAFTED.** New
   `docs/chapters/ch4_implementation.md`, written from the actual source
   (not CLAUDE.md's aspirational description) — sections 4.1–4.9 covering
   architecture, KG/provenance schema, the agent ensemble, error injection,
   Trio mechanics, SIR instrumentation, evaluation harness, run protocol,
   and engineering constraints. No results numbers (design constants only,
   cited to file). Flags several code-vs-CLAUDE.md discrepancies worth
   carrying into the final write-up: `OrchestrationAgent` is actually just
   the judge (pipeline orchestration lives in `run_contamination.py`);
   `src/evaluation/experiment_runner.py` (named in CLAUDE.md's tree) does
   not exist, runners are `scripts/run_*.py`; disjunctive lineage /
   `noisy_or` is implemented but never exercised (all lineage is
   conjunctive in practice); trajectory CSV `S`/`I`/`R` are operational
   bookkeeping, not epidemic compartments (`fit_sir.py` reconstructs the
   real I(t)/R(t) from ground-truth columns — a trap worth flagging
   prominently in ch4 since it is easy to misread the raw CSV). Still needs
   a pass to cross-check figure/number cross-references once ch5 finalises
   further and a full read-through for voice consistency with ch3/ch5.
3. **Task #25 (second-rater kappa) — IN PROGRESS.** First attempt failed
   immediately on a Fable 5 usage-credits limit before writing any code
   (account-level, not a task failure). Relaunched under Sonnet. Result
   pending as of this entry.

**Task #23 (noisy-oracle precision sweep) — BUILT, not yet run.**
Implemented directly (not delegated, since it touches the same files as
task #20's judge-mode wiring): `ValidationAgent` gains
`oracle_sensitivity` (P(flag | contaminated), default 1.0) and
`oracle_false_alarm` (P(flag | clean), default 0.0) — at defaults this is
byte-identical to the existing perfect oracle. A false alarm receives the
full quarantine treatment (state R, conf 0, cascade deprecation), so it
exercises the same collateral-damage channel a real judge's false positives
do, at a controlled, reproducible rate (`oracle_seed`, decoupled from
`random_seed`). Wired through `run_contamination.py` as
`--oracle-sensitivity` / `--oracle-false-alarm` / `--oracle-seed`.
Verified: the Bernoulli draw logic hits target rates over 2000 trials
(sensitivity 0.5→0.485, false-alarm 0.1→0.095), the constructor rejects
out-of-[0,1] knob values, and the full CLI→config→argparse path parses
correctly for all four new configs with `run_experiment` stubbed out
(no Neo4j needed for this check).

Four sweep configs created
(`experiments/configs/contamination_oracle_p{75,50,25,10}.yaml`), each
identical to `contamination_oracle.yaml` except the false-alarm knob. The
false-alarm rates are DERIVED, not guessed: solved from
precision = sens·prev / (sens·prev + fa·(1−prev)) using the MEASURED
audited-candidate contamination prevalence from the archived perfect-oracle
run (`phase38_oracle_trajectory.csv`: 12 true quarantines / 250 audited =
4.8%) — fa = 0.0168 / 0.0504 / 0.1513 / 0.4538 for targets 0.75 / 0.50 /
0.25 / 0.10. These are targets only; realized precision is
prevalence-dependent and will be read per-run from the trajectory's
`det_R_contam`/`det_R_clean` columns, exactly as the existing arms are
reported — the config file comments say so explicitly, so a stale
derivation cannot masquerade as a result later. The p=1.0 point is not
re-run; it reuses the archived `phase38_oracle` run per the pre-existing
plan to coordinate with task #24.

**Blocked on Neo4j.** Bolt port 7687 unreachable this session — Desktop-
managed, only Ashwin can start it. None of the four sweep runs, nor any
further contamination-pipeline work, can execute until then. A relaunch
script (`run_oracle_sweep.ps1`, session scratchpad) is ready: 3-stage clean
room + 40×15s preflight poll, parameterized by sweep point, one arm per
invocation (they must run sequentially — each does its own `load_kg
--clear`). Oracle audits cost zero Groq calls regardless of the
false-alarm rate (ground-truth lookup, not an LLM judge), so only
synthesis (Mistral) and the step-0/5/10 task+probe evaluations (Groq) draw
budget — materially cheaper than the judged arms (#14/#20), so more than
one sweep point should fit in a day once Neo4j is available.

**Next when Neo4j is up:** run the four sweep points (p75→p10, one at a
time), archive each trajectory/manifest to `results/summaries/`, fit SIR
per point, extend the ch5 §5.4/§5.5 dose-response narrative and the R₀ bar
chart with the new points, and fold in task #24 (oracle seed replication)
at the p=1.0 point to close out the RQ4 evidence base before 2026-07-31.

## 2026-07-23 (later) — Task #25 DONE: independent second-rater shows only slight-to-fair agreement; Neo4j back up, oracle sweep launched

**Task #25 complete.** `scripts/second_rater.py` (Sonnet-built after the
Fable-5-credits retry) rates the same 40 blind-calibration rows with
`open-mistral-nemo` (Mistral API) — a model family independent of both
existing raters (Ashwin's blind human labels, task #17; the
`llama-3.1-8b-instant` judge under calibration). Same rubric, same
5-label fidelity taxonomy (`SUPPORTED`/`QUALIFIER_LOSS`/`ENTITY_ERROR`/
`RELATION_ERROR`/`UNSUPPORTED`), same information shown (source passage +
SPO), imported verbatim from `audit_natural.py` so the task matches the
original blind task exactly. Kappa cross-checked against
`sklearn.metrics.cohen_kappa_score` — exact match to the hand-rolled
implementation. File mapping verified before running:
`phase34_judge_calibration_blind_v2.csv` (cp1252, passages + human labels)
joined to `phase34_judge_calibration_results.csv` (judge verdicts) on
`triplet_id`, identical id sets confirmed for both files (n=40).

Results (`results/summaries/phase39_second_rater.csv`, 0 parse errors,
n=40 both comparisons):

| Comparison | Cohen's κ | Raw agreement | Expected (chance) agreement |
|---|---|---|---|
| second rater vs. human | 0.151 | 80.0% | 76.4% |
| second rater vs. original judge | 0.261 | 57.5% | 42.5% |

Both fall in the "slight" (vs. human) to "fair" (vs. judge) bands on the
Landis–Koch scale. The high raw-vs-chance gap for the human comparison
(80% raw but only 0.151 κ) is a base-rate artifact: `SUPPORTED` dominates
the 40-row sample, so most of the 80% agreement is two raters both
defaulting to the majority label, not real signal — exactly the effect
Cohen's κ is designed to strip out. **This independently corroborates the
#17/#20 finding from a different angle**: it is not only the Groq judge
that struggles at this task under this rubric — a second, architecturally
different model shows limited agreement with both the human ground truth
and the judge being calibrated, suggesting the 5-label fidelity
distinction itself is a hard rating task at this evidence granularity, not
solely a `llama-3.1-8b-instant` weakness. Feeds thesis §5.6.

**Neo4j is back up** (Ashwin started it). Bolt port confirmed reachable.
Launched task #23's first sweep point (`contamination_oracle_p75`,
target quarantine precision ≈0.75) in the background via the staged
`run_oracle_sweep.ps1` — clean-room reload confirmed started
(50,000 T-REx triplets loading). Remaining three points (p50, p25, p10)
queue sequentially once this one finishes and is archived, per the
one-at-a-time constraint (each does its own `load_kg --clear`).

## 2026-07-23 (evening) — Oracle sweep point p75 complete; p50 launched

**p75 (target audit-level precision 0.75, `oracle_sensitivity=1.0`,
`oracle_false_alarm=0.0168`) — DONE.** Ran end-to-end in ~13 minutes (clean
room → extraction → contamination), far faster than any judged arm since
oracle audits cost zero Groq calls. Archived to
`results/summaries/phase40_oracle_noisy_p75_{manifest.json,trajectory.csv}`,
SIR fit at `phase40_sir_fit_oracle_noisy_p75.csv`.

Realized final quarantine precision (`det_R_contam / (det_R_contam +
det_R_clean)`, the same definition used for every other arm's reported
precision, cascade collateral included) = 17/65 = **26.2%** — notably
below both the *design target* (0.75, an audit-level flag precision that
does not account for downstream cascade collateral) and the perfect
oracle's realized 33.3% (16/48, `phase38_oracle`). This is expected and
was flagged in the config comments in advance: adding false alarms on top
of perfect recall can only ever pull realized precision down from the
perfect-oracle ceiling, and cascade deprecation dilutes precision further
regardless of the audit-level flag rate — the two "precision" numbers
(design-time audit flag rate vs. realized final quarantine precision) are
genuinely different quantities, same lesson as the #20 offline-vs-in-run
gap but from a controllable-parameter direction this time rather than a
model behaviour.

Propagated = 15 (sum gt_prop_*), exposed = 50 (cum_exposed final), γ =
0.0463, β = 0.0324, **R₀ = 0.699** — sub-critical, and (single seed, noted)
even slightly *below* the perfect oracle's 0.79. Detection AUROC = 0.903,
also nominally above the perfect oracle's 0.899 (single-seed noise at this
sample size — 500 random clean vs a few dozen contaminated nodes — not
claimed as a real effect). hotpot_em 0.10, fever_accuracy 0.60 (flat as
always). Full numbers in the archived trajectory CSV.

**p50 launched** (target 0.50, `oracle_false_alarm=0.0504`) via the same
relaunch script, running normally as of this entry. p25 and p10 queue after.

## 2026-07-23 (evening, cont.) — p50 complete; p25 launched

**p50 (target audit-level precision 0.50, `oracle_false_alarm=0.0504`) —
DONE.** Archived to
`results/summaries/phase40_oracle_noisy_p50_{manifest.json,trajectory.csv}`,
SIR fit `phase40_sir_fit_oracle_noisy_p50.csv`. Realized final quarantine
precision = 17/84 = **20.2%** (monotone below p75's 26.2%, as expected —
more induced false alarms, more collateral). Propagated 16, exposed 50.
β = 0.0351, γ = 0.0458, **R₀ = 0.765** — still sub-critical (single seed),
close to but not identical to the perfect oracle's 0.79 and p75's 0.699;
no monotone R₀-vs-precision trend is claimed yet from 3 points at n=1 each.
Detection AUROC 0.905. hotpot_em 0.10, fever_accuracy 0.60.

**p25 launched** (target 0.25, `oracle_false_alarm=0.1513`).

## 2026-07-23 (evening, cont. 2) — p25 complete; p10 (final sweep point) launched; monotone trend visible

**p25 (target audit-level precision 0.25, `oracle_false_alarm=0.1513`) —
DONE.** Archived to
`results/summaries/phase40_oracle_noisy_p25_{manifest.json,trajectory.csv}`,
SIR fit `phase40_sir_fit_oracle_noisy_p25.csv`. Realized final quarantine
precision = 16/152 = **10.5%** (collateral damage `det_R_clean` grew to
136, roughly 2x p50's 67 — cascade collateral compounds faster than the
false-alarm rate as more clean-adjacent nodes get pulled in). Propagated
16, exposed 54. β = 0.0358, γ = 0.0436, **R₀ = 0.823** — still
sub-critical (single seed).

**Provisional dose-response, 3 points so far (single seed each — hedge
accordingly):**

| Point | Design target | Realized precision | R₀ |
|---|---|---|---|
| p75 | 0.75 | 26.2% | 0.699 |
| p50 | 0.50 | 20.2% | 0.765 |
| p25 | 0.25 | 10.5% | 0.823 |
| oracle (phase38) | 1.00 | 33.3% | 0.79 |

A monotone R₀-vs-realized-precision trend is visible (R₀ rises as
precision falls) — notable that even the LOWEST precision point so far
(p25, 10.5%) stays sub-critical, well above the LLM-judge arms' realized
precision (default 5.9%, tuned 0%) which were super/critical-to-undefined.
This suggests recall, not precision, may be doing more of the sub-critical
work in the oracle arms — worth stating as a hypothesis, not a conclusion,
until p10 (target 0.10, closest to the LLM-judge regime) lands.

**p10 launched** (target 0.10, `oracle_false_alarm=0.4538`) — the last
sweep point.

## 2026-07-23 (night) — Task #23 sweep COMPLETE: all 5 points sub-critical; recall, not precision, appears to be the dominant containment lever

**p10 (target audit-level precision 0.10, `oracle_false_alarm=0.4538`) —
DONE**, the final sweep point. Archived to
`results/summaries/phase40_oracle_noisy_p10_{manifest.json,trajectory.csv}`,
SIR fit `phase40_sir_fit_oracle_noisy_p10.csv`. Realized final quarantine
precision = 18/271 = **6.6%** (collateral `det_R_clean` = 253, by far the
largest of the sweep — nearly the entire audited-and-flagged population is
now clean facts caught in cascade blast radius). β = 0.0353, γ = 0.0473,
**R₀ = 0.746**.

**Full sweep table (all single seed = 42; oracle_sensitivity = 1.0 held
fixed throughout — only oracle_false_alarm varies):**

| Point | Design target precision | Realized precision (incl. cascade) | β | γ | R₀ | Propagated | Exposed |
|---|---|---|---|---|---|---|---|
| p75 | 0.75 | 26.2% (17/65) | 0.0324 | 0.0463 | 0.699 | 11 | 50 |
| p50 | 0.50 | 20.2% (17/84) | 0.0351 | 0.0458 | 0.765 | 16 | 50 |
| p25 | 0.25 | 10.5% (16/152) | 0.0358 | 0.0436 | 0.823 | 16 | 54 |
| p10 | 0.10 | 6.6% (18/271) | 0.0353 | 0.0473 | 0.746 | 12 | 54 |
| oracle (phase38, perfect) | 1.00 | 33.3% (16/48) | 0.028 | 0.036 | 0.79 | — | 44 |

**Retracting the mid-sweep "monotone trend" hypothesis (stated in the
p25 entry above) — it does not survive p10.** R₀ does not move monotonically
with realized precision (p10's R₀ 0.746 sits BELOW p25's 0.823 despite p10
having roughly half p25's precision). At n=1 per point this is exactly the
kind of thing the seed-noise rule warns about: with only single-seed β/γ
fits, run-to-run fluctuation of this size (β ranges 0.032–0.036, γ ranges
0.044–0.047 across all 4 points — a narrow band) is plausibly noise, not
signal, and no functional R₀(precision) relationship is claimed from this
data.

**What IS robust across the sweep, and is the actual finding:** every
single point — spanning realized precision from 6.6% to 33.3%, more than a
5x range — stayed sub-critical (R₀ 0.699–0.823, all comfortably below 1),
while the LLM-judge arms at broadly similar or higher realized precision
(default 5.9%, task #14; tuned 0%, task #20) were super-critical
(R₀ 4.46±2.36) or undefined (γ=0) respectively. The one parameter held
fixed across the entire oracle sweep and different between the oracle and
LLM-judge arms is **recall**: `oracle_sensitivity = 1.0` throughout (every
contaminated node gets a fair chance at being flagged), versus the LLM
judges' unmeasured-but-evidently-poor recall on real (replacement-type)
contamination (the #20 structural-blindness mechanism: an evidence-gated
judge cannot even attempt to flag a fact with no contradicting evidence).
**Working hypothesis for RQ4: containment (R₀ sub-criticality) is driven
predominantly by validator RECALL, not PRECISION; precision instead
governs the collateral-damage cost of validation** (`det_R_clean` scales
from 32 at fa=0 to 253 at fa=0.45 — a ~8x increase — while R₀ stayed in a
narrow sub-critical band throughout). This is a single-seed, single-KG-draw
observation across 5 points and needs replication (see #24) before being
promoted past "hypothesis" — but it reframes the RQ4 story: judge FAILURE
in the real arms may be a recall failure dressed up as a precision problem,
which changes what a fix should target (catch more real contamination,
even at higher false-alarm cost) rather than what task #20 tried (raise
precision by refusing to flag without contradicting evidence, which this
sweep suggests trades away exactly the wrong thing).

**Task #23 CLOSED.** All 4 sweep points + the existing p=1.0 archive give
a 5-point precision sweep at fixed recall=1.0; this is now the primary RQ4
dose-response evidence as pre-registered. Detection AUROC across the sweep:
0.903 (p75), 0.905 (p50), 0.902 (p25), 0.902 (p10) — flat
around 0.90, consistent with the perfect-oracle's 0.899, and unlike the
LLM-judge arms shows no laundering degradation regardless of induced
false-alarm rate, because clean nodes are never re-scored upward in oracle
mode (by construction, Section 4.3.3) — false alarms zero a clean node's
confidence rather than inflating a contaminated one's.

**Next:** #24 (oracle seed replication at p=1.0) should now target
confirming or refuting the recall-vs-precision hypothesis — ideally by
replicating at LEAST ONE noisy point (p10, the most judge-like) across 2-3
more seeds, not just the perfect-oracle point, since the hypothesis lives
in the noisy arms. Ch5 §5.4/§5.5 and the R₀ bar chart figure need
extending with these 5 points.

## 2026-07-23 (late night) — CORRECTION: p10 seed replication shows large R₀ variance; "always sub-critical" claim was premature at n=1

**p10 seed 43 replicate — DONE.** Same config as p10 (target audit-level
precision 0.10, `oracle_false_alarm=0.4538`, `oracle_sensitivity=1.0`),
`--random-seed 43` (changes injection placement only, per the seeding
semantics of Section 4.8.3 — LLM generation is not seed-controlled).
Archived to `results/summaries/phase40_oracle_noisy_p10_s43_
{manifest.json,trajectory.csv}`, SIR fit
`phase40_sir_fit_oracle_noisy_p10_s43.csv`.

**β = 0.0503, γ = 0.0522, R₀ = 0.964** — nominally still sub-critical, but
this is a swing of **+0.22 in R₀** from a single seed change at the same
precision point (seed 42: 0.746; seed 43: 0.964). Propagated = 20 (vs.
seed 42's 12), exposed = 92 (vs. 54) — the seed-43 draw produced
substantially more spread by every raw count, not just the fitted R₀.
Realized precision this seed: 22/243 = 9.05% (close to seed 42's 6.6%, so
the precision knob itself is behaving consistently — the spread outcome
varies, not the validator's realized behaviour).

**This directly weakens the "all 5 points robustly sub-critical" framing
from the sweep-completion entry a few hours ago.** That entry was written
at n=1 per point and is now shown to have understated the variance: R₀ at
p10 alone spans at least [0.746, 0.964] across 2 seeds — comfortably
inside sub-critical territory so far, but close enough to 1.0 that a third
seed landing above 1 would not be shocking. Per the project's seed-noise
discipline (single-run differences below ~2 baseline SD are noise; no
headline survives on n=1), **the "recall drives containment" hypothesis is
NOT retracted, but its confidence is downgraded** — it may still be right
that recall matters more than precision for containment, but "sub-critical
across a 5x precision range" was an overclaim built on single-seed points
that plausibly have their own multi-seed spread just like every other arm
in this project has shown (baseline 17.8±4.0 propagated; full-Trio ~10x
variance amplification, task #14). A third p10 seed (44) is running now to
see whether [0.746, 0.964, ?] clusters sub-critical or straddles 1.0.

**Lesson for the write-up discipline, recorded per rule 5 (retractions are
recorded, not overwritten):** the sweep-completion entry's "all 5 points
sub-critical" line stands as written (it was true of the data available at
the time) but must now be read alongside this correction — ch5 must not
quote that line without the multi-seed caveat that follows here.

## 2026-07-23 (still later) — p10 seed 44: SUPER-CRITICAL (R₀=1.105). p10 straddles the threshold; launching seed 45 to complete n=4

**p10 seed 44 replicate — DONE.** Same config, `--random-seed 44`.
Archived to `results/summaries/phase40_oracle_noisy_p10_s44_
{manifest.json,trajectory.csv}`, SIR fit
`phase40_sir_fit_oracle_noisy_p10_s44.csv`.

**β = 0.0472, γ = 0.0428, R₀ = 1.105 — SUPER-CRITICAL.** This is the first
super-critical result in the entire noisy-oracle sweep, and it appears at
p10 (the lowest tested precision, still under perfect recall). Propagated
= 18, exposed = 65 — both mid-range between seed 42 and seed 43's counts,
so this is not an outlier-count run producing an outlier fit; the SIR fit
genuinely crossed the line.

**p10 across 3 seeds (42/43/44): R₀ = [0.746, 0.964, 1.105], mean = 0.938,
SD = 0.181 (n=3).** The mean sits just under 1.0 but the SD is wide enough
that the interval straddles the critical threshold — this is NOT a
robustly sub-critical arm. Contrast with the ~2-SD noise-hedging rule: a
single point 1.105 is well within 1 SD of the 3-seed mean, i.e., this
looks like real spread around a borderline-critical mean, not an outlier
to be explained away.

**Revised reading of task #23 (supersedes the earlier "recall alone keeps
containment sub-critical" framing):** perfect recall does NOT guarantee
sub-criticality by itself. At the higher-precision sweep points (p75, p50,
p25 — each still single-seed, not yet replicated) R₀ stayed comfortably
under 1; at the lowest precision tested (p10, ≈6-9% realized), R₀ is
genuinely borderline across seeds, with one seed already over. The
interpretation now on the table: recall may raise the FLOOR on
containment relative to the LLM-judge arms (whose R₀ was unambiguously
super-critical, 4.46±2.36, at similar-or-better precision) — i.e. recall
matters and the earlier hypothesis direction is not wrong — but it is not
a free pass at arbitrarily low precision; there is likely still a
precision floor below which even perfect-recall validation loses
sub-criticality. p10's realized precision (6.6-9%) may be near or below
that floor. This needs the higher-precision points replicated too before
any quantitative floor estimate is defensible — right now only p10 has
seed replication.

**Launching seed 45** to complete an n=4 envelope at p10 (matching this
project's established multi-seed convention — baseline and mitigated arms
both used seeds 42-45), so the p10 point can be reported with the same
n=4 mean±SD format already used throughout Chapter 5, rather than as an
n=3 orphan.

## 2026-07-23 (close-out) — p10 n=4 envelope complete: R₀ = 0.911 ± 0.158, 1/4 seeds super-critical. Task #23/#24-extension DONE.

**p10 seed 45 — DONE.** β = 0.0325, γ = 0.0393, R₀ = 0.828. Archived to
`results/summaries/phase40_oracle_noisy_p10_s45_{manifest.json,
trajectory.csv}`, SIR fit `phase40_sir_fit_oracle_noisy_p10_s45.csv`.

**p10 full n=4 envelope (seeds 42/43/44/45): R₀ = [0.746, 0.964, 1.105,
0.828], mean = 0.911, SD = 0.158.** In the same mean±SD format as every
other multi-seed arm in this thesis: **R₀ = 0.911 ± 0.158 (n=4)**. 1 of 4
seeds (44) crossed into super-critical territory; the mean sits
sub-critical but well within its own SD of the threshold, so "sub-critical"
is a mean-level statement with real single-seed exceptions, not a uniform
property of the arm.

**Final, properly-hedged reading of task #23 for RQ4 (supersedes both the
mid-sweep monotone-trend claim and the "robustly sub-critical across the
whole precision range" claim — both explicitly retracted per rule 5):**

| Arm | Realized precision | n | R₀ (mean ± SD) |
|---|---|---|---|
| p10 (noisy oracle, perfect recall) | 6.6–9% | 4 | **0.911 ± 0.158** |
| p25 (noisy oracle, perfect recall) | 10.5% | 1 | 0.823 |
| p50 (noisy oracle, perfect recall) | 20.2% | 1 | 0.765 |
| p75 (noisy oracle, perfect recall) | 26.2% | 1 | 0.699 |
| oracle (perfect, phase38) | 33.3% | 1 | 0.79 |
| mitigated (LLM judge, task #14) | 5.9% pooled | 4 | 4.46 ± 2.36 |
| mitigated_tuned (LLM judge, task #20) | 0% | 1 | undefined (γ=0) |

The headline that survives: **at every tested precision level under
perfect recall — including p10's 6.6–9%, comparable to or below the
LLM-judge arms' realized precision — mean R₀ stays sub-critical**, and the
gap to the LLM-judge arms (4.46±2.36, wildly super-critical, at similar or
better precision) is large. Perfect recall is doing real work. **But it is
not a hard guarantee**: p10's own seed variance shows individual runs can
cross the threshold even under perfect recall, when precision is low
enough — recall widens the margin, it does not eliminate the cliff. The
p75/p50/p25 points remain single-seed and their true variance is unknown;
given how much p10 moved (0.746→1.105 range), they should not be treated
as more certain than p10's pre-replication single point looked.

**Task #23 (noisy-oracle precision sweep) and the ad-hoc #24 extension
(seed replication at the p10 point) are DONE.** This is now the complete,
correctly-hedged primary RQ4 dose-response evidence base: 4 precision
points (1 with n=4, 3 with n=1) plus the existing perfect-oracle anchor,
against the LLM-judge failure arms. Remaining open item, not blocking:
p75/p50/p25 could be replicated to the same n=4 standard if time allows
before 2026-07-31, but the core RQ4 claim (recall matters, is not
sufficient alone) is already defensible without them.

**Neo4j window used for:** 4 sweep points + 3 seed replicates = 7 full
contamination runs today, all zero-Groq-judge-call oracle audits — the
"cheaper sweep" prediction from earlier in the day held up well in
practice.

## 2026-07-24 — Extending seed replication to p75/p50/p25; p75 seed 43 is ALSO super-critical (R₀=1.096)

Following up on the p10 n=4 result, replicating p75/p50/p25 to the same
n=4 standard to check whether p10's seed variance was unusual or the norm
across the whole sweep. Launched p75/p50/p25 seeds 43-45 sequentially
(`run_oracle_point_seed.ps1`, generalizes the p10 seed-replicate script to
any sweep point).

**p75 seed 43 — DONE.** β = 0.0424, γ = 0.0387, **R₀ = 1.096 —
SUPER-CRITICAL.** Archived to `results/summaries/phase40_oracle_noisy_p75_
s43_{manifest.json,trajectory.csv}`, SIR fit
`phase40_sir_fit_oracle_noisy_p75_s43.csv`.

**This is an important update to the emerging picture.** p75 was the
*highest*-precision sweep point (26.2% realized at seed 42) and its first
seed looked the most comfortably sub-critical of the four (0.699). A
second seed crossing to 1.096 suggests the seed-to-seed R₀ variance seen
at p10 is not special to low precision — it may be a property of this
whole experimental setup (consistent with the baseline arm's own
substantial multi-seed spread, 17.8±4.0 propagated, and the ~10x variance
amplification documented for the full-Trio arm in task #14). **Working
revision: seed variance in this pipeline is large enough that NO single
noisy-oracle point should be treated as reliably sub-critical or
super-critical from fewer than ~4 seeds — including p75, p50, and p25,
which are still single-seed as of the previous entries.** This reframes
task #23's contribution: the LLM-judge arms' failure (R₀ 4.46±2.36,
consistently and by a wide margin super-critical across all 4 of their
seeds) is categorically different from anything seen in the oracle sweep
so far — even the "worst" oracle point's seed spread does not approach
that magnitude — but the oracle sweep's own within-point variance is
turning out to be a substantial part of the story, not a nuisance to
average away.

p75 seed 44 launched next.

## 2026-07-24 (cont.) — p75 seed 44 ALSO super-critical (R₀=1.197); p75 running mean now ~1.0. Seed 45 launched.

**p75 seed 44 — DONE.** β = 0.0467, γ = 0.0390, **R₀ = 1.197 —
SUPER-CRITICAL**, higher than seed 43's 1.096. Archived to
`results/summaries/phase40_oracle_noisy_p75_s44_{manifest.json,
trajectory.csv}`, SIR fit `phase40_sir_fit_oracle_noisy_p75_s44.csv`.

**p75 across 3 seeds (42/43/44): R₀ = [0.699, 1.096, 1.197], mean = 0.997,
SD = 0.267 (n=3).** Two of three seeds are now super-critical. The running
mean sits almost exactly ON the critical threshold — this is a much
starker result than p10's eventual 0.911±0.158 (1/4 super-critical). If
this holds through seed 45, **p75 — the point with the HIGHEST realized
precision in the entire noisy-oracle sweep (26.2% at seed 42) — may turn
out to be no more reliably sub-critical than the lowest-precision point
(p10)**, which would be a genuinely surprising and important result:
realized precision, across the tested 6.6%-26.2% range, may simply not be
predictive of single-run R₀ under perfect recall; only the recall/no-recall
distinction (oracle-family vs. LLM-judge arms) shows a large, consistent
effect. Seed 45 launched to complete p75's n=4.

## 2026-07-24 (cont.) — p75 n=4 complete: R₀ = 0.928 ± 0.256, 2/4 seeds super-critical. Nearly identical mean to p10, wider variance.

**p75 seed 45 — DONE.** β = 0.0287, γ = 0.0399, R₀ = 0.719. Archived to
`results/summaries/phase40_oracle_noisy_p75_s45_{manifest.json,
trajectory.csv}`, SIR fit `phase40_sir_fit_oracle_noisy_p75_s45.csv`.

**p75 full n=4 envelope (seeds 42/43/44/45): R₀ = [0.699, 1.096, 1.197,
0.719], mean = 0.928, SD = 0.256 (n=4). β = 0.0376 ± 0.0084, γ = 0.0410 ±
0.0036.** 2 of 4 seeds (43, 44) are super-critical.

**Direct comparison, both now n=4:**

| Point | Realized precision (seed 42) | R₀ mean ± SD (n=4) | Super-critical seeds |
|---|---|---|---|
| p75 | 26.2% | **0.928 ± 0.256** | 2/4 |
| p10 | 6.6% | 0.911 ± 0.158 | 1/4 |

**This is the clearest statement of the finding yet:** across a 4× spread
in realized precision (6.6% vs 26.2%), the mean R₀ is essentially
identical (0.93 vs 0.91) — and if anything the HIGHER-precision point has
MORE variance and a higher super-critical rate, the opposite of what a
precision-driven story would predict. Under this experimental design
(perfect recall, precision varied only via induced false alarms), realized
precision in the 6-26% range shows no visible relationship to single-run
R₀ outcome. What separates this whole family from the LLM-judge arms
(4.46 ± 2.36, all 4 seeds badly super-critical, no seed anywhere near
sub-critical) is not precision — it is recall. The mechanism candidate:
under perfect recall, every truly contaminated node that gets audited is
eventually caught; what varies run-to-run is the RACE between exposure
growth (β, driven by which entities get sampled and how fast contamination
reaches the active retrieval subgraph) and the audit's targeted-audit
coverage of the growing contaminated set — a timing/coverage story, not a
judge-quality story, once recall is saturated at 1.0.

Moving to p50 replication next (seeds 43-45) to see whether its mean also
clusters near ~0.9-0.95, which would further support the "precision
doesn't distinguish outcomes once recall=1.0" reading.

## 2026-07-24 (cont.) — p50 seed 43: R₀=0.892 (sub-critical). Seed 44 running.

**p50 seed 43 — DONE.** β = 0.0460, γ = 0.0516, R₀ = 0.892 — sub-critical.
Archived to `results/summaries/phase40_oracle_noisy_p50_s43_
{manifest.json,trajectory.csv}`, SIR fit
`phase40_sir_fit_oracle_noisy_p50_s43.csv`. p50 so far (seeds 42/43):
[0.765, 0.892] — consistent with the ~0.9 clustering seen at p10/p75.
Seed 44 launched.

## 2026-07-24 (methodological note) — p50 seed 44 exposes a construction-level insensitivity in the R₀ metric to the false-alarm/precision knob

**p50 seed 44 — DONE.** β = 0.0472, γ = 0.0428, R₀ = 1.1048641074366614
(SUPER-CRITICAL). Archived to `results/summaries/phase40_oracle_noisy_p50_
s44_{manifest.json,trajectory.csv}`, SIR fit
`phase40_sir_fit_oracle_noisy_p50_s44.csv`.

**This value is numerically identical (13 significant figures) to p10
seed 44's fitted R₀.** Before reporting it, this was checked for a script
bug — `diff` against `phase40_oracle_noisy_p10_s44_trajectory.csv` shows
the two trajectory files ARE genuinely different runs (different
`quarantined`/`cascaded`/`det_R_clean`/`hotpot_avg_facts` at every step —
e.g. final `det_R_clean` 55 vs 241, final `hotpot_avg_facts` 4.62 vs 4.62
matched here but diverged at step 5: 4.92 vs 4.66). **What matches exactly,
at every one of the 10 steps, is `gt_total` and `det_R_contam`** — the two
columns `fit_sir.py`'s I(t)/R(t) reconstruction actually uses (Section
4.6.4: `I(t) = gt_total − det_R_contam`, `R(t) = det_R_contam`;
`det_R_clean` — the column the false-alarm knob actually drives — is
excluded from the reconstruction by design, since it is collateral
damage, not part of the epidemic curve).

**Mechanistic explanation, not a bug:** p50 and p10 share `random_seed=44`
(fixing injection placement and per-step entity sampling identically) and
`oracle_sensitivity=1.0` (fixing which genuinely-contaminated audited
nodes get caught — the same ones, in the same steps, in both configs).
Only `oracle_false_alarm` differs (0.0504 vs 0.4538), and that knob only
ever flags CLEAN nodes, feeding `det_R_clean`. The two runs' operational
columns (extraction volume, quarantine counts) visibly diverge from step 6
onward — collateral quarantining IS happening at different rates and IS
perturbing what gets retrieved and extracted — but in this particular
seed's run, that perturbation never happened to touch the specific
entities/facts that determine `gt_total`/`det_R_contam`, so the epidemic
curve the SIR model is fit to came out identical by coincidence. (**By
contrast, p75 seed 44 and p10 seed 44 — same seed, same sensitivity — got
DIFFERENT R₀ (1.197 vs 1.105), so this coincidence is run-specific, not a
general identity.**)

**This is a real, useful caveat on the whole task #23 dose-response
finding, not just a data-integrity note:** the R₀ metric as currently
computed is *insensitive by construction* to the false-alarm/precision
knob except through an indirect, sometimes-negligible feedback path
(collateral quarantine → retrieval floor exclusion → different extraction
context → different propagation). Part of why R₀ has clustered so tightly
around ~0.9 across four very different induced false-alarm rates
(0.0168→0.4538, a 27× range) may therefore be a property of the
measurement construction, not solely an empirical fact about the system.
**The "recall matters, precision doesn't (once recall=1.0)" reading from
the earlier entries should be read as: recall visibly and directly moves
`det_R_contam`/R₀ (it enters the reconstruction formula); precision (via
induced false alarms) only moves R₀ THROUGH an indirect, run-dependent
retrieval-feedback channel that is frequently but not always negligible.**
This should be stated explicitly in ch5 rather than left implicit —
otherwise a reader could reasonably think the sweep proves precision is
causally inert for containment, when the more defensible claim is that
this experimental design's R₀ metric has limited *sensitivity* to
precision, for a specific, identifiable structural reason.

p50 seed 45 launched (final seed for p50's n=4).

## 2026-07-24 (p50 complete) — p50 n=4: R₀ = 0.870 ± 0.173, 1/4 super-critical. Cross-point identity (p50_s45 == p75_s45 exactly) confirms the construction-insensitivity mechanism.

**p50 seed 45 — DONE.** β = 0.0287, γ = 0.0399, R₀ = 0.719. Archived to
`results/summaries/phase40_oracle_noisy_p50_s45_{manifest.json,
trajectory.csv}`, SIR fit `phase40_sir_fit_oracle_noisy_p50_s45.csv`.

**This fitted (β, γ, R₀, RMSE) quadruple is numerically identical to p75
seed 45's**, not just p50/p10 seed 44's from the earlier entry. Consistent
with the mechanism already identified: at the two LOWEST false-alarm rates
in the sweep (p75: 0.0168, p50: 0.0504), collateral quarantine volume is
small enough that it very often does not intersect the handful of entities
actively sampled per step, so the reconstructed epidemic curve — and
therefore the fitted R₀ — comes out identical across configs at a shared
seed. This is expected to happen LESS often at p10 (fa=0.4538, the
sweep's highest collateral rate) — consistent with p10 seed 44 diverging
from a construction-identity coincidence in only one of its four seeds
while p75/p50 show it more often at the low end.

**p50 full n=4 envelope (seeds 42/43/44/45): R₀ = [0.765, 0.892, 1.105,
0.719], mean = 0.870, SD = 0.173 (n=4). β = 0.0393 ± 0.0089, γ = 0.0450 ±
0.0050.** 1 of 4 seeds (44) super-critical.

**Updated three-point comparison, all now n=4:**

| Point | Realized precision (seed 42) | R₀ mean ± SD | Super-critical seeds |
|---|---|---|---|
| p50 | 20.2% | **0.870 ± 0.173** | 1/4 |
| p10 | 6.6% | 0.911 ± 0.158 | 1/4 |
| p75 | 26.2% | 0.928 ± 0.256 | 2/4 |

All three cluster in a narrow 0.87–0.93 mean band despite the precision
axis spanning 6.6–26.2% (4×). p75 (highest precision) has BOTH the
highest mean AND by far the highest variance/super-critical rate of the
three — if anything mildly *anti*-correlated with precision, though this
is 3 points at n=4 each and not a claim to lean on quantitatively. Given
the construction-insensitivity mechanism documented above, this clustering
should be read primarily as evidence that **the false-alarm/precision
knob, as currently wired, has limited leverage over the fitted R₀ metric**
— not as strong evidence that precision is causally inert for
containment in general. The next methodologically cleaner test (not
undertaken here, time-boxed) would use a metric sensitive to
`det_R_clean` directly, or redesign the noisy-oracle mechanism so induced
false alarms are drawn from the actively-retrieved pool rather than the
full audit candidate pool, guaranteeing feedback into propagation.

p25 remains single-seed (0.823). Given the diminishing marginal insight
from further n=4 replication at this point — the construction-
insensitivity mechanism, once understood, already explains most of why
these points cluster — replication effort now shifts to writing this up
correctly in ch5 rather than running a fourth n=4 point.

## 2026-07-24 (parallel work) — Judge in-run recall MEASURED (task #28): LLM judge catches 6% of contamination; perfect recall at the same audit budget catches 30%

Token-free analysis over existing archives (Sonnet agent, verified by me
against the trajectories before acceptance — oracle 16/49=0.3265,
tuned 0/54=0.0000 spot-checks match). New:
`scripts/measure_judge_recall.py`, `results/summaries/phase41_judge_recall.csv`.

End-of-run catch rate (det_R_contam / gt_total at final step — "of all
contaminated nodes that ever existed, what fraction was quarantined"),
audit budget verified identical across all 20 runs from their manifests
(1×25 targeted audits/step):

| Arm | n | Catch rate |
|---|---|---|
| Noisy-oracle family pooled (oracle_sensitivity=1.0) | 13 | **0.295 ± 0.049** |
| oracle perfect (seed 42) | 1 | 0.327 |
| ablation_validation (LLM judge) | 1 | 0.092 |
| mitigated (LLM judge, default) | 4 | **0.060 ± 0.035** |
| mitigated_tuned (LLM judge, quote-first) | 1 | **0.000** |

**The judge-recall deficit is now a measured number: 0.235** (pooled
perfect-recall calibration 0.295 minus the mitigated arm's 0.060) — the
LLM judge achieves roughly ONE FIFTH of the catch rate that its own audit
budget supports. Two readings drop out immediately: (1) the "structural
blindness" claim (task #20) is quantified — default prompt 6%, tuned
prompt exactly 0%; (2) the perfect-recall arms only reach ~30%, NOT 100% —
targeted-audit COVERAGE is its own separate bottleneck (the audit only
sees 25 of the cycle's read/written nodes per step, and contamination
that never re-enters a retrieval neighborhood is never audited at all).
So the containment chain has two multiplicative losses: coverage (~0.3
ceiling at this budget) × judge recall (~0.2 of that ceiling for the
default 8B judge). Mitigation design should attack whichever term is
cheaper to move — and #23-B (recall dose-response, running) directly
measures the R₀ consequence of the second term.

Caveat honestly recorded by the agent and kept: the seeded-vs-propagated
split of CAUGHT nodes is not derivable from the archives (det_R_contam is
an aggregate; no per-node quarantine log exists) — noted in the CSV
rather than approximated. If per-node quarantine attribution matters
later, run_contamination.py would need a small logging addition
[PHASE-4].

## 2026-07-24 (parallel work) — Statistical hardening complete (task #29): RQ4 R₀ separation is significant (MWU); variance-amplification claim confirmed as suggestive-only, not overturned

Formal tests over archived fits (Sonnet agent; I independently
re-verified the three load-bearing results below against the raw fit CSVs
before accepting). New: `scripts/stats_tests.py`,
`results/summaries/phase41_stats_tests.csv` (33 rows). Agent's aggregation
cross-checked against known archive values (baseline propagated
17.75±4.03, AUROC 0.8985±0.0066) — exact matches.

**Load-bearing results, re-verified by me:**
- **R₀ mitigated (4.46, n=4) vs oracle_noisy_p10 (0.911, n=4): Welch
  p=0.057, Mann-Whitney p=0.0286.** Per discipline rule 4 both are
  reported; the MWU (perfect group separation — every mitigated seed's R₀
  exceeds every p10 seed's) is the headline, and it is significant. Same
  pattern vs p50 and p75 (MWU p=0.0286 all three). This is NEW support for
  the core RQ4 claim: the recall-bearing (oracle-family) arms are
  significantly more contained than the LLM-judge mitigated arm, not just
  descriptively lower. Bootstrap 95% CI on the mean R₀ difference excludes
  0 (p10: [1.71, 5.54]).
- **AUROC baseline (0.899) vs mitigated (0.859): Welch p=0.0040, MWU
  p=0.0286.** Confirms the 2026-07-12 confidence-laundering finding as the
  one cleanly-significant full-Trio effect. Unchanged.
- **Variance-amplification claim tested, NOT overturned but pinned as
  suggestive:** β variance ratio mitigated/baseline = 6.61× (I recomputed:
  baseline β SD 0.0101, mitigated 0.0259), Levene p=0.5145, F-ratio
  p=0.155 — NOT significant at n=4. This is fully consistent with what ch5
  §5.4.1 already says ("suggestive, not conclusive, at n=4"; the spread-
  metric F(3,3) p≈0.09 quoted there is a different quantity — propagated/
  exposed count variance, ~10× — from the β-fit variance the agent tested,
  6.6×). No retraction: the claim was always hedged as suggestive and the
  formal test agrees it should stay that way. ACTION for the ch5 pass: the
  "Restated finding" summary line ("multiplies outcome variance roughly
  tenfold") states the point estimate without the inline hedge that the
  detailed bullet above it carries — tighten that one line so the summary
  can't be quoted out of its hedge. Everything else in §5.4.1 is fine.
- Within-sweep null contrasts (p75/p50/p10 mutually): all null (Welch
  p=0.72-0.91, MWU p=0.77-1.00) — supports the "R₀ clusters, precision
  doesn't separate them" reading of §5.4.4.
- Baseline-vs-mitigated propagated/exposed: all null (within seed noise),
  consistent with the "no mean spread effect" finding.

Per-run realized quarantine precision across the 13 phase40 noisy runs:
4.6%-37.8% (embedded in the CSV's test_note column). Two construction-
identical fit pairs (p10_s44≡p50_s44, p50_s45≡p75_s45; documented
2026-07-24) flagged in every contrast that touches them, not silently
pooled.

## 2026-07-24 (parallel work) — ch2 literature review DRAFTED (task #30) — CITATIONS NOT YET INDEPENDENTLY VERIFIED

Sonnet agent drafted `docs/chapters/ch2_literature_review.md`: 9 sections
(shared-memory MAS → adversarial poisoning → error cascades →
epidemiological models → provenance/ULDB → KG quality → LLM-as-judge →
synthesis+positioning table), 21 references the agent reports as
search-verified. **STATUS: DRAFT, citations pending MY independent
verification** — LLM-generated literature reviews carry a fabricated-
citation risk that is unacceptable in a thesis, so no ch2 claim or
reference is canonical until each of the 21 entries is confirmed against a
real source by me (or Ashwin). The agent already excluded one unverifiable
item (an Apart Research sprint writeup) rather than cite it shakily, and
flagged several preprints (Chu 2026, Lin et al. 2026) as non-peer-reviewed
— good signs, but verification is still mine to do.

Genuinely thin literature areas the agent surfaced (useful — these are
where the thesis's novelty is strongest): (1) no prior work fits an
epidemic model to PERSISTENT multi-agent memory contamination (closest
2026 papers study transient single-episode consensus); (2) essentially no
peer-reviewed SIR-quantification of any AI-system failure propagation
outside two 2026 preprints; (3) KG error-detection literature is uniformly
static/post-hoc and none addresses REPLACEMENT contamination — exactly the
§5.4.3 blind spot, now literature-motivated rather than just asserted;
(4) LLM-judge literature reports aggregate agreement, not precision/recall
against a low-base-rate positive class (the decomposition this thesis
needed). These thin spots strengthen the priority claim but each needs a
confirming second search before the thesis states "unstudied" outright.

## 2026-07-24 (parallel work) — RQ3 machinery built + reviewed (task #21): k-hop placement + KG density manipulation, both worktree-isolated, both code-reviewed by me

Two Sonnet agents built the RQ3 implementation in isolated git worktrees
(main tree was running live experiments). Both reviewed by me for
correctness; both mergeable, HELD pending chain-idle + live-Neo4j smoke
test (neither agent touched port 7687, correctly).

**k-hop graded seed placement** (worktree agent-a630e8d4...): new
`src/injection/khop_placement.py` (BFS over the Entity-Triplet bipartite
graph, exact-k via smaller-distance exclusion, honest early-stop on
frontier exhaustion), `Neo4jClient.get_adjacent_triplets` (batched Cypher,
one query/hop), `--seed-khop {0,1,2,3}` in run_contamination.py (default
None = existing path bit-identical), per-index-case `khop` field in the
manifest for auditing, configs khop{1,2,3}.yaml (unmitigated baseline
substrate). 22 unit tests pass against a fake adjacency client; --help and
config-parse verified. Reviewed: BFS logic correct. Live-test TODO:
hub-entity query latency on the real 50K KG, whether hop-2/3 frontiers
stay bounded/non-empty, end-to-end manifest khop population. Converts RQ1's
binary reachability result (active vs random) into a distance GRADIENT.

**KG density manipulation** (worktree agent-ab1e2b14...): new
`src/graph/density.py` (pure functions), `--density`/`--density-seed`/
`--tag` on load_kg.py with a --clear guard + realized-density JSON sidecar,
`docs/phase4_density_protocol.md`. Density defined as MEAN ENTITY DEGREE
(verified against the actual retrieval predicate `t.subject IN [key] OR
t.object IN [key]`, distinct from and crossable with the context_limit
retrieval-cap proxy). Sparsification (<1.0): degree-weighted Efraimidis-
Spirakis subsampling with coverage protection (never zeroes an entity's
last triplet). Densification (>1.0): concentration-by-restriction (never
fabricates triplets — ranks entities by degree, unions neighborhoods),
with best-prefix rollback to avoid the overshoot where late low-degree
entities drag mean degree back down. 20+ assertions pass on synthetic
fixtures; O(n) at 50K scale (~0.35s). Reviewed: both algorithms correct;
the overshoot fix is real and necessary. IMPORTANT WRITE-UP CAVEAT the
agent surfaced: densification-by-restriction changes n_entities AND
n_triplets (it's a subgraph), so density>1 arms are NOT the same KG size as
baseline — a covariate to REPORT (protocol doc flags it), not hide. Both
operations refuse to run without --clear. Carries [PENDING-#21-RUN].

RQ3 now has all four axes buildable: write frequency (entities_per_step,
config-only), validation interval (audits_per_step, config-only), graph
density (real KG manipulation, just built), retrieval density
(context_limit, config-only) — plus the k-hop distance gradient. Runs
launch after chain 1 frees Neo4j and both worktrees are merged +
live-smoke-tested.

## 2026-07-24 (verification) — ch2 citation spot-check: 4 riskiest recent citations VERIFIED real with correct arXiv IDs

Independently verified (WebFetch/WebSearch) the four highest-fabrication-
risk ch2 citations — the recent 2025/2026 arXiv preprints that carry the
novelty-priority argument:
- MINJA [Dong et al., arXiv:2503.03704] — REAL, title/authors/topic exact
  (memory injection attacks on LLM agents via query-only interaction).
- Chu 2026 security survey [arXiv:2604.23338] — REAL (the suspicious-
  looking arXiv number resolves correctly to the exact claimed title).
- Hallucination Cascade [Jamshidi et al., arXiv:2606.07937] — REAL, exact
  title/authors, multi-agent LLM error propagation.
- Epidemiology of Model Collapse (bilayer SIR) [Wang, arXiv:2606.05168] —
  REAL, exact title, the closest prior work to this thesis's framing.
All four arXiv IDs in ch2's reference list match the real ones exactly (a
fabricated ID on a real paper would have been the subtler failure — did
not occur). This strongly indicates the agent did genuine verification, so
the recent-preprint set is trustworthy.

REMAINING for ch2 to be final (not blockers, but must happen before
submission): (1) confirm the ~14 classic/established citations (Kermack-
McKendrick 1927, Hayes-Roth 1985, Daley-Kendall 1964, Widom 2005,
Benjelloun 2008, Green-Karvounarakis-Tannen 2007, Paulheim 2017, Zheng
2023, Shumailov 2023, etc. — all well-known, low fabrication risk, verify
for page/volume accuracy); (2) confirm VENUE attributions on preprints —
ch2 says "MINJA NeurIPS 2025" but the arXiv page does not itself confirm
NeurIPS acceptance, so venue claims need a targeted check (the papers are
real regardless); (3) Ashwin's own scholarly review of framing/positioning.
Task #30 stays in_progress for these; the fabrication-risk concern is
substantially retired.

## 2026-07-24 (CHAIN 1 RESULTS) — TWO major findings: (A) the R₀=0.79 "only sub-critical arm" headline is RETRACTED; (B) a CLEAN recall dose-response — the result the precision sweep could not produce

Chain 1 completed all 6 runs (perfect-oracle seeds 43/44/45 for task #24;
recall sweep sensitivity 0.75/0.50/0.25 at seed 42 for task #27). Archived
phase42_*; SIR fits phase42_sir_fit_*.

### (A) RETRACTION — perfect oracle is NOT robustly sub-critical (task #24)

Perfect oracle across 4 seeds: **R₀ = [0.79 (s42), 1.096 (s43), 1.197
(s44), 0.780 (s45)], mean 0.966 ± 0.213, 2/4 SUPER-CRITICAL.**

**This retracts the §5.4.2 headline "R₀ = 0.79, the only sub-critical
configuration observed" (thesis_log 2026-07-12, task #18).** That was a
single-seed value and it was a favourable draw: replication shows the
perfect oracle straddles the epidemic threshold exactly like every noisy
point, with half its seeds super-critical. Per discipline rule 5 this is
recorded, not overwritten — §5.4.2 must state the retraction and carry the
n=4 envelope.

Note (construction-insensitivity, already documented 2026-07-24):
oracle_s43 (1.0957) and oracle_s44 (1.1974) are numerically identical to
p75_s43 and p75_s44 — perfect oracle has false_alarm=0, p75 has 0.0168, and
at that seed the tiny collateral difference never touched the sampled
entities, so the epidemic curves coincide. Expected, not a bug.

**What survives, and is arguably STRONGER for being honest:** the RQ4
verdict was never "the oracle achieves containment" as an absolute — it is
the *comparison*. Restated: perfect judgement brings R₀ from the LLM judge's
4.46 ± 2.36 (badly super-critical, all 4 seeds; §5.4.1) down to ~1.0
(borderline, straddling the threshold). The judge-quality gap is real and
large; the destination is the critical threshold, not comfortable
containment. This is a more defensible and more interesting claim than "one
perfect run got 0.79".

### (B) THE CLEAN RECALL DOSE-RESPONSE (task #27) — recall is the causal lever

Recall sweep at seed 42 (oracle_sensitivity varied, false_alarm=0 so the
recall axis is clean), R₀ vs sensitivity:

| Sensitivity (recall) | R₀ | γ |
|---|---|---|
| 1.00 (perfect, = oracle s42) | 0.790 | 0.0360 |
| 0.75 | 0.827 | 0.0383 |
| 0.50 | 0.948 | 0.0327 |
| 0.25 | 1.067 | 0.0287 |

**Monotone: R₀ rises as recall falls, crossing the epidemic threshold
between sensitivity 0.50 and 0.25.** This is the dose-response the PRECISION
sweep (§5.4.4) structurally could not produce — and the mechanism is exactly
the one predicted by the construction-insensitivity analysis: the recall
knob determines WHICH contaminated nodes are caught, so it moves
`det_R_contam` and therefore γ DIRECTLY (γ falls 0.038→0.029 as recall
drops), and R₀ = β/γ rises. The precision/false-alarm knob only moved
`det_R_clean` (excluded from the SIR reconstruction), so it could not move
R₀ except through an inconsistent indirect path. **Recall vs. precision is
now settled, not inferred: recall is the causal containment lever; precision
governs collateral cost.** This resolves the open question §5.4.4 had to
leave hanging.

**Caveat (rule 2): the recall dose-response is single-seed (42).** Given how
far seeds 43/44 moved the perfect-oracle point, the monotonicity at seed 42
alone must be replicated before it is a headline. Chain 2 (recall sweep
seeds 43/44/45, 9 runs) launched immediately to build n=4 at each
sensitivity. The MECHANISM (γ tracks recall by construction) is robust
regardless; the exact monotone shape needs the replication.

### Consequence for the RQ4 narrative (both findings together)
The mitigation story is now: (1) LLM-judge validation fails badly (R₀ 4.46,
structural recall deficit measured at 0.235, §5.4.1/#28); (2) even PERFECT
judgement only reaches the epidemic threshold, not comfortable containment
(oracle n=4 mean ~0.97, #24 retraction); (3) within perfect-recall regimes,
R₀ tracks recall monotonically and is insensitive to precision (#27 + §5.4.4);
so (4) the binding lever is recall, and the achievable ceiling of
content-based validation in this architecture is ~R₀ 1, i.e. containment is
marginal even in the best case — which redirects the design conclusion
toward provenance-level defences (§5.7c) rather than better judges.

## 2026-07-24 (CHAIN 2 RESULTS) — Recall dose-response completed to n=4: a STRONG, statistically-supported curve, and seed 42 was an outlier-low draw (task #27 DONE)

Chain 2 (9 runs, sens 0.75/0.50/0.25 × seeds 43/44/45) archived phase42_
oracle_sens*_s*; SIR fits phase42_sir_fit_*. The n=4 dose-response is much
stronger and cleaner than seed 42 alone suggested — seed 42 was the lowest
draw at EVERY sensitivity level:

| Sensitivity (recall) | mean γ | mean R₀ ± SD | super-crit | per-seed R₀ |
|---|---|---|---|---|
| 1.00 (perfect) | 0.0375 | 0.97 ± 0.21 | 2/4 | 0.79/1.10/1.20/0.78 |
| 0.75 | 0.0291 | 1.45 ± 0.53 | 3/4 | 0.83/1.19/1.95/1.83 |
| 0.50 | 0.0223 | 1.87 ± 0.62 | 3/4 | 0.95/2.09/2.15/2.30 |
| 0.25 | 0.0138 | 3.78 ± 1.86 | 4/4 | 1.07/5.13/4.12/4.81 |

**Spearman ρ(sensitivity, R₀) = −0.67, p = 0.005 (n=16) — recall
significantly predicts R₀.** Mean γ falls monotonically with recall
(0.038→0.029→0.022→0.014) — the direct mechanism (recall → det_R_contam →
γ). This is now a HEADLINE result, not a provisional single-seed one; the
[PENDING-CHAIN2] marker is resolved and §5.4.5 rewritten to n=4.

**The loop is closed: the dose-response extrapolates into the LLM-judge
arms.** sens-0.25 (R₀ 3.78) is adjacent to the mitigated arm's
independently-fitted 4.46±2.36, and the LLM judge's measured recall (6%,
#28) sits BELOW 0.25 — so the judge arms are not a separate phenomenon,
they are the bottom of this same recall axis. The §5.4.3 prompt-tuning
failure is explained: it moved precision while recall stayed pinned near
zero. **The whole RQ4 result now collapses onto ONE axis: validator recall
sets R₀; precision, prompt, and cascade architecture are all second-order.**
This is the strongest and most unifying RQ4 statement the project has
produced, and every number traces to phase38/phase41/phase42 archives.

Caveat kept (rule 4): adjacent sensitivity levels don't each separate at
4-vs-4 (p=0.20 each, because seed 42 is consistently lowest); the FULL-axis
Spearman trend is what carries significance. Per-level SD inflates toward
low recall because near-zero γ makes β/γ variance explode — noted in §5.4.5.

Task #27 DONE. Immediate next: regenerate fig_r0_by_arm with the oracle
n=4 + full recall-sweep points (a recall dose-response panel is now
warranted as its own figure); merge worktrees + live-test; launch RQ3.

## 2026-07-24 (RQ3 machinery merged + launched, task #21) — worktrees hand-merged, k-hop live-verified, RQ3 baseline sweeps running

**Worktree merge (careful, not blind-copy).** Both RQ3 worktrees branched
from a base predating this session's working-tree edits (oracle knobs +
validator_prompt on run_contamination.py), so a wholesale copy would have
regressed those. Merge strategy: files only the worktree touched on an
unchanged base were copied wholesale (neo4j_client.py +get_adjacent_triplets;
load_kg.py +--density; new files khop_placement.py, density.py, tests,
khop configs, phase4_density_protocol.md); run_contamination.py — the one
doubly-edited file — had the k-hop additions applied SURGICALLY to the
current main (import khop_frontier, build_khop_pool wrapper, seed_index_cases
k-hop branch + khop manifest field, --seed-khop arg), preserving my oracle
knobs and validator_prompt. Verified: all files syntax-clean; `--help` shows
--seed-khop AND --oracle-sensitivity AND --validator-prompt (nothing
regressed); load_kg --help shows --density/--density-seed; both unit suites
pass (khop 22 assertions, density 20+).

**k-hop live-verified** (the one thing the worktree agent couldn't do):
against the loaded 50K KG, khop_frontier returns exact-k pools (hop-values
{1}/{2}/{3} correct), 1.9s/8.8s/9.4s for k=1/2/3 at pool_size 300 — the
hub-entity blowup concern did NOT materialize. Density load-integration will
be tested when a density arm runs.

**RQ3 chain 3 LAUNCHED (7 runs, baseline substrate, no judge calls):**
k-hop gradient khop1/2/3 (RQ1→RQ3 distance bridge — also end-to-end tests
the merged code), write-frequency wf6/wf24 (entities_per_step 6/24 vs
baseline 12), retrieval-density rd3/rd10 (context_limit 3/10 vs baseline 5).
All unmitigated (γ=0) so β/reach effects are clean; baseline (12/5/active)
is the shared reference already archived. Configs: contamination_{khop*,
wf6,wf24,rd3,rd10}.yaml. Seed 42 first pass; replication decision after the
effect sizes are visible.

**RQ3 axes status:** write-frequency ✓running, retrieval-density ✓running,
k-hop gradient ✓running, graph-density = NEXT (separate chain, load_kg
--density {0.5,2.0} per phase4_density_protocol.md), validation-interval =
DEFERRED (needs either an audit-cadence flag or an oracle-substrate
audits_per_step sweep — token-free but needs a small design decision).

### 2026-07-24 (cont.) — RQ3 chain 3 partial results + structural-density infeasibility

**Background-task reaping diagnosed.** Chain 3 was killed three times mid-run
(all status "killed", never "failed" — no run errored). Cause: background
tasks are reaped after a short idle window; they survive only while the
session stays actively engaged (the first launch ran ~50 min across active
turns; the idle relaunches died in 6–17 min). One death also involved an
orphaned child from a prior "killed" task colliding on Neo4j (both running
load_kg --clear). Fix: verify no stray python before relaunch, and hold the
session active with a Monitor loop for the duration. No data lost — every
completed run had already archived before its chain died.

**Completed + archived (baseline substrate, γ=0, seed 42):** khop1/2/3, wf6.
SIR fits (scratch, to be re-fit into results/summaries when chain completes):
  - **k-hop: β = 0.0000 at k=1, 2, AND 3.** Zero contaminated facts served
    across all steps of all three runs (mechanism confirmed directly). A seed
    even ONE hop outside the active retrieval subgraph never propagates —
    same outcome as the #10 random-placement control. RQ1 reachability
    sharpens from "binary" to a **hard threshold at the retrieval horizon**;
    the "graded" k-hop design is empirically a step function, not a gradient.
  - **write-frequency: wf6 (entities_per_step 6, half baseline) → β 0.0193,
    empirical reproduction 0.175/seed** vs baseline seed-42 β 0.055,
    emp-repro 0.538. Halving write frequency ~thirds the reproduction — a
    clean β-channel dose-response (wf24 pending to complete the monotone
    triple).

**Structural-density axis is infeasible on T-REx as loaded (offline finding,
no Neo4j spent).** Dry-run of apply_density against the real 50,000-triplet
file: baseline mean entity degree is **1.66 (median 1.0, p90 2.0)** — a
near-tree/forest, not a hub-and-spoke graph. The achievable structural range
is hard-capped by this structure: requested factors 0.1–0.7 all realize
**0.86** (coverage protection blocks drops — almost every triplet is some
entity's sole triplet), and 2.0–5.0 all realize **1.26** (best-prefix
concentration peaks at mean degree 2.10). So the *structural* density knob
can only deliver a ~1.5× contrast, not the intended 4×.
  - **Decision (per "comprehensive, gapless, don't compromise"):** the
    primary RQ3 density evidence is the **retrieval-density axis**
    (context_limit, rd3/rd10 — varies freely, already running). The two
    structural endpoints (realized 0.86/1.26) still get run as a
    documented-limitation confirmatory arm so both operationalizations are
    reported; realized factors cited from kg_density_*.json sidecars, not the
    requested 0.5/2.0. This sparsity ceiling is itself a reportable property
    of using T-REx for a density study — surfaced, not hidden.
  - phase4_density_protocol.md "What still needs live-Neo4j validation" item 2
    (realized density on the ACTUAL T-REx distribution) is now resolved
    offline; the [PENDING-#21-RUN] marker stays until the two arms run.

### 2026-07-24 (cont.) — RQ3 COMPLETE: all 4 β/reach axes archived + written (§5.9)

All seven fixed-KG arms (phase43_rq3_sir_fit.csv) + both structural-density
arms (phase44_density_sir_fit.csv) archived and fitted; ch5 §5.9 written
(5.9.1–5.9.5). Headline RQ3 findings, all seed-42 single, hedged against the
4-seed baseline envelope (repro 0.452±0.101, β 0.0437±0.0101):

  - **k-hop = hard threshold, not gradient.** β=0, propagated=0, exposed=0 at
    k=1/2/3; 0 contaminated facts served across all steps. A seed one hop out
    is as inert as random placement (§5.3). AUROC at chance (0.485–0.491) at
    all k reproduces "detectability is a cascade property" three more times.
  - **Write frequency: velocity saturates, reach does not.** wf6 repro 0.175
    (2.7 SD below), wf24 repro 0.675 (2.2 SD above) but β flat vs baseline
    (0.056 vs 0.055) — above baseline, extra writes add reach (exposed 143 =
    2.3× baseline) at an unchanged per-contact rate.
  - **Retrieval density (context_limit): clean monotone dose-response**, both
    estimators. repro 0.25→0.54→0.70, β 0.026→0.055→0.063 across ctx 3→5→10.
    Primary density operationalization.
  - **Structural density (mean degree): large INVERSE effect.** Denser graph
    → slower spread: repro 0.842→0.538→0.135 (β 0.070→0.055→0.013) as mean
    degree rises 1.43→1.66→2.10. ~6× swing over a 1.5× density change, both
    endpoints >3 SD out. Mechanism: the two density knobs act on the SAME
    retrieval bottleneck from opposite sides — context_limit widens the
    window (more contaminated facts admitted, higher β); structural degree
    raises clean-fact competition for a FIXED window (contaminated share
    diluted, lower β). Confound checked: seeded 38/40/37, RS-only difference,
    does not drive the ED/QL reproduction. density_0.5 realized 0.86× live,
    matching the offline dry-run exactly (load integration verified E2E).
  - **[PENDING-#21-RUN] RESOLVED.** All density arms run; validation-interval
    axis remains DEFERRED (handled epidemiologically via §5.4 γ-arms).

**Infra note:** background tasks are reaped when the session idles between
re-invocations; a single long run with no intermediate events (density_2.0,
1st attempt) died at ~step 5. Fix that worked: Monitor with a ~3-min step
heartbeat re-invokes frequently enough to hold the session warm through a
full ~15-min run. Every completed run archived before any kill — no data
lost across the whole reap saga.

**Chapter:** ch5 title updated Phase 2–3 → Phase 2–4 (now carries RQ3).
RQ3 arms are single-seed; multi-seed replication of the retrieval-/write-/
density extremes is the thesis→paper hardening step (task #33).

### 2026-07-24 (cont.) — external-validity re-evaluation + RQ3 replication launch

**Strategic re-evaluation (prompted by "will bigger models change this?").**
Split the thesis's findings by their dependence on model scale:
  - PROPAGATION (RQ1 reachability, RQ2 error-type ranking, RQ3 velocity/
    density) is ARCHITECTURAL — retrieval-augmented agents follow retrieved
    context incl. wrong context regardless of scale (knowledge-conflict
    literature). Survives frontier models. Strengthened by the fact that the
    KG is T-REx LONG-TAIL facts, exactly where a bigger model has no
    parametric prior to resist a contaminated fact with.
  - DETECTION (RQ4 validator recall/precision) is JUDGE-CAPABILITY-
    CONTINGENT: a frontier judge adds a world-knowledge channel the evidence-
    gated 8B judge lacks. The structural-blindness result holds; the recall
    ceiling could lift with a stronger judge. This is now an explicit,
    bounded limitation rather than an unstated assumption.
  - Rejected my own first idea (one arm with a frontier synthesis model) as
    CONFOUNDED — different model = different prose/volume/coverage, β shifts
    through many channels unrelated to "does it trust a contaminated fact."
    Correct instrument = REPLAY: hold the served (context, prompt) constant,
    vary only the model. Precedent: the #25 second-rater offline replay;
    never-switch-the-judge invariant applies to in-run judging, not offline
    replay.

**Decision:** RQ3 replication runs GROQ-FREE (the dose-response is SIR/reach/
AUROC, none of which touch Groq); the freed budget goes to offline replay
probes (propagation + detection) across model sizes to measure the scale
question empirically instead of hedging it in prose. Downgrades the earlier
"full-Groq 10–14 day crawl" plan as over-investment on a secondary RQ.

**Code (run_contamination.py):** added `--log-prompts` (archives verbatim
synthesis context+prompt+paragraph+propagation as JSONL → the replay corpus,
zero LLM cost) and `--no-eval` (skips task-eval + probe, the only Groq
consumers; SIR/reach/AUROC unaffected, probe/task columns omitted). Both
config-settable; oracle/khop/validator_prompt flags verified intact.

**Launched:** RQ3 seed replication — 9 arms (wf6/wf24, rd3/rd10, khop1/2/3,
density_0.5/2.0) × seeds 43/44/45 = 27 runs, each no_eval + log_prompts,
n=4 to match the baseline envelope. Density arms hold density-seed=42 (same
KG structure) and vary only the contamination seed. khop1_s43 leads as the
end-to-end smoke test of the new path. [PENDING-#33-RQ3-RUN] until archived
+ fitted; replay probes follow from the logged corpus.

### 2026-07-24 (cont.) — RQ3 replication COMPLETE (27 runs): 2 retractions, 2 confirmations

All 27 runs archived + fitted to n=4 (`phase45_rq3_replication_n4.csv`). The
replication was decisive both ways; §5.9 rewritten to n=4. [PENDING-#33-RQ3-RUN]
RESOLVED. (Survived one full session-process exit mid-chain; resumable script
skipped the archived runs and resumed — no data lost.)

**CONFIRMED (robust at n=4):**
  - Retrieval-density: reproduction 0.277→0.452→0.743, β 0.025→0.044→0.059
    (ctx 3→5→10). rd3 vs rd10 Welch p=0.005, MWU p=0.029. The cleanest axis.
  - Write-frequency: reproduction 0.176→0.452→0.915, β 0.016→0.044→0.069
    (÷2→×2). Monotone, clean separation both ends.
  - k-hop hard threshold: β=0, propagated=0, contam-served=0 at k=1/2/3 across
    ALL 4 seeds. The k=1 boundary (could it leak as subgraph grows?) does NOT
    leak on any seed. §5.9.1 single-seed caveat lifted.

**RETRACTED (single-seed → n=4, rule 5, recorded in §5.9.2 / §5.9.4):**
  - Write-freq "β saturates above baseline" — seed-42's flat wf24 β (0.056) was
    the low tail; n=4 β is monotone (0.069 mean). Write freq raises BOTH rate
    and reach.
  - Structural-density "large inverse effect / 6× swing / matched-pair
    mechanism" — rested ENTIRELY on seed 42 being the extreme of both arms'
    distributions (sparse 0.842=max, dense 0.135=min). n=4: sparse 0.517±0.21,
    dense 0.375±0.15; all pairwise tests null (sparse-vs-dense Welch p=0.384,
    MWU p=0.686; gap 1.6 baseline SD, within noise). The inverse effect, its
    magnitude, and the mechanism are withdrawn; replicated result is a null
    over the achievable [0.86x,1.26x] range.

**Value:** replication caught two over-claimed single-seed results BEFORE they
became thesis headlines — exactly the failure mode the discipline rules target.
Surviving RQ3 claims now bulletproof at n=4. Corpus for the propagation replay
probe (`scripts/replay_propagation.py`, built + logic-validated; Nemo baseline
0.75 on wf6_s43) is complete across all in-subgraph arms; scale ladder
(12B→70B→123B) is the next step for the model-scale question.

### 2026-07-24 (cont.) — SCALE LADDER: propagation reproduction RISES with capability (ch5 §5.10)

The model-scale question ("would a frontier model resist a contaminated
retrieved fact?") answered empirically via the propagation replay probe: 337
contaminated-context records (n_contam>0, from the RQ3 --log-prompts corpus)
replayed through a Claude capability ladder, context held constant, thinking
disabled, same string-containment reproduction measure applied to every model
incl. Nemo's own logged paragraph. Ladder built: added _AnthropicClient to
llm_client.py (no temperature — Sonnet/Opus 400 on it; thinking disabled for
apples-to-apples single-pass gen), --provider anthropic in replay_propagation,
anthropic SDK installed + in requirements. 0/1011 calls failed.

**RESULT (phase46_scale_ladder.csv; monotone increasing):**
  - Mistral Nemo 12B (in-run): 0.858
  - Claude Haiku 4.5:          0.932
  - Claude Sonnet 5:           0.964
  - Claude Opus 4.8:           0.967
Overlap-with-Nemo = 0.858 for Sonnet AND Opus = Nemo's own rate exactly →
Nemo's reproduced set is a strict SUBSET of the frontier models'. Opus
reproduces everything Nemo does PLUS ~11% Nemo missed. Frontier models are
STRICTLY MORE contaminating on this corpus, not less.

**Interpretation:** bigger models do NOT fix non-adversarial cascade; they
intensify propagation, because faithful context-following (what capability
buys) faithfully renders contaminated context too — and on T-REx long-tail
entities there is no parametric prior to override it with. Sharpens the core
claim on the exact axis a reviewer presses. SCOPE: this is PROPAGATION only;
DETECTION (RQ4 recall) remains judge-capability-contingent and is explicitly
NOT claimed scale-robust — the propagation/detection split is now itself
evidenced. Caveats: string-containment (blind to semantic paraphrase),
single model family (cross-family GPT/Llama rung would rule out a
Claude-specific idiosyncrasy). Neither changes the direction.

Cost: ~$3 total on the Anthropic key (Haiku+Sonnet+Opus). Key note: the first
two keys Ashwin tried 401'd (revoked/invalid); the third authenticated.

### 2026-07-24 (cont.) — DETECTION LADDER: capability does NOT rescue detection (ch5 §5.10.1)

Second replay probe (detection half of the scale question). 154 unique
contaminated + 154 matched clean triplets, same validator prompt/format
(OrchestrationAgent imported verbatim), co-served facts as evidence, judge
model varied. Caught = verdict UNSUPPORTED (conf<0.4). Both recall (on contam)
AND clean false-flag rate reported — recall alone is useless (flag-everything
scores 1.0). phase47_detection_ladder.csv + replay_detection_judge_*.csv.

**RESULT (discrimination = recall − false-flag; NOT monotone, essentially flat):**
  - Llama-3.1-8B (in-run):  recall 0.617, FPR 0.383, disc +0.234
  - Haiku 4.5:              recall 0.617, FPR 0.416, disc +0.201
  - Sonnet 5:               recall 0.636, FPR 0.448, disc +0.188
  - Opus 4.8:               recall 0.526, FPR 0.240, disc +0.286 (best, via conservatism)

All four in a narrow +0.19–0.29 band; frontier Opus beats 8B by only ~0.05, and
by flagging LESS (not knowing more). Even Opus catches ~53% of contam while
false-flagging 24% of clean. Opus by-type: ED 0.75, QL 0.44, propagated 0.25–0.36
— misses the subtle + second-generation errors (structural blindness, §5.4.3).

**Correction recorded:** my in-turn read leaned "flat-to-declining" after 3
points; Opus reversed it to flat-with-best-at-top. Written up honestly as FLAT
(no meaningful capability gain), not declining.

**UNIFIED TWO-AXIS CONCLUSION (§5.10.2):** scaling makes propagation clearly
WORSE (0.858→0.967) and detection NO BETTER (+0.05). Same T-REx long-tail
mechanism both ways: capability buys faithful context-following (spreads
contamination) but not knowledge of obscure facts (can't catch it). The
propagation/detection split is now evidenced on both sides from one corpus.
NOTE: offline detection recall (~0.6) is NOT the in-run 6% — different task
(isolated judgment vs budget-throttled live-retrieval audit); do not equate.

Figures: fig_scale_ladder (propagation), fig_detection_ladder (detection),
fig_rq3_doseresponse (RQ3 n=4) — all rendered, archive-faithful, referenced in
ch5. Detection ladder cost ~$1.5 Anthropic (llama rung Groq-free).

## 2026-07-25 — RQ3 validation-cadence sweep (closes the exposé "validation intervals" commitment)

**Done:** implemented `--validate-every N` in `run_contamination.py` (pure-delay,
full-coverage: skipped steps accumulate their audit candidates onto a backlog,
the flush step audits the entire backlog uncapped since oracle audits are
LLM-free; N=1 byte-identical to prior per-step behaviour). 9 configs
(`contamination_oracle_int{2,5,10}_s{42,43,44}.yaml`, all `no_eval` → Groq-free),
resumable chain runner `scripts/run_interval_sweep.py`, offline unit test
`scripts/test_validate_interval.py` (6 groups, all pass; existing khop/density/
agents suites regress clean). Sweep ran end-to-end on Neo4j in ~1h02 (9 arms,
~7 min each). SIR fits: `phase48_sir_fit_interval.csv`; aggregation:
`phase48_interval_summary.csv`. Written up as ch5 §5.4.6 + R₀-table rows in §5.5;
§5.9.5 deferral note resolved; ch6 deviations row 2 marker `[PENDING-INTERVAL-
SWEEP]` resolved.

**Finding — a threshold, not a gradient.** Perfect oracle, total coverage held
constant, only cadence varied. R₀ by interval (mean±SD):
  - int 1 (every step, n=4):  0.96 ± 0.21   (2/4 super-crit)  [= §5.4.2 oracle]
  - int 2 (n=3):              0.50 ± 0.05   (0/3)
  - int 5 (n=3):              0.77 ± 0.18   (0/3)
  - int 10 (end only, n=3):   2.25 ± 0.21   (3/3 super-crit)
Any in-run cadence holds R₀ at/below the epidemic threshold; deferring ALL
validation to a single end-of-run sweep collapses containment. Interval-10 vs
every-step: Welch t p=0.0008, Mann–Whitney U p=0.057 (the n=3-vs-4 FLOOR).

**Mechanism (model-free):** at interval 10 the audit fires only at step 10, so
`det_R_contam` is exactly 0 for steps 1–9 of every seed (verified in the
trajectories) → γ=0 through the whole propagating phase → the system runs at the
UNMITIGATED R₀ (~4.46, §5.4.1). The late sweep catches a big batch (33 nodes at
s43, > every-step's cumulative 14.5) but after the epidemic has run. Recovery
after propagation is bookkeeping, not mitigation.

**Honesty constraints (recorded, not smoothed):**
1. In-run cadence is NOT monotone — int2/int5 R₀ sit BELOW int1 (0.50, 0.77 vs
   0.96). Trend test n.s.: Spearman ρ(interval,R₀)=0.36 p=0.22. Do NOT claim
   "more frequent is safer." The dip is within seed noise (int1 SD alone 0.21)
   and partly a fitting artefact: a perfect oracle sweeping an accumulated
   backlog yields a steeper R(t), which constant-γ SIR reads as HIGHER γ (0.071
   at int2 vs 0.038 at int1). Load-bearing claim = interval-10 collapse only.
2. n=3 per new interval → every cross-interval comparison suggestive, not
   significant (rule 4). Interval-10 R₀ point estimate has high fit RMSE (6.1–9.1
   vs 1.1–2.9) because one late recovery pulse is what constant-γ fits worst —
   read "2.25" as "decisively super-critical," not a precise value.

**Connection:** complements the recall dose-response (§5.4.5). There coverage
(recall) was the lever, timing fixed; here coverage pinned at 100%, only timing
varies. Same γ-starvation mechanism both ways: a validator contains contamination
only by removing contaminated nodes WHILE the epidemic is still propagating —
whether it misses them (low recall) or arrives too late (full deferral), R₀
climbs above 1. RQ3 "validation intervals" is thereby answered as two distinct
levers (how good the validator is; when it runs) — richer than the single
ablation the exposé envisioned.
