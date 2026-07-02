# Cascading Knowledge Contamination in Shared Memory Multi-Agent AI Systems

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

The **Basic Reproduction Number (R₀)** quantifies how fast each error type spreads across the graph under different system configurations.

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
| Basic Reproduction Number (R₀) | Contagion velocity per error type per configuration |

---

## Repository Structure

```
src/
  agents/          — ExtractionAgent, OrchestrationAgent, ValidationAgent
  graph/           — Neo4j client, provenance schema (x-tuples, lineage)
  sir/             — Discrete-time SIR model, R₀ calculator
  injection/       — Controlled error injection (3 error types)
  mitigation/      — Trio provenance-aware retrieval + cascade deprecation
  evaluation/      — Metrics computation, experiment runner

data/              — Raw and processed datasets (not committed)
experiments/       — Experiment configuration files
results/           — Aggregated result summaries and figures
notebooks/         — Jupyter analysis notebooks (Phase 5)
docs/              — Thesis outline and supplementary documentation
```

---

## Timeline

| Phase | Period | Deliverable |
|---|---|---|
| Ph.1 Foundation | W1–W8 (Mar–May 2026) | Working infra, datasets, agent scaffolds, SIR module |
| Ph.2 Baseline | W9–W14 (May–Jul 2026) | End-to-end pipeline without mitigation, contamination measurements |
| Ph.3 Mitigation | W15–W18 (Jul 2026) | Trio framework + ablation configuration system |
| Ph.4 Experiments | W19–W21 (Jul–Aug 2026) | Full experiment matrix: baseline vs. mitigated |
| Ph.5 Analysis | W22–W24 (Aug–Sep 2026) | SIR curves, R₀ heatmaps, RQ interpretations |
| Ph.6 Write-up | W25–W26 (Sep 2026) | Thesis submission |

---

## Setup

> Full environment setup instructions will be added at the end of Phase 1.

**Requirements (preview):**
- Python 3.11+
- Ollama (for local model serving)
- Neo4j Community Edition 5.x
- See `requirements.txt` for Python dependencies

---

## Status

**Current Phase:** Phase 1 — Foundation & Setup (W7 of 8)  
**Last Updated:** 2026-05-08
