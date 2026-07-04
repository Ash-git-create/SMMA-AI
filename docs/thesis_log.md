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
