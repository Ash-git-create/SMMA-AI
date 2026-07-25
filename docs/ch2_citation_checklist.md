# ch2 Citation Verification Checklist

Purpose: confirm every reference in `docs/chapters/ch2_literature_review.md` is
real and its metadata (authors, year, venue, volume/pages, arXiv ID) is correct,
before ch2 is treated as final. Ordered by **fabrication risk** — do Tier 1
first.

Status key: ✅ web-verified (earlier session) · 🔴 unverified, high risk ·
🟡 unverified, low risk (established work — metadata check only).

---

## Tier 1 — Recent 2026 arXiv preprints (HIGHEST RISK: post-Jan-2026 cutoff, few-author, arXiv-only)

These cannot be confirmed from model training knowledge (they postdate the
cutoff) and are the classic fabrication-risk profile. **Open each arXiv URL and
confirm: (a) the page loads to a real paper, (b) title matches, (c) author list
matches, (d) it actually says what ch2 claims it says.**

| # | Citation | arXiv | Status | What to confirm |
|---|---|---|---|---|
| 1 | Lin et al. (2026), *Survey on Long-Term Memory Security in LLM Agents* | 2604.16548 | 🔴 | Page exists; title + 8-author list match; that it surveys memory-lifecycle attacks/defenses as ch2 §2.2 claims. Also flagged inline with `[REVIEW]` (line ~125). |
| 2 | Luo et al. (2026), *Survey on the Evolution of LLM Agent Memory* | 2605.06716 | 🔴 | Page exists; title + author list; that it frames private-vs-shared memory as ch2 §2.1 attributes ("Luo et al., 2026"). |
| 3 | Xie et al. (2026), *From Spark to Fire: Error Cascades in LLM Multi-Agent Collaboration* | 2603.04474 | 🔴 | Page exists; title + 8-author list; that it models propagation dynamics + message-layer governance (ch2 §2.3 + comparison table row). **This is the closest prior work — verify carefully.** |

## Tier 1b — Already web-verified (earlier session; re-spot-check only if time)

| # | Citation | arXiv | Status |
|---|---|---|---|
| 4 | Chu (2026), *Systematic Survey of Security Threats… Layered Attack Surface* | 2604.23338 | ✅ (also `[REVIEW]`-flagged line ~125) |
| 5 | Dong et al. (2025/2026), *MINJA: Memory Injection Attacks* (NeurIPS 2025) | 2503.03704 | ✅ |
| 6 | Jamshidi et al. (2026), *Hallucination Cascade* | 2606.07937 | ✅ |
| 7 | Wang (2026), *Epidemiology of Model Collapse (Bilayer SIR)* | 2606.05168 | ✅ |

---

## Tier 2 — Recent but likely real (pre/near cutoff; verify venue)

| # | Citation | ID | Status | What to confirm |
|---|---|---|---|---|
| 8 | Zou et al. (2024/2025), *PoisonedRAG* | arXiv 2402.07867 | 🟡 | Real & well-known. Confirm the USENIX Security 2025 venue attribution (arXiv is 2024) and the ID 2402.07867. |
| 9 | Shumailov et al. (2023), *Curse of Recursion* | arXiv 2305.17493 | 🟡 | Real & famous. ID correct. Note: a *Nature* 2024 version exists ("AI models collapse when trained on recursively generated data") — decide whether to cite the preprint or the Nature paper. |
| 10 | Zheng et al. (2023), *Judging LLM-as-a-Judge (MT-Bench / Chatbot Arena)* | NeurIPS 2023 D&B | 🟡 | Real & famous. Confirm NeurIPS 2023 Datasets & Benchmarks track + the self-preference/family-bias claim ch2 §2.x attributes to it. |
| 11 | Govindankutty & Gopalan (2024), *Epidemic modeling for misinformation…* | *Sci. Reports* 14 | 🟡 | Less well-known — confirm it exists, the Scientific Reports 2024 venue, and the article number. |
| 12 | Liu et al. (2023), *Error Detection on KGs with Triple Embedding* | EUSIPCO 2023 | 🟡 | Confirm EUSIPCO 2023 + IEEE Xplore doc 10289852. |

---

## Tier 3 — Established classics (LOW risk; metadata check only)

Real, canonical works. Only verify **year / volume / pages** are exactly right —
these are the details reviewers spot-check.

| # | Citation | Confirm |
|---|---|---|
| 13 | Kermack & McKendrick (1927), *Contribution to the Mathematical Theory of Epidemics* | *Proc. R. Soc. London A*, **115(772), 700–721**. (Foundational SIR paper.) |
| 14 | Daley & Kendall (1964), *Epidemics and Rumours* | *Nature*, **204, 1118**. (One-page note — confirm the single page.) |
| 15 | Widom (2005), *Trio: … Data, Accuracy, and Lineage* | CIDR 2005, Asilomar. (Stanford ilpubs 843.) |
| 16 | Agrawal et al. (2006), *Trio: A System for Data, Uncertainty, and Lineage* | VLDB 2006, Seoul. |
| 17 | Benjelloun et al. (2008), *Databases with uncertainty and lineage* (ULDB) | *VLDB Journal*, **17(2), 243–264**. |
| 18 | Green, Karvounarakis & Tannen (2007), *Provenance Semirings* | PODS 2007, Beijing. (Canonical provenance-semiring paper.) |
| 19 | Hayes-Roth (1985), *A blackboard architecture for control* | *Artificial Intelligence*, **26(3), 251–321**. |
| 20 | Paulheim (2017), *Knowledge graph refinement: a survey* | *Semantic Web*, **8(3), 489–508**. |

---

## Also resolve before ch2 is final

- **`[REVIEW]` markers** in the body (grep `\[REVIEW\]` in ch2) — at least one at
  line ~125 flagging Chu 2026 / Lin et al. 2026 as thin single/few-author
  preprints. Decide: keep with a hedge, or lean on the peer-reviewed anchors
  (MINJA-NeurIPS, PoisonedRAG-USENIX, Shumailov-Nature) for the load-bearing
  claims and demote the surveys to supporting cites.
- **Comparison table (lines ~411–419)** — every row cites a Tier-1/2 work; make
  sure each row's yes/no claims are actually supported by that paper (this is
  where an over-claim would hide).
- **Dual-venue citations** (Dong "NeurIPS 2025; arXiv", Zou "USENIX 2025; arXiv")
  — cite the peer-reviewed venue as primary, arXiv as secondary.

## Suggested workflow
1. Tier 1 (#1–3): open the three arXiv URLs, confirm existence + claim. ~15 min.
2. Tier 2 (#8–12): confirm the five venues. ~15 min.
3. Tier 3 (#13–20): metadata spot-check against the DOIs/URLs already in the
   reference list. ~15 min.
4. Resolve `[REVIEW]` markers + audit the comparison table. Your scholarly call.
