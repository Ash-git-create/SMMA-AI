# CLAUDE.md — Project Bible for Claude Code

This file is read by Claude Code at the start of every session. It contains everything needed to work on this project without drifting.

---

## What this project is

**Master Thesis:** Cascading Knowledge Contamination in Shared Memory Multi-Agent AI Systems  
**Student:** Ashwin Jayan | SRH University Heidelberg | M.Sc. Applied Data Science & Analytics  
**Supervisor:** Prof. Dr. Ing. Binh Vu | Second Supervisor: Prof. Dr. Ing. Swati Chandana  
**Timeline:** 26 weeks | 2026-03-25 → 2026-09-23  

---

## The core problem (in one paragraph)

When multiple LLM agents share a central Knowledge Graph (KG), extraction errors — hallucinations, entity mismatches, dropped qualifiers — don't stay local. They get written into the shared memory and retrieved by other agents as if they were facts. Those agents build on the corrupted facts, producing further errors, which cascade. A system where each agent is 95% accurate degrades to ~59% cumulative accuracy over 10 pipeline steps. This is "cascading knowledge contamination." It is non-adversarial (no attacker needed) and largely unstudied at the system level.

---

## 4 Research Questions

1. Under what conditions do non-adversarial errors persist and spread in shared-memory MAS?
2. Which error types (qualifier loss, relation strengthening, entity disambiguation) are most harmful?
3. How do graph density, memory write frequency, and validation intervals affect contamination velocity and reach?
4. Can Trio-inspired provenance-aware retrieval reduce contamination while preserving answer quality?

---

## System Architecture

### Models (via Ollama, CPU-only on local machine)
| Model | Role | Why |
|---|---|---|
| Mistral Nemo 12B Q4_K_M | Extraction & synthesis | DRAGON score 0.688, best local extraction |
| Llama 3.1 8B Instruct | Orchestration, validation, confidence scoring | Faster, lower memory, DRAGON 0.588 |

### Shared Memory
- **Neo4j Community Edition** — central Knowledge Graph, SPO triplets
- Every node stores provenance metadata: `{source_id, agent_id, timestamp, confidence_score, lineage}`

### Datasets
| Dataset | Purpose |
|---|---|
| T-REx | Pre-populates KG with ground-truth SPO triplets (the "pristine/susceptible" baseline) |
| HotpotQA | Multi-hop Q&A — measures Exact Match degradation as KG contaminates |
| FEVER | Claim verification — measures Veracity Accuracy under contamination |

### Error Taxonomy (controlled injection — 3 types)
1. **Entity Disambiguation Failure** — wrong entity substituted for a predicate
2. **Qualifier Loss** — temporal/spatial/conditional modifiers dropped from a triplet
3. **Relation Strengthening** — weak associative predicate upgraded to strong causal one

### Mitigation: Trio Framework
Inspired by Stanford ULDB (Uncertainty Lineage Databases):
- **x-tuples**: each KG node stores `(value, confidence, lineage_formula)`
- **Lineage function**: DNF boolean formula linking derived nodes to their ancestor source nodes
- **Confidence propagation**: derived node confidence = f(parent confidences) via arithmetization
- **Cascade deprecation**: when hallucination detected, walk lineage graph and deprecate all downstream dependents
- **Retrieval threshold**: agents only retrieve nodes above a configurable confidence floor

### Epidemiological Model: SIR
Discrete-time SIR applied to KG nodes:
- **S (Susceptible)**: pristine T-REx nodes, accurate but unvalidated
- **I (Infected)**: contaminated nodes (error written by agent)
- **R (Recovered)**: validated/quarantined nodes (flagged by ValidationAgent)
- **Beta**: KG retrieval frequency × LLM susceptibility to retrieved context
- **Gamma**: validation agent efficacy
- **R₀**: Basic Reproduction Number per error type per configuration — the headline metric

---

## Evaluation Metrics

| Metric | Category | How measured |
|---|---|---|
| Exact Match (EM) | Task performance | HotpotQA predicted answer vs ground truth |
| Veracity Accuracy | Task performance | FEVER claim classification (Supported / Refuted / NEI) |
| Unsupported Sentence Ratio (USR) | Provenance | % answer sentences not traceable to a high-confidence KG node |
| Error Detection AUROC | Epidemiological | Classifier ability to detect hallucinated nodes step-by-step |
| Basic Reproduction Number (R₀) | Epidemiological | Contagion velocity per error type per graph configuration |

---

## Project Structure

```
SMMA_AI_Systems/
├── CLAUDE.md                  ← you are here
├── README.md                  ← human-readable project overview
├── .gitignore
├── requirements.txt           ← Python dependencies
├── src/
│   ├── agents/
│   │   ├── extraction_agent.py      ← Mistral Nemo 12B: text → SPO → Neo4j
│   │   ├── orchestration_agent.py   ← Llama 3.1 8B: validates, scores, manages context
│   │   └── validation_agent.py      ← audits KG nodes, flags low-confidence triplets
│   ├── graph/
│   │   ├── neo4j_client.py          ← Neo4j connection + CRUD helpers
│   │   └── provenance_schema.py     ← x-tuple structure, lineage formula builder
│   ├── sir/
│   │   ├── sir_model.py             ← discrete-time SIR difference equations
│   │   └── r0_calculator.py         ← R₀ from beta and gamma parameters
│   ├── injection/
│   │   └── error_injector.py        ← controlled injection of 3 error types
│   ├── mitigation/
│   │   └── trio_framework.py        ← provenance-aware retrieval + cascade deprecation
│   └── evaluation/
│       ├── metrics.py               ← EM, Veracity Accuracy, USR, AUROC
│       └── experiment_runner.py     ← ablation study runner
├── data/
│   ├── raw/                   ← downloaded datasets (git-ignored)
│   └── processed/             ← normalized JSON (git-ignored)
├── experiments/
│   └── configs/               ← YAML/JSON experiment configs
├── results/
│   ├── raw/                   ← per-run CSVs (git-ignored)
│   └── summaries/             ← aggregated tables and plots (committed)
├── notebooks/
│   └── analysis/              ← Jupyter notebooks for Phase 5 analysis
└── docs/
    └── thesis_outline.md      ← chapter structure and writing plan
```

---

## 6-Phase Timeline

| Phase | Weeks | Dates | Goal |
|---|---|---|---|
| Ph.1 Foundation & Setup | W1–W8 | 2026-03-25 → 2026-05-19 | Working infra, datasets loaded, agents scaffolded |
| Ph.2 Baseline | W9–W14 | 2026-05-20 → 2026-07-01 | End-to-end pipeline without mitigation, measure natural contamination |
| Ph.3 Mitigation | W15–W18 | 2026-07-02 → 2026-07-29 | Trio framework implementation + ablation config system |
| Ph.4 Experiments | W19–W21 | 2026-07-30 → 2026-08-19 | Full-scale experiments: baseline vs mitigated |
| Ph.5 Analysis | W22–W24 | 2026-08-20 → 2026-09-02 | Interpret results, answer 4 RQs, produce figures |
| Ph.6 Write-up | W25–W26 | 2026-09-03 → 2026-09-23 | Submit thesis PDF + code |

---

## Hardware Constraints

- **GPU:** RX 560X — no ROCm support on Windows. **No GPU acceleration locally.**
- **RAM:** 16GB
- **CPU:** Ryzen 5
- **Strategy:** Ollama CPU-only for local dev and small experiments. Google Colab + Groq API for large-scale runs.
- Mistral 12B at Q4_K_M needs ~8GB RAM — feasible on CPU but slow (~3–5 tok/s)

---

## Working Rules (for Claude Code)

1. **Git:** Never run git commands. Always output them as text for Ashwin to execute.
2. **Commits:** Every meaningful unit of work gets its own commit. Progressive history matters — this is an academic project and the git log is evidence of work.
3. **No speculation:** If a design decision is unclear, ask before implementing.
4. **Memory:** Update `~/.claude/projects/.../memory/` after each session with current phase status and what was done.
5. **No premature abstraction:** Build exactly what each phase needs. Don't over-engineer agents before the experiments demand it.
6. **Data files:** Never commit raw datasets or model weights. Only commit code, configs, and result summaries.
