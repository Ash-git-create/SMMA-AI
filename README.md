# Cascading Knowledge Contamination in Shared Memory Multi-Agent AI Systems

Code and experiments for a study of how non-adversarial extraction errors spread
through the shared memory of a multi-agent LLM system, measured with an
epidemiological (SIR) model, and whether a provenance-aware mitigation can
contain them.

---

## The Problem

Modern AI pipelines increasingly chain multiple LLM agents together, with a shared Knowledge Graph (KG) as their collective memory. Each agent reads from and writes to this shared store.

The issue: LLMs make errors. Even a single agent that is 95% accurate will, in a 10-step pipeline, produce cumulative accuracy of only ~59% if errors compound. But in a *shared memory* system, the problem is worse — one agent's error gets written into the KG and retrieved by other agents as a trusted fact. Those agents build on it, producing further errors, which cascade system-wide. This is **cascading knowledge contamination**.

This isn't an adversarial attack. It requires no malicious prompt injection. It emerges from normal, non-adversarial operation — hallucinations, entity mismatches, dropped qualifiers — written into memory and mistaken for ground truth by the system itself.

---

## Research Questions

1. Under what conditions do non-adversarial errors persist and spread in shared-memory multi-agent systems?
2. Which error types (qualifier loss, relation strengthening, entity disambiguation failure) are most harmful?
3. How do graph density, memory write frequency, and validation intervals affect contamination velocity and reach?
4. Can Trio-inspired provenance-aware retrieval reduce contamination while preserving answer quality?

---

## Approach

### System Design

A multi-agent pipeline is built around a central **Neo4j Knowledge Graph**:

- **ExtractionAgent** (Mistral Nemo 12B): reads documents, extracts SPO triplets, writes to KG
- **OrchestrationAgent** (Llama 3.1 8B): routes queries, validates outputs, scores confidence
- **ValidationAgent** (Llama 3.1 8B): audits KG nodes, flags and quarantines low-confidence entries

Every node in the KG stores provenance metadata: source, agent, timestamp, confidence score, and lineage.

### Measuring Contamination: SIR Model

Borrowed from epidemiology, a discrete-time **SIR model** is applied to KG nodes:

- **S (Susceptible):** pristine ground-truth nodes (from T-REx dataset)
- **I (Infected):** contaminated nodes containing extraction errors
- **R (Recovered):** validated/quarantined nodes removed from active retrieval

The **Basic Reproduction Number (R0)** quantifies how fast each error type spreads across the graph under different system configurations.

### Mitigation: Trio Framework

Inspired by Stanford's Uncertainty Lineage Databases (ULDB), each KG node is extended into an **x-tuple** storing:
- A confidence score (derived from LLM log-probabilities)
- A lineage formula (DNF boolean expression linking the node to its source ancestors)

When a contaminated node is detected, the system walks the lineage graph and **cascade-deprecates** all dependent nodes below a confidence threshold — stopping the spread rather than just patching the source.

### Datasets

| Dataset | Role |
|---|---|
| T-REx | Ground-truth SPO triplets — populates the pristine baseline KG |
| HotpotQA | Multi-hop Q&A — measures Exact Match degradation under contamination |
| FEVER | Claim verification — measures Veracity Accuracy under contamination |

---

## Evaluation Metrics

| Metric | What it measures |
|---|---|
| Exact Match (EM) | Final answer quality on HotpotQA |
| Veracity Accuracy | Claim classification accuracy on FEVER |
| Unsupported Sentence Ratio (USR) | % of answer sentences not traceable to a confident KG node |
| Error Detection AUROC | How well the system detects hallucinated nodes step-by-step |
| Basic Reproduction Number (R0) | Contagion velocity per error type per configuration |

---

## Key Findings

- **Contamination spreads with no adversary.** Once a wrong fact enters the retrieval-reachable region of the shared memory, later agents read it as fact and reproduce it, while standard task metrics (EM / F1 / veracity) stay flat — the memory is quietly corrupted while the system still looks fine.
- **Spread is gated by retrieval reachability.** A corrupted fact placed outside the retrieved region does not propagate; persistence and spread are separate properties.
- **Harm tracks plausibility.** Entity-substitution errors (the most fact-like) reproduce most; relation-strengthening (the most flagrant) barely moves.
- **The provenance mitigation does not reliably contain spread.** The binding factor is validator *recall* (how much contamination the checker catches), not precision or the cascade architecture; even a perfect checker only reaches the epidemic threshold rather than ending the spread.

---

## Repository Structure

```
src/
  agents/       — extraction, orchestration (judge), validation agents + LLM client
  graph/        — Neo4j client, provenance schema (x-tuples, lineage), density, k-hop
  injection/    — controlled error injection (3 error types), k-hop placement
  mitigation/   — Trio provenance-aware retrieval + cascade deprecation
  sir/          — discrete-time SIR model, R0 calculator
  evaluation/   — metrics (EM, veracity, USR, AUROC)

scripts/              — experiment runners and analysis (load_kg, run_*, fit_sir, replay_*, stats_tests, ...)
experiments/configs/  — YAML configs for every experiment arm
results/summaries/    — aggregated result tables (per-run raw data is git-ignored)
docs/figures/         — result and concept figures
docs/setup_guide.md   — full setup instructions
data/                 — datasets (git-ignored)
```

---

## Setup

> Full setup instructions: [`docs/setup_guide.md`](docs/setup_guide.md)

**Requirements:**
- Python 3.11+
- Mistral La Plateforme + Groq API keys (extraction / orchestration)
- Neo4j Community Edition 5.x
- Optional: Ollama as an offline local fallback
- See `requirements.txt` for Python dependencies

Copy `.env.example` to `.env` and fill in your Neo4j credentials and API keys before running.

---

## Reproducing the Experiments

```bash
# 1. Load the pristine T-REx KG into Neo4j
python scripts/load_kg.py --clear

# 2. Run a contamination experiment (config selects the arm)
python scripts/run_contamination.py --config experiments/configs/contamination_baseline.yaml

# 3. Fit the SIR model / compute R0 from the trajectory
python scripts/fit_sir.py
```

Each arm in `experiments/configs/` is self-describing; aggregated outputs land in
`results/summaries/`.

---

## License

Released under the terms in [`LICENSE`](LICENSE).
