# Chapter 3 — Methodology

> **Draft status (2026-07-09):** structure and content complete for Phases 1–3.
> Sections marked `[PHASE-4]` will be extended once the RQ3 parameter sweeps are
> designed. Figures are marked `[FIG]` and will be produced in Phase 5.

## 3.1 System overview

The experimental system is a shared-memory multi-agent architecture in which
multiple LLM-driven agents read from and write to a single central Knowledge
Graph (KG). The design deliberately mirrors the pattern emerging in production
multi-agent systems — specialised agents coordinating through a persistent
store rather than through direct message passing — because the research
questions concern precisely the failure mode this pattern introduces: an error
written by one agent becomes retrievable context for every other agent.

Three agents operate on the KG:

| Agent | Model (as run) | Role |
|---|---|---|
| ExtractionAgent | Mistral Nemo 12B (`open-mistral-nemo`, Mistral API) | Reads text units, extracts SPO triplets, writes them to the KG |
| OrchestrationAgent | Llama 3.1 8B (`llama-3.1-8b-instant`, Groq API) | Answers task questions using KG retrieval as context; synthesises new derived facts |
| ValidationAgent | Llama 3.1 8B (`llama-3.1-8b-instant`, Groq API) | Audits KG nodes against their provenance, flags low-confidence triplets for quarantine |

The original design targeted local CPU inference via Ollama (Section 4.1
discusses the hardware constraint); during Phase 2 the models were pivoted to
their hosted API equivalents (same model families and sizes) to make full
experimental runs tractable. All prompts, roles, and the two-tier model split
(a stronger extractor, a faster orchestrator/validator) were preserved.

**Run cycle.** An experiment proceeds in discrete steps. In each step the
OrchestrationAgent processes a batch of entities: for each entity it retrieves
the top-k triplets from the KG (k = `context_limit` = 5 by default), composes
them into working context, produces derived statements, and writes new
triplets back through the ExtractionAgent's writing path. Contamination
propagates exactly when a corrupted triplet enters some agent's working
context and influences what that agent writes — the retrieval channel is the
transmission vector.

`[FIG] System architecture: three agents around a central Neo4j KG, with the
retrieval (beta) and validation (gamma) channels annotated.`

## 3.2 Knowledge Graph schema and provenance

The KG is a Neo4j property graph storing subject–predicate–object triplets.
Every triplet node carries provenance metadata:

```
{source_id, agent_id, timestamp, confidence_score, lineage, error_type}
```

Following Stanford Trio's ULDB model, each node is an *x-tuple*: a value
paired with a confidence score and a lineage formula. The lineage formula is
a DNF boolean expression over ancestor node identifiers, recorded at write
time whenever a derived triplet is produced from retrieved context. Lineage
serves two purposes: (i) it makes cascade deprecation possible (Section 3.5),
and (ii) it provides the ground-truth transmission graph for the
epidemiological analysis — every propagated error is attributable to its
root injected error (`root_type` attribution was 100% in all runs).

The `error_type` field is experimental bookkeeping, not information available
to agents: it records ground-truth contamination status for measurement and
is never exposed through retrieval.

**Pre-population.** Before each run the KG is loaded with ~50,000 pristine
T-REx triplets. These constitute the Susceptible population in
epidemiological terms: accurate, but unvalidated and structurally
indistinguishable from agent-written content.

## 3.3 Error taxonomy and controlled injection

Three non-adversarial error types are injected, chosen to span the space of
plausible extraction failures:

1. **Entity Disambiguation failure (ED)** — a wrong but related entity is
   substituted for the subject or object.
2. **Qualifier Loss (QL)** — a temporal, spatial, or conditional modifier is
   dropped, silently widening the claim's scope.
3. **Relation Strengthening (RS)** — a weak associative predicate is upgraded
   to a strong or causal one.

The ErrorInjector corrupts existing KG triplets in place (15 index cases per
type per run by default). Not every triplet admits every corruption; the
injector filters a candidate pool for admissibility, which matters for one
methodological detail: when candidates are drawn from the *active retrieval
subgraph* (the default), only 9–10 of 15 RS injections typically find
admissible candidates, whereas the full-KG pool always yields 15/15. RS
results are therefore reported with their realised seed counts.

**Seed placement as a manipulated variable.** By default, index cases are
placed inside the active retrieval subgraph — the region of the KG that the
task workload actually queries — via a pool built from the entities the run
will touch (`--seed-placement active`). A control condition places the same
number of index cases uniformly at random across the full Susceptible KG
(`--seed-placement random`). The contrast between these two conditions
isolates *retrieval reachability* as a necessary condition for spread (RQ1),
independent of the errors' existence in shared memory.

## 3.4 Epidemiological formulation

KG nodes are assigned SIR compartments:

- **S (Susceptible):** pristine T-REx nodes — accurate but unvalidated;
- **I (Infected):** contaminated nodes — an injected index case or a
  propagated error written by an agent under contaminated context;
- **R (Recovered):** nodes quarantined by the ValidationAgent.

The discrete-time dynamics follow the standard difference equations with
transmission rate β (probability per step that contact between an infected
context and an agent write produces a new infection, driven by retrieval
frequency and the LLM's susceptibility to retrieved context) and recovery
rate γ (validation efficacy). The basic reproduction number R₀ = β/γ is the
headline contagion metric; arms without validation (γ = 0) report the
per-step effective reproduction instead, since classical R₀ is undefined.

**Compartment measurement.** I(t) is reconstructed as the cumulative
ground-truth contaminated population minus quarantined-contaminated nodes;
R(t) is the quarantined count. β and γ are estimated post hoc by non-linear
least squares, forward-simulating the SIR difference equations against the
empirical trajectories (Section 5.5). A scale caveat is inherited by design:
with N ≈ 50,000 and |I| < 100, S never depletes, so the model cannot
reproduce late-trajectory plateaus; fit quality is reported alongside the
estimates.

**Empirical per-seed reproduction** (transmissions per index case, from the
lineage bookkeeping) is reported alongside the SIR estimates as a
model-free check, overall and per error type (RQ2).

## 3.5 Trio-inspired mitigation framework

The mitigation under test adapts three mechanisms from Trio/ULDB:

1. **Confidence floor on retrieval** (`retrieval_threshold` = 0.5): agents
   only retrieve triplets above a confidence threshold — an attempt to
   suppress the β channel.
2. **Targeted validation audits** (`audits_per_step` = 1, 25 nodes/audit):
   the ValidationAgent samples nodes that agents read or wrote in the current
   cycle, judges them, and quarantines those below `quarantine_threshold`
   (0.4) — the γ channel. Quarantine triggers **cascade deprecation**: the
   lineage graph is walked and all downstream dependents of a quarantined
   node are deprecated with it.
3. **Confidence propagation at write time** (`trio_confidence`): a derived
   triplet's confidence is computed from its parents' confidences via
   arithmetisation of the lineage formula, so uncertainty compounds along
   derivation chains instead of resetting.

The experimental design treats these as separable levers: single-mechanism
ablation arms isolate the floor and the validation channel, and the full
combination is run as its own arm (Section 3.6). No assumption is made that
the combination is beneficial; whether it is, is an empirical question (RQ4).

## 3.6 Experimental design

**Clean-room protocol.** Every run starts from an identical state: the KG is
cleared and reloaded with the pristine T-REx snapshot, the extraction
pipeline is replayed deterministically (fixed seed 42, identical document
sample), and only then does the contamination run begin. Arms differ only in
their configuration file; within a multi-seed replication, arms differ only
in the contamination RNG seed and run tag.

**Arms (Phase 2–3):**

| Arm | Floor | Audits | Confidence prop. | Purpose |
|---|---|---|---|---|
| `baseline` | off | off | off | unmitigated contamination dynamics |
| `ablation_floor` | 0.5 | off | on | isolate the retrieval floor |
| `ablation_validation` | off | 25/step | off | isolate the validation channel |
| `mitigated` | 0.5 | 25/step | on | full Trio combination |
| `control_random` | off | off | off | baseline with random seed placement (RQ1 control) |
| `oracle` | 0.5 | 25/step (ground truth) | on | full Trio with perfect quarantine decisions — isolates judge precision from architecture (RQ4 upper bound) |

The oracle arm replaces the Llama-8B validator's verdict with the
experimenter's ground-truth contamination labels (the `error_type`
bookkeeping of Section 3.3) while leaving audit targeting, quarantine
mechanics, and cascade deprecation untouched; audits therefore cost zero
LLM calls. It bounds what the architecture can achieve with a perfect
judge and, by construction, cannot exist outside the laboratory — real
deployments have no ground-truth channel, which is what makes validator
precision the operative variable.

**Replication.** The baseline and mitigated (full-Trio) arms were each
replicated across four seeds (42–45): the baseline to establish the
seed-noise envelope, the mitigated arm to test whether its seed-42 result
generalises (Section 5.4.1). Single-run differences smaller than roughly two
baseline standard deviations are treated as within noise and explicitly
hedged. The control arm is a single seed by design: its effect (Section 5.3)
is mechanistically forced rather than statistical, and this is noted as a
limitation rather than replicated.

**Reproducibility controls.** Task-evaluation questions are sampled with a
*fixed* evaluation seed (42) decoupled from the run seed, so task metrics are
comparable across runs; contamination probes use the run seed. All LLM calls
pass through a caching client with server-stated-wait retry, so rate-limit
interruptions stretch wall-clock time without corrupting results (zero failed
calls in all completed runs).

## 3.7 Evaluation metrics

| Metric | Category | Measurement |
|---|---|---|
| Exact Match / F1 | Task | HotpotQA answers vs ground truth (50 fixed questions, steps 0/5/10) |
| Veracity Accuracy | Task | FEVER claim classification (fixed sample, steps 0/5/10) |
| Probe contamination rate | Persistence | Direct queries against the injected facts: fraction of probes whose answer reproduces the corrupted version |
| Propagated / cumulative exposed | Spread | Lineage bookkeeping: errors written under contaminated context; agent contexts containing ≥1 contaminated triplet |
| Detection AUROC | Detectability | Feature-based classifier separating contaminated from clean nodes |
| Quarantine precision | Mitigation | Fraction of quarantined nodes that are truly contaminated |
| R₀ / effective reproduction | Epidemiological | Fitted β/γ (Section 3.4) plus model-free per-seed reproduction |

The probe/task distinction is central to the analysis: probes measure whether
an error *persists and is believed when directly queried*; task metrics
measure whether the workload's aggregate quality degrades. Phases 2–3 show
these can dissociate completely (Section 5.2).

`[PHASE-4]` The Unsupported Sentence Ratio (USR) from the original metric
plan has not yet been wired into runs; a decision to integrate or formally
drop it (with justification) is scheduled before Phase 4.

## 3.8 Validity instrumentation

Because most headline numbers depend on LLM judgement somewhere in the
pipeline, three instruments measure the pipeline's own error processes:

1. **Natural contamination audit.** Every extraction-written triplet (n=783)
   is audited for *fidelity* against its source passage by a judge of the
   same model grade as the ValidationAgent, using the injected error taxonomy
   as the label set. This estimates the base rate of non-adversarial error
   (RQ1) and tests whether the injected taxonomy matches naturally occurring
   errors (RQ2 realism).
2. **Human judge calibration.** A stratified sample of 40 audit rows (20
   judge-SUPPORTED, 20 judge-flagged, including a census of all RELATION
   flags) was blind-labelled by the author against the source passages. The
   human labels serve as ground truth for judge precision/recall, and the
   audit's aggregate rates are corrected by the measured per-category
   precision (Section 5.6).
3. **Truth-channel quantification.** Fidelity auditing cannot see one
   channel by construction: a world-false claim faithfully extracted is
   SUPPORTED. Because FEVER ships ground-truth verdicts, every FEVER-derived
   triplet is mapped to its claim's verdict (SUPPORTS / REFUTES / NEI),
   giving an exact, LLM-free measurement of false and unverifiable content
   entering the KG (Section 5.7).

This layered design — LLM audit, human calibration of the audit, and a
ground-truth channel the audit cannot reach — is itself a methodological
contribution: it demonstrates (and Section 5.6 confirms) that uncalibrated
LLM-judge measurements of contamination can be off by an order of magnitude.
