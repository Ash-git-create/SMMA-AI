# Writing Progress

Living state for the paragraph-by-paragraph write-up. Updated after every approved
paragraph. Read `00_protocol.md` first.

## Current position

- **CHAPTER 1 COMPLETE** (1.1-1.6, approved 2026-08-09), in ch1 + report.docx. Refs [1]-[5].
- **CHAPTER 2 COMPLETE + DEEPENED** (2.1-2.4 approved 2026-08-09). Added SIR difference
  equations + R0 derivation (2.1.3), Trio lineage/arithmetization (2.1.4), and 2 figures:
  fig_sir_compartments (Fig 2.1 in 2.1.3), fig_contagion_contrast (Fig 2.2 in 2.3.2).
  Build script now embeds images via ![caption](path). scripts/make_ch2_figures.py.
- **Size so far:** ch1 ~2150 words, ch2 ~2850 words + 2 figures; est. ~22-24 pp.
- Equations currently plain-text (beta/gamma spelled out, · multiply). FINAL POLISH:
  convert to Word equation objects; figure captions use auto-numbering in Word.
- **CHAPTER 3 in progress** (rework of _predraft/ch3_methodology_v0.md, verified vs code):
  3.1 System overview DONE (agent roles corrected vs code: OrchestrationAgent = judge, not
  question-answerer; propagation loop is Mistral end-to-end; Fig 3.1 architecture).
  3.2 Schema DONE (fixed: confidence not confidence_score; added state field; error_type
  stripped before prompt not "never retrieved"; trace-back by-construction). Table 3.2.
  Gate cadence for ch3: fact + style per section; single originality sweep at chapter end.
  Build script now renders markdown tables ([TBL] + | | |) and images.
- **CHAPTER 3 COMPLETE** (3.1-3.8, all fact+style gated vs code; originality sweep CLEAN
  2026-08-10). Sections: overview / schema / injection / SIR formulation / Trio mitigation
  / experimental design / metrics / validity instrumentation. New: Fig 3.1 architecture;
  Tables 3.1 agents, 3.2 provenance fields, 3.3 error types, 3.4 arms, 3.5 metrics.
  Fact gate caught & fixed real errors: OrchestrationAgent = judge not QA-er (+ figure);
  confidence not confidence_score; error_type stripped-before-prompt; propagated/exposed
  were SWAPPED; AUROC uses confidence score not a fitted classifier; trace-back
  by-construction. docx rebuilt: 3 figs, 5 tables, ~186 paras.
- NUMBER-STYLE polish TODO: standardize spelled-out vs numeral (fifty thousand/twenty-five
  vs 783/40) across ch3 in final pass.
- **CH2 DEEPENED** (2026-08-10): 2.1.1 +retrieval/KG-retrieval [21][22]; 2.1.2 +hallucination
  detection [23][24] (foreshadows structural blindness); 2.1.3 +network epidemiology /
  superspreaders [25][26]; 2.1.4 +confidence-computation cost [27] (fact gate caught [27]
  misattribution - reframed simple-arithmetic as THESIS's own shortcut, not [27]'s method).
  All refs verified real. ch2 ~2760 -> ~3430 words (+~2pp). Total ~8730 body words, ~37-41pp.
- PAGE TRAJECTORY (honest): concise gate-verified prose accrues ~2pp per ~650 words. 50-by-ch3
  budget was optimistic. Decisive levers to 100 are VERTICALLY DENSE: ch4 prompt+code listings,
  ch5 figures/tables, appendices (full prompts + R0 tables). Next per Ashwin: FULL ch4.
- **+5pp PASS + DOC-READY (2026-08-10):** numerals standardized in ch3; SIR equations now a
  typeset image (fig_sir_equations); added Fig 3.2 (injection) + Fig 3.3 (pipeline) +
  Table 2.1 (related-work comparison); front matter added: Acknowledgement, List of Acronyms
  (17), List of Figures, List of Tables. docx now ~225 paras, 6 images, 7 tables, ~43-47pp.
  build script: add_kv_table helper; FIGURES/TABLES/ACRONYMS constants.
- **REVIEW-READY (2026-08-10):** German umlauts restored (ä/ö/ü/ß) in DE abstract + affidavit
  + heading; date set "August 2026"; updateFields=true in settings.xml so Word auto-fills the
  TOC page numbers on open. docx verified: umlauts present, date set, updateFields present.
  Submitting ch1-3 for professor review.
- (2) Optional native German proofread still advisable (affidavit is official SRH text = correct).
  (3) List of Figures/Tables are manual lists (captions, no page numbers) - fine for review.

## 2026-08-10 IN-PLACE FIXES + WORKFLOW CHANGE
- Ashwin hand-edited report.docx: section headers, Chandana->Chandna, added SRH logo, spacing,
  generated TOC. Section numbering was messed up (Heading 1/2/3 STYLES carried list numbering,
  so front/back matter auto-numbered 1-10 while chapters used typed numbers).
- Fixed IN PLACE (scripts/fix_report_inplace.py, NOT a rebuild - preserves logo/spacing/Chandna):
  stripped numPr from heading styles + 28 heading paras (chapters keep typed 1/1.1/2.1.1);
  applied the 5 German fidelity fixes + Fig 3.3 caption fix; swapped pipeline image (aspect
  preserved); Chandana->Chandna in Acknowledgement; updateFields=true. Verified: logo (7 media),
  6 images, 7 tables preserved. Backup: report_backup_pre_numbering.docx.
- **WORKFLOW CHANGE:** report.docx is now the HAND-FORMATTED MASTER. build_report_docx.py would
  OVERWRITE the logo/spacing, so do NOT rebuild over it. For ch4+, ADD to report.docx IN PLACE
  (python-docx append) to preserve formatting. Build script kept in sync (Chandna) for reference.
- USER ACTION: open report.docx in Word, let it Update Fields (or Ctrl+A then F9) so the TOC
  re-renders with corrected numbering (front/back matter unnumbered; chapters 1/2/3).
- **Deferred adds:** ch2 figures (SIR compartment diagram; message-chain vs shared-graph
  contagion schematic); front matter still needs Acknowledgements + List of Acronyms;
  plus the 5 report.docx to-dos (umlauts, LICENSE, Chandana spelling, date, TOC update).

## 2026-08-15 CH2 DEEP-DIVE WAVES (+8pp request, non-impl/non-results)
- Ashwin: "8 more pages before section 4, explain something in deep, not impl/results,
  through the agents, keep the style." Doing it as gated waves, edited into report.docx
  IN PLACE (never rebuilt), each with style + fact gates.
- WAVE A (integrate_waveA.py) DONE + gated: 2.1.1 +KG-construction/refinement/blackboard
  [28][29]; 2.1.4 +why/how/where provenance, probabilistic DBs, provenance semirings
  [30][31]. Fact gate caught D1 misattribution (simple arithmetic = thesis's own naive
  baseline, not [27]'s method) - reframed. Refs [28]-[31] added w/ DOIs, bookmarked, linked.
- WAVE B (integrate_waveB.py) DONE + gated: 2.1.2 +info-cascade bridge (Vosoughi false-news
  [32], simple vs complex contagion [33]) at end of 2.1.2; 2.1.3 +SIR assumptions (closed
  pop / homogeneous mixing / single infected state) + SEIR latent-period variant [34].
  Style gate fixes applied (2 vague-sourcing openers, 1 incomplete clause, hollow opener,
  "compartment"->"group" consistency, de-duped homogeneous-mixing restatement). Fact gate:
  all 3 citations VERIFIED w/ DOIs (aap9559 / 1185231 / 978-3-540-78911-6_2). Refs [32]-[34]
  added w/ DOIs, bookmarked ref32-34, in-text linked. Body now ~12,309 paragraph words.
- WAVES C/D/E DONE + gated (combined batch ch23_deepen_waveCDE.md, ONE style + ONE fact
  gate to save spend). Style gate: Wave C original E1/E2 was ~half DUPLICATE of the existing
  2.1.2 opener -> trimmed to ONE new paragraph (compounding/snowballing + no-truth-check +
  extraction risk, reuse [9]). Fact gate: 2 NEEDS-HEDGE, rest VERIFIED. (1) D-reach "low R0
  still reaches far if it runs long" only true under susceptible REPLENISHMENT (= this
  thesis's regime, ~50k facts, continual injection) not textbook closed final-size ->
  reframed. (2) USR "high-confidence node" didn't match ch3.7's actual overlap-based USR ->
  compression already dropped it. Confirmed 3.9 does NOT duplicate 3.8 (instruments vs
  assumptions/threats). Integrated (integrate_waveCDE.py):
    * 2.1.2 +compounding/no-truth-check paragraph (Wave C)
    * 2.1.3 +velocity-vs-reach (final size) + herd-immunity threshold 1-1/R0 (Wave D, [12])
    * NEW SECTION 3.9 "Assumptions, scope, and threats to validity" (Wave E, 7 paras, [16]):
      non-adversarial threat model / construct / internal / stats-treatment / external /
      reproducibility. Heading 2 (shows in TOC on update). No new refs; [9][12][16] linked.
- HONEST PAGE MATH: deepening added +2,281 body words total (A 686, B 418, CDE 1177) over
  pre-waveA 11,205 -> 13,486. At ~325 w/formatted page ~= +7 pages, ~1 short of the +8 ask.
  OPTIONAL Wave F to close gap: 2.1.1 RAG-failure-modes (retrieval returns wrong/contradictory
  context; models defer to retrieved context over own knowledge = the mechanism contamination
  exploits). Genuine background, non-impl/non-results. NOT done - offered to Ashwin, awaiting.
- USER ACTION after opening report.docx in Word: Ctrl+A then F9 to repopulate TOC (now
  includes 3.9). Backups: report_backup_pre_waveA/B/CDE.docx.

## Decisions locked (2026-08-09)

- Checker cadence: per subsection, then approve paragraph by paragraph.
- Start point: Chapter 1, reworking the existing pre-draft to the plain standard.
- Citation style: numbered [1].
- Originality: agent hygiene per paragraph now; Ashwin runs Turnitin at the end.
- ch1 section scheme switched to Binh Vu house style (Motivation / Problem Statement
  / Research Questions / Approach / Thesis Contribution / Thesis Outline).

## Note on existing drafts

The pre-draft chapters (ch1, parts of ch3/ch5, ch6 deviations) were written in the
old academic register (em-dashes, elevated vocabulary). They are source material,
not finished text. Each gets reworked through this pipeline. Old ch1 preserved as
reference until replaced.

## Approved so far

- ch1 §1.1 Motivation — COMPLETE, P1-P4 approved 2026-08-09. In ch1_introduction.md.
- ch1 §1.2 Problem Statement — COMPLETE, P1-P4 approved 2026-08-09.
- ch1 §1.3 Research Questions — COMPLETE, approved 2026-08-09 (Nair-style format:
  bold question + explanation below). Confirmed in line with exposé RQ1-RQ4.
- ch1 §1.4 Approach — drafted, gated (fact 6/6 MATCH; 5 style glosses applied), AWAITING APPROVAL.
- ch1 §1.5 Contribution — MINIMAL version (Ashwin chose defer-everything; matches
  Behrouzi intro). States 4 contributions, defers all findings to abstract + ch5. Keeps
  [5] for novelty differentiation; [6] no longer cited in ch1 (moves to ch2). Content is
  a strict reduction of already-gated claims. AWAITING APPROVAL.
- ch1 §1.4 Approach, §1.5 Contribution (minimal), §1.6 Outline — APPROVED 2026-08-09,
  in ch1_introduction.md + report.docx. CHAPTER 1 DONE.
- report.docx BUILT from SRH template (scripts/build_report_docx.py): title page,
  bilingual affidavit, EN abstract + DE Zusammenfassung, TOC field, ch1 (1.1-1.3),
  refs [1]-[4]. Re-run script after each newly approved section.

## 2026-08-16 reviewer-fix pass (Ch2/Ch3, up to 3.9 only)

External reviewer (codex) critique triaged. Verified via a Sonnet fact agent (citations)
and directly against code/config (numbers). Only clearly-true, in-scope (<= 3.9) fixes
were integrated IN PLACE into report.docx (backup: report_backup_pre_reviewerfixes.docx;
script scripts/integrate_reviewer_fixes.py; style-gated draft in
_working/ch3_reviewer_fixes.md). Body 13,486 -> 14,421 words.

Integrated:
- 3.3: all 3 error types injected together (45 index cases, config-confirmed), and
  confidence/lineage/state left untouched at injection (error_injector.py 16-20) ->
  connects to structural blindness (cascade can't reach a clean-ancestor index case).
- 3.6: run length stated in prose ("ten steps").
- 3.4: rate identifiability (only b-g from I-curve; g pinned by observed R) + R0 read as
  per-run summary not a constant.
- 3.7: Veracity Accuracy given same detail as EM/F1 (50 claims, steps 0/5/10); HotpotQA/
  FEVER now cited.
- 3.9: hosting reconciled with Table 3.1 (open-weight, small, but reached via hosted APIs;
  no more "no graphics card" contradiction); "held fixed for the whole study" -> "across
  the comparative arms" (removes contradiction with abstract's cross-family claim);
  two small-sample limits named (MW min p~0.03 at n=4; noise SD itself from n=4); RQ2
  measurement-asymmetry caveat; dataset/model licence sentence.
- 2.1.2: Zhang et al. snowballing [41] co-cited + one explanatory sentence (primary source
  for the compounding claim, previously only [9]).
- 2.2 + Table 2.1: Margalit [19] corrected from "proposed, not stress-tested" to
  "built and measured, not tested under spreading error" (verified: MemClaw/ArgusFleet
  claims are real, but it's a single non-peer-reviewed industry preprint - do not oversell).
- New refs [35]-[41] (T-REx, HotpotQA, FEVER, Neo4j, Mistral NeMo, Llama 3.1, Zhang),
  all fact-gate verified, bookmarked + external links.

HELD (not done this pass, by design):
- Ch5-dependent (4.1 oracle-full/audit-budget, 4.2 question-contamination overlap,
  4.3 abstract recall-vs-architectural reword) - Ch5 not yet in report.
- Ch2 restructure (split 2.2 into subsections; add Ju et al. 2407.07791, Gu et al. Agent
  Smith 2402.08567, Shen et al. EMNLP2025 2505.23352; a 2.3.3 convergent-evidence paragraph
  on Margalit's contradiction-gate). Needs paragraph-level approval (novelty-critical).
- 1.2 reframing the 0.95^10 opener toward the reachability threshold (argument reshaping).
- Liu companion paper arXiv:2606.23195 exists and is DISTINCT from [18] (2606.20493), but
  its "no safe threshold" is bias-type/model dependent - hedge if ever cited.

4.11 (3.8 human calibration) RESOLVED 2026-08-16: Ashwin confirms he labelled the 40 items
himself, no second rater. Correction is per-category/stratified, NOT flat and NOT IPW
(phase34_judge_calibration_summary.json line 22: 56*0.0 + 32*0.2 + 1 ~= 7.4/783 ~= 0.9%),
which pre-empts the reviewer's stratified-sample concern. Added a 3.8 paragraph disclosing
the single rater (no inter-rater agreement, wide margin) and describing the per-category
correction. (scripts/integrate_calib_note.py; backup report_backup_pre_calibnote.docx.)

USER ACTION: open report.docx, Ctrl+A then F9 to update the TOC (and REF-field citations).

## 2026-08-16 (later) - §1.2 reframe + Ch2 restructure

- §1.2: replaced the self-undercutting 0.95^10 opener with a tightened hook that pivots to
  the reachability-threshold + reinforcement mechanism the thesis actually studies (option 3).
  Style-gated. (scripts/integrate_ch1_reframe.py; backup report_backup_pre_ch1reframe.docx.)
- §2.2 restructured into 2.2.1 Attacks on agent memory / 2.2.2 Models of how errors spread /
  2.2.3 Attempts to contain the spread (mirrors 2.3.1-2.3.3). Added Ju et al. [42] (2.2.1),
  Gu et al. Agent Smith [43] + Shen et al. [44] (2.2.2). Old 4 §2.2 paragraphs removed, no
  dup. Added a convergent-evidence paragraph to §2.3.3 on Margalit's dedup-starves-
  contradiction result, explicitly flagged "not yet peer reviewed and not independently
  reproduced." Refs [42]-[44] verified (fact+originality gate: all TRUE; Gu softened to
  "roughly a million"; Margalit sentence reworded off the source). Ashwin approved after a
  novelty check (none of the three do the non-adversarial fact-level KG cascade + SIR/Trio;
  they surround and support; Shen closest so cite-and-distinguish via existing 2.3.2).
  (scripts/integrate_ch2_restructure.py; backup report_backup_pre_ch2restructure.docx.)
- Body now ~15,139 words. USER ACTION: Ctrl+A then F9 in Word to refresh TOC + fields.

HELD still: Ch5-dependent reviewer items (4.1 oracle-full, 4.2 decoupling overlap, 4.3
abstract reword) - wait until Chapter 5 is in the report.

## report.docx TO-DO (before submission)
- German abstract/affidavit currently use ae/oe/ue/ss transliteration; restore real
  umlauts and get a native/fluent proofread.
- Verify supervisor spelling: exposE + CLAUDE.md say "Swati Chandana"; Behrouzi thesis
  says "Swati Chandna". Confirm which is correct.
- Add a LICENSE + confirm repo is public before 1.5 P5 "prepared for open release" ships.
- Set the real submission date (placeholder "September 2026").
- In Word, right-click the Table of Contents and Update Field (F9) to populate it.

## Open [VERIFY] items

- refs [1]-[4] verified real, author lists corrected.
- PRIOR-WORK ALERT (see prior_work_watch.md): 2026 papers overlap the novelty claim.
  Niu et al. 2607.21912 (SEIC contagion over LLM agent networks) and Jamshidi et al.
  2606.07937 (hallucination cascade) VERIFIED real. Three more reported, TO VERIFY.
  Impact: soften 1.5 Contributions #1 (no outright epidemiology-first claim); ch2 must
  differentiate. Our distinct ground: contagion at the KG-NODE level in shared memory,
  plus Trio provenance mitigation and the structural-blindness result.

## Running page estimate

- Target: >= 100 pages. Current approved body text: 1 paragraph (~0.15 pp).
- Rough per-chapter aim: ch2 ~22-30 pp, ch3 ~15-20, ch4 ~12-18, ch5 ~20-28,
  ch1/ch6/ch7 the remainder.
