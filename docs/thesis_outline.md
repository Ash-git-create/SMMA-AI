# Thesis Chapter Outline

**Working Title:** Cascading Knowledge Contamination in Shared Memory Multi-Agent AI Systems

---

## Chapter 1 — Introduction
- Background: rise of multi-agent LLM systems, shared memory architectures
- The contamination problem: why accuracy compounds negatively
- Gap in literature: non-adversarial, systemic contamination unstudied at scale
- Research questions (all 4)
- Contribution summary
- Thesis structure overview

## Chapter 2 — Related Work
- Multi-agent AI systems: architectures, coordination patterns
- Knowledge Graphs as shared memory: Neo4j, RDF stores, SPO triplets
- LLM hallucination: types, causes, detection methods
- Retrieval-Augmented Generation (RAG) and KG-augmented LLMs
- Epidemiological models in information systems (prior SIR applications)
- Provenance and uncertainty in databases: Stanford Trio / ULDB
- Mitigation literature: fact-checking agents, confidence scoring, retrieval filtering

## Chapter 3 — Methodology
- System architecture overview (diagram)
- Agent design: ExtractionAgent, OrchestrationAgent, ValidationAgent
- Knowledge Graph schema: nodes, edges, provenance x-tuple structure
- Error taxonomy: definitions and injection mechanism for all 3 types
- SIR model formulation for KG nodes: S/I/R states, beta, gamma, R₀
- Trio framework adaptation: lineage function, confidence propagation, cascade deprecation
- Experimental design: ablation matrix (error type × injection rate × graph config)
- Evaluation metrics: EM, Veracity Accuracy, USR, AUROC, R₀

## Chapter 4 — Implementation
- Environment and infrastructure (Ollama, Neo4j, Python stack)
- Dataset preparation: T-REx KG population, HotpotQA/FEVER preprocessing
- Agent implementation details and prompt design
- Error injector: controlled and organic (temperature) injection
- SIR simulation runner
- Trio mitigation module
- Experiment runner and logging

## Chapter 5 — Evaluation & Results
- Baseline results: pristine KG performance (EM, Veracity Accuracy)
- Contamination propagation: SIR curves per error type
- R₀ values: heatmap across error type × graph configuration
- Task performance degradation: EM and Veracity Accuracy over time
- Mitigation results: Trio vs. baseline on all 5 metrics
- USR and AUROC comparison
- Statistical significance tests

## Chapter 6 — Discussion
- RQ1: conditions for error persistence/spread
- RQ2: most harmful error type and why
- RQ3: effect of structural parameters (density, write frequency, validation interval)
- RQ4: Trio effectiveness and limits
- Limitations: hardware constraints, dataset scope, model-specific confounders
- Threats to validity: internal, external, construct
- Future work: adversarial injection, larger graphs, real production deployments

## Chapter 7 — Conclusion
- Summary of contributions
- Practical implications for MAS designers
- Final remarks

---

## Appendices (as needed)
- A: Full dataset statistics
- B: Prompt templates used for each agent
- C: Full R₀ tables
- D: Code listing highlights
