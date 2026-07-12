"""
Evaluation metrics for the contamination experiments.

Task performance:
  - exact_match / token_f1   — HotpotQA answers (SQuAD-style normalization)
  - veracity_report          — FEVER claim classification accuracy + confusion

Epidemiological:
  - detection_auroc          — can the system's confidence scores separate
                               ground-truth-contaminated nodes (error_type set)
                               from clean ones?

Provenance:
  - unsupported_ratio        — share of answer statements not traceable to a
                               high-confidence KG fact (USR)

All functions are pure — no LLM or DB access — so they are unit-testable
and reusable across baseline and mitigated runs.
"""

from __future__ import annotations

import re
import string
from collections import Counter


# ---------------------------------------------------------------------------
# HotpotQA — Exact Match / F1 (SQuAD-style normalization)
# ---------------------------------------------------------------------------

def normalize_answer(s: str) -> str:
    """Lowercase, strip articles, punctuation, and extra whitespace."""
    s = s.lower()
    s = re.sub(r"\b(a|an|the)\b", " ", s)
    s = "".join(ch for ch in s if ch not in string.punctuation)
    return " ".join(s.split())


def exact_match(prediction: str, gold: str) -> int:
    """1 if normalized prediction equals normalized gold, else 0."""
    return int(normalize_answer(prediction) == normalize_answer(gold))


def token_f1(prediction: str, gold: str) -> float:
    """Token-overlap F1 between normalized prediction and gold."""
    pred_tokens = normalize_answer(prediction).split()
    gold_tokens = normalize_answer(gold).split()
    if not pred_tokens or not gold_tokens:
        return float(pred_tokens == gold_tokens)
    common = Counter(pred_tokens) & Counter(gold_tokens)
    num_same = sum(common.values())
    if num_same == 0:
        return 0.0
    precision = num_same / len(pred_tokens)
    recall = num_same / len(gold_tokens)
    return 2 * precision * recall / (precision + recall)


# ---------------------------------------------------------------------------
# FEVER — Veracity Accuracy
# ---------------------------------------------------------------------------

FEVER_LABELS = ("SUPPORTS", "REFUTES", "NOT ENOUGH INFO")


def veracity_report(predictions: list[str], golds: list[str]) -> dict:
    """Accuracy plus per-label counts and a confusion table."""
    assert len(predictions) == len(golds), "prediction/gold length mismatch"
    correct = 0
    confusion: dict[str, Counter] = {label: Counter() for label in FEVER_LABELS}
    for pred, gold in zip(predictions, golds):
        pred = pred if pred in FEVER_LABELS else "NOT ENOUGH INFO"
        if pred == gold:
            correct += 1
        if gold in confusion:
            confusion[gold][pred] += 1
    n = len(golds)
    return {
        "n":         n,
        "accuracy":  correct / n if n else 0.0,
        "confusion": {g: dict(c) for g, c in confusion.items()},
    }


# ---------------------------------------------------------------------------
# Detection AUROC — ground truth (error_type) vs detection signal
# ---------------------------------------------------------------------------

def detection_auroc(is_contaminated: list[int], suspicion_scores: list[float]) -> float:
    """
    AUROC of a suspicion score at separating contaminated from clean nodes.

    is_contaminated: 1 if the node has ground-truth error_type set, else 0.
    suspicion_scores: higher = more suspicious (use 1 - confidence).

    Returns 0.5 when only one class is present (AUROC undefined).
    """
    if len(set(is_contaminated)) < 2:
        return 0.5
    from sklearn.metrics import roc_auc_score
    return float(roc_auc_score(is_contaminated, suspicion_scores))


# ---------------------------------------------------------------------------
# USR — Unsupported Sentence Ratio (task #16, decided 2026-07-11)
#
# Fully mechanical — string/entity overlap only, no LLM judge anywhere. The
# judge calibration (task #17) measured the 8B judge at 10% flag precision,
# which disqualifies LLM judgement for a metric that must stay trustworthy
# while the validators themselves are under study. Deterministic and
# token-free by design; the lexical crudeness (string overlap is not
# semantic support) is a documented limitation.
#
# Two grain sizes:
#   sentence_usr()     — sentence-level, for multi-sentence text: a sentence
#                        is supported if some retrieved fact has BOTH its
#                        endpoints (subject and object) named in it, i.e. the
#                        sentence connects entities the KG connects.
#   answer_traceable() — span-level, for the QA path's short answers (the
#                        _QA_SYSTEM prompt requests "a few words at most", so
#                        an answer IS the sentence): the span is traceable if
#                        it appears inside some retrieved fact's subject/
#                        object/predicate, or one of those appears inside it.
#
# USR measures GROUNDING, not truth: an answer that faithfully reproduces a
# retrieved contaminated fact is traceable. That is intentional — the truth
# channel (task #19) showed grounding and truth are independent axes, and
# this metric owns the grounding axis (RQ4: does mitigation preserve answer
# support while filtering retrieval?).
# ---------------------------------------------------------------------------

# Answers with no entity content to ground: abstentions and bare booleans.
NON_GROUNDABLE_ANSWERS = frozenset({"", "unknown", "yes", "no"})

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _norm_ground(s: str) -> str:
    """Normalization for grounding comparisons: lowercase, snake_case → words,
    punctuation stripped, whitespace collapsed."""
    s = s.replace("_", " ").lower()
    s = "".join(ch if ch not in string.punctuation else " " for ch in s)
    return " ".join(s.split())


def _contains(haystack_norm: str, needle_norm: str) -> bool:
    """Word-boundary containment between two already-normalized strings."""
    if not needle_norm:
        return False
    return re.search(rf"\b{re.escape(needle_norm)}\b", haystack_norm) is not None


# Common abbreviations whose trailing period must not end a sentence.
_ABBREVIATIONS = ("co.", "inc.", "ltd.", "corp.", "mr.", "mrs.", "ms.", "dr.",
                  "st.", "jr.", "sr.", "no.", "u.s.", "u.k.", "vs.")


def split_sentences(text: str) -> list[str]:
    parts = [s.strip() for s in _SENTENCE_SPLIT.split(text or "") if s.strip()]
    merged: list[str] = []
    for part in parts:
        if merged and merged[-1].lower().endswith(_ABBREVIATIONS):
            merged[-1] = f"{merged[-1]} {part}"
        else:
            merged.append(part)
    return merged


def sentence_supported(sentence: str, facts: list[dict]) -> bool:
    """True if some retrieved fact has both endpoints named in the sentence."""
    sent = _norm_ground(sentence)
    for f in facts:
        subj, obj = _norm_ground(f["subject"]), _norm_ground(f["object"])
        if subj and obj and _contains(sent, subj) and _contains(sent, obj):
            return True
    return False


def sentence_usr(text: str, facts: list[dict]) -> dict:
    """Sentence-level USR over a multi-sentence text.

    Returns {"n_sentences", "n_unsupported", "usr"}; usr is None for empty
    text (nothing to grade — callers must not coerce that to 0.0).
    """
    sentences = split_sentences(text)
    flags = [sentence_supported(s, facts) for s in sentences]
    return {
        "n_sentences":   len(sentences),
        "n_unsupported": sum(1 for ok in flags if not ok),
        "usr":           unsupported_ratio(flags) if sentences else None,
    }


def answer_traceable(answer: str, facts: list[dict]) -> bool | None:
    """Span-level grounding for short QA answers.

    None  — non-groundable (abstention/boolean): excluded from USR.
    True  — the span appears in a retrieved fact (or a fact field in it).
    False — no retrieved fact accounts for the span: unsupported.
    """
    ans = _norm_ground(answer)
    if ans in NON_GROUNDABLE_ANSWERS:
        return None
    for f in facts:
        for field in ("subject", "object", "predicate"):
            val = _norm_ground(str(f.get(field, "")))
            if _contains(val, ans) or _contains(ans, val):
                return True
    return False


def unsupported_ratio(supported_flags: list[bool]) -> float:
    """
    Share of answer statements NOT supported by a high-confidence KG fact.

    The caller determines support per statement (e.g. entity+predicate match
    against retrieved facts above the confidence floor); this just aggregates.
    """
    if not supported_flags:
        return 0.0
    return sum(1 for s in supported_flags if not s) / len(supported_flags)
