# Thesis Writing Protocol

This file governs how the thesis is written. Read it first thing in any writing
session, before drafting a single word. It does not change unless Ashwin says so.

## Hard requirements

- **Length:** at least 100 pages of genuine, relevant content. 100 is the floor,
  not the ceiling. Never pad with jargon or filler to reach it. If a paragraph
  does not earn its place, cut it.
- **Audience level:** fellow master's students (Ashwin's classmates). A reader at
  that level must be able to follow every sentence. Define each technical term the
  first time it appears. Prefer the plain word over the clever one.
- **No AI language.** See the ruleset below. This is the single most important
  rule after correctness.
- **Every number traces to a file.** No figure appears in the text unless a CSV or
  JSON in `results/summaries/` (or `results/raw/`) backs it (CLAUDE.md rule 1).
- **Citations:** numbered `[1]` style (IEEE-like), matching the Binh Vu reference
  theses. Every external claim carries a citation or gets cut. Running reference
  list lives in `docs/writing/references.md`.

## No-AI-language ruleset

Avoid, always:
- Em-dashes. Use commas, parentheses, a colon, or two shorter sentences.
- The vocabulary tells: delve, leverage, underscore, robust, comprehensive,
  pivotal, seamless, nuanced, realm, testament, crucial, intricate, moreover,
  furthermore, notably, it is worth noting, in today's world, landscape, tapestry.
- The three-part list habit ("fast, cheap, and reliable") used for rhythm.
- The "not just X, but Y" / "not only ... but also" parallelism.
- Hollow openers and closers ("It is important to note", "In conclusion,").
- Vague sourcing ("studies show", "researchers agree") with no citation.
- Superficial -ing clauses tacked on the end ("..., highlighting the importance of").

Write instead: short sentences, concrete nouns, active voice, one idea per
sentence, terms defined on first use.

## The three checker gates

Every subsection is drafted, then three independent agents check it before Ashwin
sees it. Cadence: run the gates once per subsection (3-6 paragraphs), then present
to Ashwin paragraph by paragraph for approval.

Cadence exception (agreed 2026-08-09): for Chapter 2 Section 2.1 Background, present
each subsection as a BLOCK for approval (the gates still run per subsection). Keep
strict paragraph-by-paragraph approval for 2.3 Related Work Comparison, the
novelty-critical, highest citation-risk part.

1. **Style & level gate.** Confirms classmate-level readability, zero AI tells (uses
   the humanizer criteria), and genuine relevance to the thesis (not page-count
   filler). Returns a per-paragraph verdict and specific rewrite notes.
2. **Originality gate.** Flags any sentence lifted or too close to a source, and web
   spot-checks distinctive phrasings. NOT a Turnitin substitute: it cannot produce
   a similarity score. Ashwin runs SRH's Turnitin/Ouriginal on finished chapters as
   the real check.
3. **Fact gate.** Splits claims into two lanes. Our numbers get checked against the
   archived CSVs. External claims and citations get checked via web search. Anything
   unverifiable comes back marked `[VERIFY]`, never smoothed over.

A paragraph reaches Ashwin only after all three gates pass or their flags are
resolved. Ashwin approves, then it is written into the chapter file.

## Chapter structure (agreed, from the Binh Vu house style)

1. Introduction — 1.1 Motivation / 1.2 Problem Statement / 1.3 Research Questions /
   1.4 Approach / 1.5 Thesis Contribution / 1.6 Thesis Outline
2. State of the Art — 2.1 Background / 2.2 Related Work / 2.3 Related Work
   Comparison / 2.4 Summary
3. Methodology (Dataset and Methodology)
4. Implementation
5. Evaluation / Results
6. Discussion — Discussion / Answer to Research Questions / Limitations / Future Work
7. Conclusion

Required front matter (SRH template): bilingual affidavit (German + English),
English abstract + German Zusammenfassung (each <= half a page), TOC, indexes.

## Working files

- `docs/writing/00_protocol.md` — this file.
- `docs/writing/progress.md` — living state: where we are, what is approved, open
  `[VERIFY]` items, running page estimate.
- `docs/writing/references.md` — numbered reference list, added to as we cite.
- `docs/chapters/ch*.md` — the approved chapter text, appended paragraph by paragraph.

## Not committed / kept local

- `For writing/` reference PDFs are third-party copyrighted work. Stay gitignored.
