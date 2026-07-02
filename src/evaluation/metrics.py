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
# USR — Unsupported Sentence Ratio
# ---------------------------------------------------------------------------

def unsupported_ratio(supported_flags: list[bool]) -> float:
    """
    Share of answer statements NOT supported by a high-confidence KG fact.

    The caller determines support per statement (e.g. entity+predicate match
    against retrieved facts above the confidence floor); this just aggregates.
    """
    if not supported_flags:
        return 0.0
    return sum(1 for s in supported_flags if not s) / len(supported_flags)
