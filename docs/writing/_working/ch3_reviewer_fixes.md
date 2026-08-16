# Chapter 3 reviewer fixes (working draft, pre-gate)

Scope: only content up to §3.9 (what the reviewer saw). Every number below is
grounded in code/config, cited inline for the fact gate:
- steps=10, injections_per_type=15 (=45 index cases), eval_questions=50, eval_every=5
  → experiments/configs/contamination_baseline.yaml (7,9,21,22).
- confidence/state/lineage NOT touched at injection → src/injection/error_injector.py (16-20),
  and _corrupt only ever returns object/predicate changes (250-273).
- FEVER veracity uses the same 50-question fixed sample at steps 0/5/10 →
  scripts/run_contamination.py run_task_eval (474-500), eval_fever in the same loop.
- root-label attribution of propagated errors → ch3 §3.2 (existing text, lines 82-83).
- Mann-Whitney U two-sided min p at n=4 vs n=4 = 2/C(8,4) = 2/70 = 0.0286.

Each fix names its target anchor (an exact existing sentence in ch3_methodology.md /
report.docx) and whether the new text is INSERTED AFTER it or REPLACES it.

---

## FIX 1 — §3.3, injection is combined (45 in one run) and leaves confidence/lineage alone

Addresses reviewer 4.12 (together or separately) and 4.8 (injection-time treatment).

INSERT AFTER the existing §3.3 sentence that ends:
"...reported with the number of index cases actually placed."

New text (two paragraphs):

All three error types are injected in the same run, fifteen of each, for forty-five
index cases in total, rather than one type to a run. This is possible because each
injected error carries the root label described in Section 3.2, and that label is
passed on to every fact later derived from it. The spread of each type can therefore
be separated out afterwards from a single run, which is what the per-type comparison
of the second research question needs.

One choice about how an error is injected matters for how the later results should be
read. When a triplet is corrupted, only its content changes: the wrong entity, the
dropped qualifier, or the strengthened predicate. Its stored confidence score, its
lineage formula, and its SIR state are left exactly as they were. This is deliberate.
An error that has not yet been caught should look identical to a trustworthy fact,
which is the situation the thesis studies, so nothing about a freshly corrupted
triplet is allowed to mark it as suspect. Two things follow, and the results chapter
returns to both. Because the confidence score still reflects the fact's clean origin,
a check that reads confidence alone has little to work with on the index cases
themselves. And because the lineage of a corrupted-in-place fact still points back to
its clean ancestors, following the lineage forward from a fact that was caught does
not lead back to an index case that was never derived from anything contaminated. The
error, in effect, removes the trail that would lead back to it, which is the same
blind spot noted for in-place extraction errors in Section 2.1.1.

---

## FIX 2 — §3.6, state the run length in prose

Addresses reviewer "§3.6 never states the number of steps in prose."

INSERT AFTER the existing §3.6 sentence that ends:
"...only then does the contamination run begin."

New sentence (append to that paragraph):

Each run is ten steps long, and every step works through the same fixed number of
entities, so runs differ only in configuration and seed and never in length.

---

## FIX 3 — §3.7 Table 3.5, give Veracity Accuracy the same detail as Exact Match

Addresses reviewer "§3.7: Veracity Accuracy specifies neither steps nor sample size."

REPLACE the Veracity Accuracy cell text in Table 3.5:
OLD: "FEVER claim classification: the share of claims labelled correctly against the ground truth"
NEW: "FEVER claim classification: the share of claims labelled correctly against the ground truth, on the same fixed set of 50 claims, at steps 0, 5, and 10"

---

## FIX 4 — §3.9, reconcile model hosting with Table 3.1

Addresses reviewer "§3.9 vs Table 3.1 contradiction" (says no graphics card, table says API).

REPLACE the existing §3.9 sentence:
OLD: "Two open models are used, one for extraction and one for judgement, both small
enough to run on a single machine with no graphics card, so behaviour on larger or
commercial models may differ."
NEW: "Two open-weight models are used, one for extraction and one for judgement, both
small by current standards, in the low tens of billions of parameters, so behaviour
on larger or commercial models may differ. For the experiments they were reached
through hosted inference services rather than run on the local machine (Section 4.1),
a choice made for speed on the available hardware that does not change which models
were used."

---

## FIX 5 — §3.9, model-family wording (remove the internal contradiction)

Addresses reviewer 4.4: §3.9 "held fixed for the whole study" contradicts the
abstract's cross-family claim. (The cross-family arm itself lives in Chapter 5, not
added here; this only softens the absolute wording so the report stops contradicting
its own abstract.)

REPLACE the existing §3.9 clause:
OLD: "the judge model used for validation and auditing is held fixed for the whole
study, since changing it partway would confound a change in the system with a change
in the ruler."
NEW: "the judge model used for validation and auditing is held fixed across the
comparative arms, since changing it partway would confound a change in the system
with a change in the ruler."

---

## FIX 6 — §3.4, identifiability of the rates and how to read R0

Addresses reviewer 4.5 (only b - g identifiable from the I-curve; g recovered
separately from R; beta is a per-step hazard, R0 not a cross-condition constant).

INSERT AFTER the existing §3.4 sentence that ends:
"...using non-linear least squares. Section 5.5 reports the fits and how well they match."

New paragraph:

One caveat about this fit is worth stating plainly. From the infected curve on its
own the two rates cannot be told apart, because many different pairs of β and γ
produce the same net growth, and only their difference is fixed by that curve. They
can be separated here because the recovered count is observed on its own: each step
records how many contaminated facts the validator quarantined, which pins γ directly,
and β then follows. Even so, β is best read as a per-step hazard, a rate of spread for
this particular setup, rather than a constant of nature, and R₀ as a summary of how
fast contamination spread within these runs, not a fixed number that would carry
unchanged to a different graph or workload.

---

## FIX 7 — §3.9, name the two limits of the small-sample rule

Addresses reviewer 4.10 (min attainable p under the both-tests-agree rule; noise SD
itself estimated from n=4).

INSERT AFTER the existing §3.9 sentence that ends:
"...claiming an effect that is not there would be worse than missing one."

New text (append to that paragraph, or as a short following one):

Two limits of this scheme are worth naming. With only four runs in each group, and
both tests required to agree, the Mann-Whitney U test can reach at best a two-sided p
of about 0.03, and only when the two groups do not overlap at all, so no small or
partial difference can ever be called real under this rule. And the noise threshold of
Section 3.6, twice the baseline's standard deviation, rests on a standard deviation
that is itself estimated from only four runs, so it is a rough guide rather than an
exact cut-off.

---

## FIX 8 — §3.9, the per-type spread ranking carries a measurement asymmetry

Addresses reviewer 4.9 (a value substitution may be easier to recognise as
"reproduced" than a strengthened predicate or a dropped qualifier).

INSERT into §3.9 construct-validity area, AFTER the existing sentence that ends:
"...counts as supported and the analysis treats it that way."

New sentence:

One measurement asymmetry bears on the second research question in particular. A
propagated error is counted when a newly written fact carries an injected error
forward, and an entity substitution, which changes a single object, can be easier to
recognise as carried forward than a strengthened predicate or a dropped qualifier. The
per-type ranking of spread should therefore be read as indicative, with this asymmetry
of the instrument kept in mind.

---

## FIX 9 — §2.1.2, add the primary source for error compounding (Zhang "snowballing")

Addresses reviewer Section 6 (Zhang et al. is the primary source for the compounding
claim currently carried by [9] alone). VERIFIED real: arXiv:2305.13534, ICML 2024,
finding = models over-commit to an early wrong answer and generate further claims to
stay consistent with it, though the same model asked directly often recognises those
claims as false.

INSERT AFTER the existing §2.1.2 sentence that ends:
"...a short chain of steps can drift further from the facts at each one [9]."

New sentence:

A study of this effect finds that a model will commit to an early wrong answer and
then produce further claims that keep it consistent, even though the same model, asked
about those claims on their own, often recognises them as false [NEW-SNOWBALL].

---

## FIX 10 — Table 2.1, correct the Margalit et al. [19] row (do not oversell)

Addresses reviewer 4.6. VERIFIED: the paper does build and measure its mechanism
(a production service and a test harness), but not under propagating error. It is a
single, recent, non-peer-reviewed, self-reported industry preprint, so the correction
states what they did without leaning on it as strong evidence.

REPLACE the Table 2.1 cell for Margalit et al. [19] (Provenance mitigation column):
OLD: "proposed, not stress-tested"
NEW: "built and measured, not tested under spreading error"

ALSO REPLACE the §2.2 sentence:
OLD: "Margalit et al. [19] name the failure modes of shared agent memory, including the
loss of provenance, and propose provenance tracking and governed sharing as the fix."
NEW: "Margalit et al. [19] name the failure modes of shared agent memory, including the
loss of provenance, and build and measure provenance tracking and governed sharing as
the fix, though they test it on ordinary operation rather than under a spreading error."

(HELD, not in this pass: a §2.3.3 paragraph claiming their contradiction-gate result as
convergent evidence, and the §2.2 additions of Ju et al. / Gu et al. / Shen et al. with
a §2.2 split. These reshape the novelty-critical Related Work and need paragraph-level
approval. Offer separately.)

---

## FIX 11 — the dataset/model/infra citations (reviewer 4.7), all VERIFIED

In-text [n] at first mention, exact anchors from ch3_methodology.md:

- Neo4j [NEW-NEO4J]: §3.2, sentence "The shared memory is a Neo4j graph."
  → "The shared memory is a Neo4j graph [NEW-NEO4J]."
- T-REx [NEW-TREX]: §3.2, "...with about 50,000 correct triplets from the T-REx dataset,
  a large set of facts drawn from Wikipedia and aligned with Wikidata."
  → append [NEW-TREX] after "T-REx dataset [NEW-TREX],".
- Mistral Nemo [NEW-MISTRAL] and Llama [NEW-LLAMA]: §3.1, the sentence
  "The ExtractionAgent runs the larger Mistral Nemo 12B ... Llama 3.1 8B." Attach each
  citation to the model's first in-text mention in §3.1 paragraph (lines 33-37):
  "...runs the larger Mistral Nemo 12B [NEW-MISTRAL], which is stronger..." and
  "...run the smaller and faster Llama 3.1 8B [NEW-LLAMA]."
- HotpotQA [NEW-HOTPOT] and FEVER [NEW-FEVER]: first prose mention is §3.7 Table 3.5.
  Attach in the Table 3.5 cells: "HotpotQA [NEW-HOTPOT] answers against the ground truth..."
  and "FEVER [NEW-FEVER] claim classification:...". (FEVER also appears in §3.8; the
  citation at first mention in §3.7 suffices.)

Reference entries to add to references.md and the report bibliography (with bookmarks +
external links, same mechanism as [28]-[34]):

[NEW-TREX] H. Elsahar, P. Vougiouklis, A. Remaci, C. Gravier, J. Hare, F. Laforest, and
E. Simperl, "T-REx: A Large Scale Alignment of Natural Language with Knowledge Base
Triples," in Proc. 11th Int. Conf. on Language Resources and Evaluation (LREC), 2018.
Available: https://aclanthology.org/L18-1544/

[NEW-HOTPOT] Z. Yang, P. Qi, S. Zhang, Y. Bengio, W. W. Cohen, R. Salakhutdinov, and
C. D. Manning, "HotpotQA: A Dataset for Diverse, Explainable Multi-hop Question
Answering," in Proc. Conf. on Empirical Methods in Natural Language Processing (EMNLP),
2018, pp. 2369-2380. Available: https://doi.org/10.18653/v1/D18-1259

[NEW-FEVER] J. Thorne, A. Vlachos, C. Christodoulopoulos, and A. Mittal, "FEVER: a
Large-scale Dataset for Fact Extraction and VERification," in Proc. Conf. of the North
American Chapter of the Association for Computational Linguistics: Human Language
Technologies (NAACL-HLT), 2018, pp. 809-819. Available: https://doi.org/10.18653/v1/N18-1074

[NEW-NEO4J] Neo4j, Inc., "Neo4j Graph Database Platform," 2024. [Online]. Available: https://neo4j.com/

[NEW-MISTRAL] Mistral AI and NVIDIA, "Mistral NeMo: A 12B Model with a 128k Context
Length," Jul. 2024. [Online]. Available: https://mistral.ai/news/mistral-nemo

[NEW-LLAMA] A. Grattafiori, A. Dubey, A. Jauhri, et al. (Llama Team), "The Llama 3 Herd
of Models," arXiv:2407.21783, 2024. Available: https://arxiv.org/abs/2407.21783

[NEW-SNOWBALL] M. Zhang, O. Press, W. Merrill, A. Liu, and N. A. Smith, "How Language
Model Hallucinations Can Snowball," in Proc. 41st Int. Conf. on Machine Learning (ICML),
2024. Available: https://arxiv.org/abs/2305.13534

---

## FIX 12 — §3.9, note the dataset and model licences (reviewer 4.7)

INSERT into §3.9 external-validity paragraph, AFTER the existing sentence that ends:
"...may understate how well a model resists an error about a famous entity it already
knows well."

New sentence:

The three datasets are public research benchmarks released for academic use under open
licences, and both models are open-weight releases under their own licences, so all of
them are used here within the terms their authors set.

## NEEDS ASHWIN (cannot be written truthfully without him) — reviewer 4.11

§3.8 human calibration: who labelled the 40-item sample (was it Ashwin alone?), was
there a second rater / any inter-rater agreement, and was the correction to the
783-fact audit a flat factor or inverse-probability weighted (the sample is
stratified, not random). Ask before writing anything here.

## NEEDS ASHWIN (cannot be written truthfully without him) — reviewer 4.11

§3.8 human calibration: who labelled the 40-item sample (was it Ashwin alone?), was
there a second rater / any inter-rater agreement, and was the correction to the
783-fact audit a flat factor or inverse-probability weighted (the sample is
stratified, not random). Ask before writing anything here.
