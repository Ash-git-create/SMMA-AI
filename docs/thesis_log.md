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
