# Ch2 deepening Wave C (2.1.2 causes of hallucination) — awaiting gates
# Reuses existing citations [4], [9], [10] (no new references).

## Insert in 2.1.2 AFTER the definition paragraph ("...widespread across models and tasks [9].") and BEFORE "Researchers separate hallucinations along two lines."

**E1.**
Why do models hallucinate at all? The root is the training objective [9]. A language model
is trained to predict the next word given the words so far, and it is rewarded for
producing text that looks like its training data, not for producing text that is true.
Truth and likelihood usually agree, but when they part ways the model follows likelihood.
It has no separate step that checks a statement against a source of truth before it writes
it down.

**E2.**
Several conditions make this worse. When a question falls outside what the training data
covered well, the model has little to go on and fills the gap with a fluent guess. When it
is asked to produce output in a fixed shape, such as a table or a set of triples, the
pressure to fill every slot can push it to invent a value rather than leave one blank. And
errors compound: a model shown its own earlier output tends to stay consistent with it, so
an early mistake is carried forward rather than corrected. Extraction, the task at the
centre of this thesis, sits squarely in this danger zone, because it asks the model to turn
free text into filled, structured slots at speed.
