# Ch2 deepening wave 1 (2.1.1 retrieval + 2.1.2 detection) — awaiting gates

## Add to end of 2.1.1 (after "...covered in Section 2.1.4.")

**A1.**
Because retrieval is the channel this thesis studies, it is worth being precise about how
it works. In its simplest form, retrieval-augmented generation matches a query against a
store of text and returns the most similar passages, which are then placed in the model's
prompt. Similarity is increasingly measured with dense vectors: a trained encoder turns the
query and each passage into points in a high-dimensional space, and the points nearest the
query are returned [21]. The generator then answers using those passages as context.

**A2.**
A knowledge graph changes what is retrieved. Instead of passages, the store returns facts
and the links between them, and retrieval can follow those links across several steps to
gather facts that are related but not next to each other, which is what multi-hop questions
need. Placing a knowledge graph behind a language model in this way is now a distinct line
of work [22], including the graph-based retrieval of GraphRAG mentioned above [3]. For this
thesis the point is simple: whatever an agent retrieves becomes the ground it reasons on,
so a contaminated fact that is retrieved is a contaminated fact that gets used.

## Add to end of 2.1.2 (after "...after it is written into shared memory.")

**B1.**
If hallucinations cannot be prevented, the natural response is to detect them, and how to
do that is its own research area. One family of methods asks the model itself: the same
claim is generated several times, and claims the model states inconsistently across those
samples are treated as likely hallucinations [23]. Another family checks a claim against an
outside source, retrieving evidence and asking whether it supports the claim. A third uses a
second language model as a judge, prompting it to rate whether an answer is supported [24].
The validator in this thesis belongs to the second and third families: it judges a fact
against the evidence held in the graph.

**B2.**
These methods share a weakness that matters here. A detector that checks a claim against
retrieved evidence can only work if the evidence is there to check against. When the
contamination has replaced the original fact rather than sitting beside it, there is no
contradicting evidence to find, and the detector is blind to it. Chapter 5 shows this is
exactly what happens to the validator, and Section 5.4.3 names the mechanism.
