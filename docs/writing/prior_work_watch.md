# Prior-work watch (novelty-critical) — all VERIFIED on arXiv

2026 turned "error cascades in multi-agent LLM systems" into an active area. Seven
recent papers overlap parts of this thesis. They overlap DIFFERENT parts, and several
set up the thesis's strongest result rather than pre-empting it. All entries below were
fetched from arXiv directly (title/authors/abstract confirmed).

## The epidemiology one (closest to SIR/R0)
1. Niu, Shu, Zhao — "Reliability-Contagion Feasibility in LLM Multi-Agent Networks"
   arXiv:2607.21912 (Jul 2026). SEIC (susceptible-exposed-infectious-corrected) model
   over LLM AGENT communication networks; derives invasion conditions (an R0 analog).
   DIFFERENCE: their unit is agents in a message network; ours is FACTS (nodes) in a
   shared knowledge-graph memory. Their compartments over agents; our S/I/R over KG
   facts. We add Trio provenance mitigation + the structural-blindness negative result.
   ACTION: retire the bare "first to apply epidemiology" claim; differentiate on unit
   of contagion + shared-KG memory.

## The provenance-mitigation ones (closest to Trio) — and they claim SUCCESS
2. Xie et al. — "From Spark to Fire: Modeling and Mitigating Error Cascades in
   LLM-Based Multi-Agent Collaboration" arXiv:2603.04474 (Mar 2026). Injects a single
   atomic error seed -> false consensus; a genealogy-graph governance layer (message-
   layer plugin) prevents final infection in >=89% of runs.
3. Margalit et al. — "Governed Shared Memory for Multi-Agent LLM Systems"
   arXiv:2606.24535 (Jun 2026). Names fleet-memory failure modes incl. "provenance
   collapse"; proposes provenance tracking + policy-governed propagation (MemClaw).
   KEY POSITIONING: both CLAIM provenance/genealogy mitigation works. THIS THESIS finds
   provenance mitigation (Trio) largely FAILS under a realistic (non-oracle) LLM
   validator, due to structural blindness, and explains why. We are the honest
   counter-result to these optimistic mitigation claims. This is a STRENGTH.

## The validation-timing one (corroborates our cadence finding)
4. Itkin — "Delayed Verification Destabilizes Multi-Agent LLM Belief: Instability
   Thresholds and Optimal Corrector Placement" arXiv:2606.27409 (Jun 2026). Delayed
   verification lets false claims propagate; finds instability thresholds (delay-2
   threshold = inverse golden ratio) and studies corrector placement.
   RELATION: independently corroborates our §5.4.6 result (any in-run cadence contains;
   end-only deferral goes super-critical). Cite as CONVERGENT evidence, not a threat.

## Adjacent / contrast
5. Jamshidi et al. — "Hallucination Cascade" arXiv:2606.07937 (Jun 2026). Tracks
   claim-level errors down 3-agent chains; finds NET ATTENUATION (amp factor 0.644<1).
   CONTRAST: message-passing chains can attenuate; our shared-KG memory can go
   super-critical. Different architecture, opposite headline.
6. Liu — "Contagion Networks: Evaluator Preference Propagation in Multi-Agent LLM
   Systems" arXiv:2606.20493 (Jun 2026). Evaluator PREFERENCE/bias spread by topology
   and committee size. Adjacent (bias, not fact error); larger committees reduce spread.
7. (older) "On the Resilience of LLM-Based Multi-Agent Collaboration with Faulty
   Agents" arXiv:2408.00989 (Aug 2024). Resilience with faulty agents. Background.

## Net effect on the thesis
- NOT scooped. Overlaps are partial and split across seven papers.
- Distinct ground that holds: contagion at the KG-NODE level in a shared PERSISTENT
  memory (Neo4j); S/I/R + R0 per error type per config; the 3-type taxonomy; and the
  provenance-mitigation NEGATIVE result with mechanism.
- Reposition: not "first to notice", but "the systematic node-level study whose
  honest finding is that provenance mitigation fails under a realistic validator" —
  a direct counterpoint to the >=89%-success mitigation papers.

## Adversarial-contrast citation (ch2 §2.2/2.3)
8. Zou, Geng, Wang, Jia — "PoisonedRAG: Knowledge Corruption Attacks to RAG"
   arXiv:2402.07867 (USENIX Security 2025). VERIFIED. Attacker injects crafted texts so
   retrieval returns attacker content (~90% attack success, 5 texts/question). Used as
   the adversarial contrast: this thesis is the non-adversarial counterpart. = ref [16].

## Write-up actions
- [ ] ch2: "Related Work Comparison" subsection covering all 7, grouped as above.
- [ ] 1.5 Contributions: reword #1 (differentiated, no bare priority claim); frame the
      RQ4 negative result explicitly against Xie et al. and Margalit et al.
- [ ] ch5/ch6 cadence: cite Itkin 2606.27409 as convergent with §5.4.6.
