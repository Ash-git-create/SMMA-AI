# Chapter 4 — Implementation

> **Draft status (2026-07-23):** describes the system as implemented and run
> through Phase 3.9 (tuned-validator arm). Chapter 3 owns the design rationale
> and experimental arms; Chapter 5 owns the results. This chapter documents the
> engineering realization: what the code does, where each mechanism lives, and
> which pragmatic choices shaped it. Figures are marked `[FIG]`. Components
> that exist only as Phase 4 plans are marked `[PHASE-4]`.

## 4.1 Architecture overview

The system is organised in four layers:

1. **Shared memory** — a Neo4j property graph holding all triplets and their
   provenance (`src/graph/neo4j_client.py`, `src/graph/provenance_schema.py`).
2. **Agents** — the extraction, judging, and validation logic, each a thin
   Python class around an LLM call with strict JSON contracts
   (`src/agents/`).
3. **Experimental control** — runner scripts that compose the agents into the
   three-stage clean-room protocol and emit trajectory/manifest artifacts
   (`scripts/load_kg.py`, `scripts/run_extraction.py`,
   `scripts/run_contamination.py`), configured by YAML files in
   `experiments/configs/`.
4. **Measurement and analysis** — pure-function metrics
   (`src/evaluation/metrics.py`), the SIR model and R₀ machinery
   (`src/sir/`), and the post-hoc fitting script (`scripts/fit_sir.py`).

`[FIG] Component diagram: Neo4j KG at the centre; ExtractionAgent (write
path), synthesis step, evaluation LLM and ValidationAgent around it; the
retrieval (beta) and audit/quarantine (gamma) channels annotated; runner
scripts as the outer control loop.`

**Model stack as run.** The original design (Chapter 3.1) targeted local
CPU inference via Ollama. That plan did not survive contact with the
hardware constraint (Section 4.9): all experimental runs use hosted APIs.
The pivot changed the serving infrastructure only — model families, sizes,
prompts, and the two-tier split were preserved.

| Role | Model | Provider | Selected via |
|---|---|---|---|
| Extraction & synthesis | `open-mistral-nemo` (Mistral Nemo 12B) | Mistral API | `ModelRole.EXTRACTION` |
| Judging, validation, task evaluation | `llama-3.1-8b-instant` (Llama 3.1 8B) | Groq API | `ModelRole.ORCHESTRATION` |

The router in `src/agents/llm_client.py` maps each `ModelRole` to a provider
and model from environment variables; an Ollama backend remains implemented
as a selectable third provider but is unused in any experimental run. All
providers share one call pipeline (`_BaseClient.chat`): deterministic
settings (temperature 0.0, `max_tokens` 1024 by default), up to 3 retries
with exponential backoff, a rate-limit-aware wait that parses the server's
own "try again in …" suggestion (capped at 300 s), an optional JSONL audit
log of every request/response, and an optional on-disk response cache
(Section 4.8). API or parse failures surface to callers as explicit
no-ops — a design invariant discussed in Section 4.3.

## 4.2 Knowledge graph and provenance schema

### 4.2.1 Graph model

The KG schema (`src/graph/neo4j_client.py`) reifies each
subject–predicate–object triplet as its own node rather than as an edge, so
that a fact can carry properties and participate in lineage:

```
(:Entity {id, name})
    -[:SUBJECT_OF]->
(:Triplet {id, subject, predicate, object, source_text, source,
           state, confidence, lineage, source_id, agent_id, timestamp,
           error_type})
    -[:HAS_OBJECT]->
(:Entity {id, name})

(:Triplet)-[:DERIVED_FROM]->(:Triplet)   # lineage edges, written by agents
```

Uniqueness constraints on `Entity.id` and `Triplet.id` plus indexes on
`state`, `confidence`, and `Entity.name` are created idempotently
(`create_indexes`). Bulk loading batches 500 records per transaction. The
T-REx snapshot is loaded by `scripts/load_kg.py` with `TripletMetadata.baseline`
provenance: confidence 1.0, state `S`, `agent_id = "baseline_loader"`, and a
lineage formula equal to the triplet's own `source_id` (a pristine fact is
its own source). The loader refuses a second load without `--clear` — the
deterministic `trex_*` ids would violate the uniqueness constraint mid-batch
and leave a partially doubled entity graph.

### 4.2.2 X-tuples and lineage

Following Trio/ULDB, each triplet is an *x-tuple*: value, confidence, and a
lineage formula (`src/graph/provenance_schema.py`). Lineage is recorded in
two redundant forms:

- **The formula string** — a DNF boolean expression over ancestor ids, built
  by `LineageFormula`. In practice every derived triplet gets a
  *conjunction* of its retrieval-context parents ("derived from all of
  these"); the disjunctive form (and its arithmetization, `noisy_or` in
  `src/mitigation/trio_framework.py`) is implemented but exercised by no
  pipeline path — the write path never produces alternative derivations.
- **Materialized `DERIVED_FROM` edges** — one edge per parent, written by the
  ExtractionAgent at store time. The formula string alone is not walkable by
  a Cypher traversal; the edges are what cascade deprecation
  (Section 4.5) actually follows, via
  `Neo4jClient.get_downstream` (`<-[:DERIVED_FROM*1..]-`, i.e. transitive).

### 4.2.3 Ground truth vs detection — the central schema invariant

Two properties encode two *independent* channels, and the code enforces
their separation everywhere:

- `state` (`S`/`I`/`R`) is the *operational* SIR status, written only by
  agents: the judge marks `I` when confidence falls below its threshold, the
  ValidationAgent marks `R` on quarantine.
- `error_type` is *ground truth*, written only by the experimenter's
  instruments: the ErrorInjector sets it at seeding, and the contamination
  runner sets `propagated_<root_type>` when a written triplet demonstrably
  reproduces a corrupted payload (Section 4.6.2).

Agents never read or write `error_type`; it is not exposed through any
retrieval query. Detection metrics (AUROC, quarantine precision, collateral
damage) are cross-tabulations of `state` against `error_type`
(`detection_confusion` in `src/graph/neo4j_client.py`). The injector,
symmetrically, never touches `state` or `confidence` — an undetected
injected error is structurally indistinguishable from a trusted fact, which
is the phenomenon under study.

### 4.2.4 Deterministic retrieval

Two details in the client exist purely for reproducibility. First, every
retrieval query orders by `confidence DESC, t.id`: Neo4j returns
confidence ties in arbitrary order otherwise, and that order varies across
database reloads — retrieval, and therefore every downstream LLM prompt,
must be byte-stable for run-to-run differences to be attributable to
treatment. Second, `search_triplets(randomize=True)` (`ORDER BY rand()`) is
mandatory for audit sampling and injection-pool draws; without it Neo4j
returns the same rows every call, which would silently bias both the
validator's coverage and the SIR estimates.

## 4.3 The agent ensemble

### 4.3.1 ExtractionAgent (`src/agents/extraction_agent.py`)

The extraction agent turns a text passage into SPO triplets and writes them
with full provenance. Its `_SYSTEM_PROMPT` demands a bare JSON array of
`{subject, predicate, object}` objects and — critically for the
contamination design — instructs the model to extract *what the text
asserts*, explicitly including false, unverified, or fictional claims
("you are recording the text's claims, not judging their truth"). This
fidelity-not-truth rule is what allows FEVER's REFUTED claims to enter the
KG as facts, the channel quantified in Section 5.7c.

Implementation details that matter to the experiments:

- **Context as the transmission channel.** `extract_and_store` accepts
  `context_facts` — KG triplets retrieved for the passage's entity. They are
  rendered into the prompt ("Facts already in the knowledge graph…"), their
  ids become the conjunctive lineage formula, and one `DERIVED_FROM` edge is
  written per parent. This is the susceptibility component of β: a
  contaminated fact in context can shape what gets written back.
- **Confidence at write time.** Fresh extractions carry
  `confidence_default = 0.85`. With Trio confidence propagation enabled
  (`propagate_confidence=True`, the `trio_confidence` config switch), the
  written confidence is instead derived from the parents
  (Section 4.5).
- **Deterministic ids.** Triplet ids are UUID5 hashes of a per-agent
  monotonic write counter, not random UUID4s. Because retrieval tie-breaks
  on `t.id`, random ids made confidence-tied facts order differently across
  otherwise identical runs; counter-derived ids make an identical pipeline
  replay mint identical ids, keeping runs byte-comparable end to end.
- **Failure semantics.** The JSON parser tolerates markdown fences but
  nothing else; an unparseable response or API failure yields an empty
  result and no write. Partial or guessed writes would inject
  experimenter-caused contamination.

### 4.3.2 OrchestrationAgent — the judge (`src/agents/orchestration_agent.py`)

Despite its name (a Phase 1 designation retained for continuity), this class
implements exactly one function as run: it is the *fact-checking judge*. It
receives a candidate triplet plus evidence triplets retrieved from the KG
(via `get_related_triplets` — facts sharing an entity with the candidate,
highest confidence first, at most 20, above the retrieval floor) and asks
Llama 3.1 8B for a verdict. Pipeline-level orchestration — the step loop,
entity sampling, synthesis — lives in `scripts/run_contamination.py`
(Section 4.6), not in this class.

**The JSON verdict contract.** The default `_SYSTEM_PROMPT` requires:

```
{"verdict": "SUPPORTED" | "UNSUPPORTED" | "UNCERTAIN",
 "confidence": <float 0.0–1.0>,
 "reason": "<one sentence>"}
```

with prescribed confidence bands: SUPPORTED 0.7–1.0, UNCERTAIN 0.35–0.7,
UNSUPPORTED 0.0–0.35. The returned confidence is written back to the
triplet; if it falls below `infection_threshold = 0.4` a Susceptible triplet
is marked `I`. The band boundaries interlock with the quarantine threshold
(0.4, Section 4.3.3): any UNSUPPORTED verdict lands below it, UNCERTAIN
verdicts straddle it.

**The tuned prompt.** `_TUNED_SYSTEM_PROMPT` (selected with
`validator_prompt="tuned"`) is the in-run adaptation of the offline
prompt-tuning winner (Section 3.6, results in Section 5.4.3). It keeps the
model, the parsing, and every threshold identical and changes only the
judgement rules, adding one field to the contract (`evidence_quote`) and two
structural constraints: the judge must copy the single most relevant
evidence line *verbatim before* giving a verdict, and UNSUPPORTED requires a
non-empty quoted line that the candidate *contradicts* — "absence of
evidence is NOT contradiction", which under the 0.4 threshold is the rule
that stops sparse-evidence pristine nodes from being quarantined. World
knowledge is explicitly forbidden.

**Failure semantics.** An API failure or unparseable verdict returns `None`
from `_call_llm`, and `_run_validation` then leaves the KG untouched and
returns an `error`-flagged result. Writing any fallback confidence here
would let infrastructure failures masquerade as contamination in the
measurements; the ValidationAgent skips such results entirely.

### 4.3.3 ValidationAgent (`src/agents/validation_agent.py`)

The ValidationAgent is the γ channel. One audit pass (`run_audit_pass`)
selects candidate triplets, obtains a verdict per candidate, and quarantines
those whose revised confidence falls below
`quarantine_threshold = 0.4` — setting `state = R`, and triggering cascade
deprecation of every lineage descendant (Section 4.5).

**Three judge modes**, all sharing identical audit targeting and quarantine
mechanics:

1. *Default* — verdicts from the OrchestrationAgent judge with the original
   prompt (all Phase 2–3 LLM-validated arms).
2. *Tuned* — the same judge with `_TUNED_SYSTEM_PROMPT`
   (`mitigated_tuned` arm).
3. *Oracle* (`oracle=True`) — verdicts read directly from the ground-truth
   `error_type` property: any contaminated node (seeded or propagated) is
   quarantined at confidence 0, at zero LLM calls per audit. Clean nodes'
   confidences are never re-scored in this mode, so the
   confidence-laundering channel identified in Section 5.4.1 is absent by
   construction — the property that makes the arm an architecture-vs-judge
   attribution instrument (Section 3.6).

**Two sampling modes.** With `candidates` supplied (the `audit_targeted`
config flag), the pass audits the triplet ids the pipeline actually read and
wrote in the current cycle, capped at `sample_size` and skipping
already-quarantined nodes — *targeted* validation. Without it, the pass
draws a uniform random sample split between `S` and `I` states
(`randomize=True`). The targeted mode exists because uniform sampling makes
γ vanish at KG scale: an audit of 50 nodes over a ~51,000-node graph touches
any given corrupted node with probability ≈0.001 per pass. Where the
validator looks is as much a design variable as how often it runs. All
mitigated arms use targeted audits of 25 nodes once per step
(`experiments/configs/contamination_mitigated.yaml`; the 25-node cap
reflects that each audited node costs one LLM call under the default
judge).

### 4.3.4 The synthesis step

The transmission cycle needs a second write-side agent: a synthesiser that
turns retrieved KG facts into prose which the ExtractionAgent then
re-ingests. It is implemented as a prompt (`_SYNTH_SYSTEM` in
`scripts/run_contamination.py`) against the extraction-role model (Mistral
Nemo): write a 2–4 sentence paragraph from the given facts, "do not correct,
question, or omit facts — you are a summarizer, not a fact checker." The
instruction is deliberate: the synthesiser is designed as a *faithful
carrier*, so that transmission measures the memory-mediated channel rather
than one model's inclination to editorialise.

## 4.4 Controlled error injection

`src/injection/error_injector.py` implements the three error types of the
taxonomy (Section 3.3) as corruptions applied *in place* to Susceptible
triplets. The transformations are pure functions, unit-testable without a
database:

- **Qualifier loss** (`strip_qualifier`): removes the first matching
  qualifier from the object string — parentheticals ("(1844–1846)"),
  trailing comma-qualifiers (", California"), clauses opened by
  from/between/during/until/since, and year ranges; full dates are truncated
  to the year ("24 October 1968" → "1968", ISO dates likewise) — temporal
  precision loss.
- **Relation strengthening** (`strengthen_predicate`): upgrades a weak
  associative predicate to a strong causal/definitive one via a fixed
  substring-matched mapping of 28 pairs ("associated with" → "caused",
  "nominated for" → "winner of", "cast member" → "lead actor", …), replacing
  case-insensitively inside the original predicate text.
- **Entity disambiguation** (`_corrupt`): swaps the object for another
  entity that occurs with the *same predicate* elsewhere in the candidate
  pool — a plausible confusion rather than random noise — falling back to
  any other pooled object only if no same-predicate alternative exists.

Not every triplet admits every corruption, so the injector oversamples
(pool of `count × 10` candidates when drawing from the full KG) and
filters for admissibility; qualifier-bearing triplets are additionally
under-represented in a uniform sample, so the QL pool is supplemented with
date-of-birth/date-of-death triplets. A realised shortfall is logged loudly,
never silent — this is the mechanism behind the RS realised-seed caveat of
Section 3.3. An explicit `pool` argument lets the contamination runner seed
inside the active retrieval subgraph (Section 4.6.1).

Every applied injection updates the triplet through a strict field allowlist
(`Neo4jClient.update_triplet_fields`), writing the corrupted value alongside
an `original_<field>` audit copy, `error_type`, and `injected_at`.
`state` and `confidence` are deliberately untouched (Section 4.2.3). The
injector's RNG is seeded from the run seed, and every run's injection
records (triplet id, error type, field, before, after) go into the run
manifest, so any run's index cases are fully reconstructable.

## 4.5 Trio mitigation implementation

`src/mitigation/trio_framework.py` implements the three mechanisms of
Section 3.5; the module is deliberately small because each mechanism is a
few lines operating on the provenance schema.

1. **Confidence propagation at write time** (`propagate_confidence`): a
   derived triplet's confidence is the arithmetized conjunction of its
   lineage — the product of parent confidences times the extractor's base
   confidence (0.85), clamped to [0, 1]. Parent independence is assumed (the
   standard ULDB simplification, documented as a limitation). The intended
   consequence: confidence decays with derivation depth, so agent-written
   generations sink toward the retrieval floor while pristine sources stay
   at 1.0 — without this, every derived fact enters at the flat default and
   the floor separates nothing. Applied inside
   `ExtractionAgent.extract_and_store` when `trio_confidence` is on.
2. **Retrieval confidence floor**: enforced not by a dedicated component but
   by the `min_confidence` parameter threaded through every retrieval site —
   the transmission cycle, the judge's evidence retrieval, the task
   evaluation, and the probe evaluation all pass the configured
   `retrieval_threshold` (0.5 in all mitigated arms; 0.0 = no floor in
   baseline). Confidence is the *only* retrieval currency: quarantined nodes
   are excluded because deprecation zeroes their confidence
   (`DEPRECATED_CONFIDENCE = 0.0`), not via a state check — one number
   decides visibility, keeping the mechanism pure Trio.
3. **Cascade deprecation** (`cascade_deprecate`): on quarantine, walk the
   `DERIVED_FROM` edges transitively downstream and set every dependent to
   `state = R`, confidence 0.0. Idempotent (already-Recovered nodes are
   skipped). The over-quarantining this implies — a derived node may have
   had other, clean parents — is measured (the `det_R_clean` collateral
   column, Section 4.6.3), not assumed away.

The module writes `state` and `confidence` only, never `error_type`,
preserving the ground-truth separation of Section 4.2.3.

## 4.6 Epidemiological instrumentation

### 4.6.1 The contamination runner

`scripts/run_contamination.py` is the experiment engine: one script serves
every arm, with all differences expressed in configuration
(Section 4.8.2). A run proceeds as:

- **Step 0 — seeding.** The active entity keys are read from the extraction
  manifest (the entities the workload actually retrieves for). Under
  `seed_placement: active`, the candidate pool is the union of those keys'
  retrieval neighbourhoods (`pool_per_key = 50` per key); under `random`,
  the injector draws uniformly from the Susceptible KG (the RQ1 control).
  The injector then applies `injections_per_type = 15` corruptions per error
  type, and the runner records each as a *payload*
  `{root_type, field, before, after}` keyed by triplet id.
- **Steps 1..N (`steps = 10`) — transmission cycles.** Each cycle samples
  `entities_per_step = 12` active entities; for each, it retrieves up to
  `context_limit = 5` facts above the floor, has the synthesis model write a
  paragraph from them, and has the ExtractionAgent re-extract triplets from
  that paragraph with the same facts as lineage context. Between cycles,
  the ValidationAgent runs `audits_per_step` audit passes over the cycle's
  read/written ids (targeted) or a random sample.
- **After every cycle — measurement** (Section 4.6.3), with the full task
  and probe evaluation battery on eval steps (every `eval_every = 5` steps
  and the final step).

The runner aborts at start-up if the KG already contains
ground-truth-corrupted nodes — stale injections from a previous sequence
would confound every count — unless `--allow-dirty` is passed explicitly.

### 4.6.2 Ground-truth transmission bookkeeping

The runner, acting as experimenter rather than agent, classifies every newly
written triplet (`check_transmission`):

- **Exposed** — at least one lineage parent carries a contamination payload;
  cumulative exposure is a trajectory column.
- **Infected** — the triplet's content reproduces a payload's corrupted
  value and not the original. Matching is field-specific, tuned against a
  first-run audit: object payloads (entity swaps, stripped qualifiers) must
  equal the derived subject or object *exactly* after normalization —
  substring matching over-counted fragments like "New Orleans" inside "New
  Orleans Pelicans" or "2006" inside "14 September 2006" — while predicate
  payloads (strengthened relations) use word-boundary matching, because
  extraction re-phrases predicates ("lead actor" → `lead_actor_in`). The
  rule is conservative by construction: paraphrased reproductions are not
  counted, so infection counts are a lower bound.

An infected triplet receives `error_type = propagated_<root_type>` and its
payload is added to the payload map, so second-generation transmission is
tracked and every propagated error remains attributable to its root injected
error — the lineage-based attribution used throughout Chapter 5. The cycle
additionally instruments the β decomposition directly: counts of retrieval
contexts containing ≥1 contaminated fact and of contaminated facts served,
so that β = P(retrieve contaminated) × P(reproduce | exposed) can be
estimated from the run itself rather than assumed.

### 4.6.3 Trajectory logging

`measure()` appends one row per step combining three views of the graph:
operational SIR counts (`count_by_state`), ground-truth contamination per
error type — seeded and propagated separately (`count_by_error_type`) — and
the detection confusion (`detection_confusion`): `det_R_contam` (true
quarantines), `det_R_clean` (mitigation collateral), and the analogous
infected-mark columns. Cycle statistics (new triplets/edges,
exposed/infected, context contamination counts, audits/quarantines/cascades)
and the eval-step metric columns complete the row. At run end the final
confidences yield the detection AUROC: all ground-truth-contaminated nodes
versus a 500-node random clean sample, suspicion score = 1 − confidence
(`get_contamination_confidences`; `detection_auroc` in
`src/evaluation/metrics.py`).

### 4.6.4 SIR model and R₀ fitting

`src/sir/sir_model.py` implements the discrete-time SIR difference equations
by forward Euler, with per-step clamping of new infections/recoveries to the
available compartments. `src/sir/r0_calculator.py` computes R₀ = β/γ; its
original four-parameter decomposition (retrieval rate × susceptibility,
validation frequency × detection accuracy) is a Phase 1 planning construct —
the as-run pipeline enters through `R0Calculator.from_beta_gamma` with
empirically fitted values.

`scripts/fit_sir.py` performs the post-hoc fit (Section 3.4). One subtlety
is documented at length in its module docstring: the trajectory CSV's raw
`S`/`I`/`R` columns are *operational bookkeeping, not epidemic
compartments* — `I` is always 0 as a node state, `R` includes false-positive
quarantines, and `S` is simply the growing triplet count. The epidemic
series is therefore reconstructed from the ground-truth columns:

```
I(t) = gt_total(t) − det_R_contam(t)     # infected, not yet caught
R(t) = det_R_contam(t)                   # caught and removed from spread
N    = S(0);  S(t) = N − I(t) − R(t)
```

Fitting uses `scipy.optimize.least_squares`, forward-simulating
`SIRModel.run` itself — so the fitted (β, γ) are literally what the model
would reproduce, clamps included. Arms without a quarantine curve
(`det_R_contam` ≡ 0) get a one-parameter β fit with γ fixed at 0, since
fitting a recovery rate to a curve that never recovers is meaningless and
R₀ = β/γ undefined; those arms report the per-step effective reproduction
(mean of β·S(t)/N) instead, alongside the model-free empirical reproduction
per index case as a cross-check. Fit RMSEs are carried into the output CSV;
the S-never-depletes scale caveat is stated in Sections 3.4 and 5.5.

## 4.7 Evaluation harness

`scripts/run_baseline_eval.py` implements the KG-grounded task evaluation;
`scripts/run_contamination.py` imports its functions so per-step evaluation
inside a run and standalone baseline measurement are the same code path.
For each question or claim, capitalized-token-run heuristics extract entity
keys, facts are retrieved per key above the configured floor (the evaluator
is itself an agent reading the shared memory, so it honors the same floor as
the pipeline), and the Groq model must answer using *only* those facts,
under strict JSON contracts (`_QA_SYSTEM`: a short answer span or
`"unknown"`; `_FEVER_SYSTEM`: one of the three FEVER labels). Parse
failures are counted, scored as wrong (empty answer / NEI), and never
retried into the metrics.

Scoring lives in `src/evaluation/metrics.py`, all pure functions with no LLM
or DB access:

- **Exact Match / token F1** — SQuAD-style normalization (lowercase,
  articles and punctuation stripped).
- **Veracity accuracy** — accuracy plus a full per-label confusion table;
  out-of-vocabulary predictions coerce to NOT ENOUGH INFO.
- **Detection AUROC** — `roc_auc_score` over suspicion = 1 − confidence,
  returning 0.5 when only one class is present.
- **USR** — the mechanical grounding metric (design rationale and
  limitations in Section 3.7). `answer_traceable` implements the span rule:
  a normalized answer is traceable if it appears inside some retrieved
  fact's subject/object/predicate or vice versa, with word-boundary
  containment; abstentions and bare booleans (`"", "unknown", "yes", "no"`)
  are non-groundable and excluded, with the abstention rate reported
  separately. `sentence_usr` implements the sentence rule for
  multi-sentence text (supported iff some retrieved fact has both endpoints
  named in the sentence) over an abbreviation-safe splitter. The HotpotQA
  evaluator emits per-row traceability and summary `usr`/`usr_n`/
  `abstain_rate`, which the contamination runner maps into trajectory
  columns; FEVER is excluded (its answer is a class label, not a groundable
  span). No LLM is involved anywhere in USR.

The probe evaluation (`run_probe_eval` in `scripts/run_contamination.py`) is
the harm-when-reached instrument (Section 3.7): for every ground-truth
corrupted node (capped at `probe_limit = 60` in sorted-id order for
determinism), a question is generated *from the corrupted triplet itself*
("What is the '<predicate>' of <subject>?"), answered over `probe_facts = 8`
retrieved facts, and the answer classified by word-boundary matching as
*contaminated* (reproduces the corrupted value), *original* (the
pre-corruption value), or *other*. The probe set grows as infections
accumulate, so `probe_n` is reported with every rate.

## 4.8 Run protocol and reproducibility

### 4.8.1 The three-stage clean room

Every contamination run starts from an identical state, produced by three
commands in order:

```
python scripts/load_kg.py --clear                 # ~50K pristine T-REx, all S
python scripts/run_extraction.py --config experiments/configs/extraction_baseline.yaml
python scripts/run_contamination.py --config experiments/configs/contamination_<arm>.yaml
```

Stage 2 replays the extraction workload deterministically (fixed seed 42,
50 documents per dataset, validation split, 2 paragraphs per HotpotQA
document — `experiments/configs/extraction_baseline.yaml`), writing the
extraction manifest whose entity keys define the active subgraph for
stage 3. Stage 3's dirty-KG preflight (Section 4.6.1) enforces that
stages 1–2 actually ran. Neo4j itself is Desktop-managed and must be started
manually before stage 1; runs begin with a connectivity check and, for long
batches, a relaunch script is kept ready — all outputs are written
incrementally, so an external kill loses nothing but the not-yet-written
manifest.

### 4.8.2 Configuration system

Every runner accepts `--config <yaml>`; `src/config.py` loads a flat mapping
whose keys equal the CLI flag names, applied via argparse `set_defaults` so
explicit CLI flags still win. Arms are therefore *config diffs, never code
diffs*: `contamination_mitigated.yaml` differs from
`contamination_baseline.yaml` only in the mitigation block
(`retrieval_threshold: 0.5`, `audits_per_step: 1`, `audit_sample: 25`,
`audit_targeted: true`, `quarantine_threshold: 0.4`,
`trio_confidence: true`); the oracle and tuned arms add exactly one key each
(`oracle_validation: true`, `validator_prompt: tuned`); the control arm
changes only `seed_placement`. The complete arm configurations are in
`experiments/configs/`. [PHASE-4] The RQ3 parameter sweeps will reuse this
mechanism — one YAML per grid point over density, write-frequency, and
validation-interval parameters.

### 4.8.3 Seeding semantics

Three RNG streams are deliberately decoupled:

- The **run seed** (`random_seed`) drives injection placement, pool
  shuffling, and per-step entity sampling. It does **not** fix LLM
  generation: hosted APIs are not bit-deterministic even at temperature 0,
  so same-seed reruns diverge in generated content. Rerun deltas are
  API nondeterminism, not bugs (working rule 6; the Section 5.4.1
  replication note quantifies one instance).
- The **evaluation seed** (`eval_seed`, fixed at 42 for all runs from
  2026-07-09 onward) samples the task questions, decoupled from the run
  seed so task metrics compare identical questions across runs and seeds.
- **Probes** intentionally use the run seed's world: they are generated from
  that run's corrupted nodes and are inherently run-specific.

Determinism of everything *around* the LLM is engineered explicitly:
counter-derived triplet ids (Section 4.3.1), id-tie-broken retrieval
(Section 4.2.4), sorted probe order, and a fixed question sample.

### 4.8.4 Outputs and manifests

Each run emits to `results/raw/`: a trajectory CSV (one row per step — the
curves everything in Chapter 5 is fitted to), a JSON manifest (full
configuration, the injection records with before/after values, the complete
transmission log, and the extraction-manifest path), per-question evaluation
CSVs per eval step, and per-probe CSVs. Aggregations promoted to
`results/summaries/` are the citable archive per the project's analysis
discipline; no number is quoted in the thesis that cannot be traced to one
of these files.

### 4.8.5 LLM call durability and caching

The shared client (`src/agents/llm_client.py`) makes long runs survivable on
free tiers: transient errors retry with backoff, and rate-limit errors honor
the server's own stated wait (capped at 300 s) instead of burning retries
into a closed window — so rate limiting stretches wall-clock time without
corrupting results. A configured `sleep` (1.0 s) between calls paces every
loop. Every request/response can be audit-logged to JSONL (`LLM_LOG_FILE`).

The client also implements an on-disk response cache keyed on
(provider, model, temperature, system, prompt), active only at
temperature 0 and only when `LLM_CACHE_DIR` is set. One operational
correction is on record (thesis log, 2026-07-12): the environment variable
was in fact unset for every run up to that date, so all Phase 2–3 runs and
reruns executed as full fresh generations; the cache has been enabled since.
No archived result is affected — an enabled cache returns byte-identical
stored responses and changes cost, not behaviour — but earlier session
narratives crediting reruns to cache replay were retracted.

## 4.9 Engineering constraints and pragmatic choices

**Hardware forced the API pivot.** The local machine (Ryzen 5, 16 GB RAM,
RX 560X) has no usable GPU acceleration — the RX 560X lacks ROCm support on
Windows — and CPU-only inference of a 12B model at Q4 quantization runs at a
few tokens per second: a full 10-step contamination run with per-step
evaluation would take days per arm. The pivot to hosted APIs (Section 4.1)
made the experimental programme tractable while preserving the model
families; the Ollama code path was kept for local smoke testing.

**Free-tier budgets shaped the experimental design.** Both APIs are used on
free tiers (a deliberate constraint; paid upgrades were declined). Groq's
rolling 24-hour token budget caps throughput at roughly one to three full
runs per day, which is why: audit samples are capped at 25 nodes per step
(one judge call each); replication was concentrated where it decides claims
(baseline and mitigated arms) rather than spread over every arm; the oracle
arm's zero-LLM-call audits are a budget feature as well as a design feature;
and token-free work (fitting, analysis, USR) was scheduled into exhausted
windows. The judge model is never switched mid-experiment
(`llama-3.1-8b-instant` throughout) — a cheaper judge would confound the
validator-precision findings with a model change.

**Windows/encoding hazards.** All scripts reconfigure stdout to UTF-8
(Windows consoles default to cp1252) and read/write files with explicit
UTF-8 encoding. One incident is on record: re-saving a calibration CSV
through Excel silently re-encoded passage bytes to cp1252, which was caught
because it perturbed downstream byte-keyed comparisons — since then,
human-labelling artifacts are round-tripped as UTF-8 text only.

**Small, auditable mechanisms over frameworks.** No agent framework is
used. Each agent is a small class with one LLM call and a strict JSON
contract; the mitigation module is ~100 lines; metrics are pure functions.
This is a deliberate methodological stance: every mechanism that produces a
thesis number must be small enough to audit, unit-test, and cite by file and
line — the measurement pipeline's own error processes are themselves under
study (Section 3.8), and an inscrutable stack would undermine exactly the
claims the thesis makes.
