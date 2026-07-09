"""
Task #19 — false-claim ingestion rate (the truth channel), token-free.

The natural audit (task #9) measured FIDELITY: is a triplet faithful to its
source passage? The judge calibration (task #17) showed the complementary
channel it cannot see: FEVER claims that are world-FALSE but faithfully
extracted enter the KG as facts and count as SUPPORTED. FEVER ships
ground-truth verdicts (SUPPORTS / REFUTES / NOT ENOUGH INFO), so this channel
can be measured exactly, with zero LLM calls:

  1. Replay the same extraction manifest the natural audit used.
  2. Map every FEVER-derived triplet to its claim's FEVER verdict.
  3. Count triplets extracted from REFUTED claims (known-false content in the
     KG) and from NEI claims (unverifiable content in the KG).

Counting note: a REFUTED claim can contain true sub-facts (e.g. "Aarhus is
located south of London" — the entity is real, the relation is the false
part), so triplets-from-REFUTED-claims is an UPPER bound on false triplets;
one claim-core triplet per REFUTED unit is the natural lower bound.

Run from project root (no Neo4j, no LLM):
    python scripts/analyze_truth_channel.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from audit_natural import contaminated_ids, load_jsonl  # noqa: E402

# Same manifest pair as the task #9 natural audit — keeps the triplet
# population identical to the audited 783.
EXTRACTION_MANIFEST = ROOT / "results" / "raw" / "extraction_both_20260707_173140.csv"
CONTAM_MANIFEST = ROOT / "results" / "raw" / "contamination_baseline_s45_20260707_173142_manifest.json"
AUDIT_CSV = ROOT / "results" / "summaries" / "phase34_natural_audit.csv"
SUMM = ROOT / "results" / "summaries"

VERDICTS = ("SUPPORTS", "REFUTES", "NOT ENOUGH INFO")


def main() -> None:
    fever_labels = {d["id"]: d.get("label", "").strip().upper()
                    for d in load_jsonl(ROOT / "data" / "processed" / "fever.jsonl")}
    audit = {r["triplet_id"]: r for r in csv.DictReader(open(AUDIT_CSV, encoding="utf-8"))}
    excluded = contaminated_ids(CONTAM_MANIFEST)

    unit_counts = {v: 0 for v in VERDICTS}
    units_with_triplets = {v: 0 for v in VERDICTS}
    triplet_counts = {v: 0 for v in VERDICTS}
    rows_out, n_excluded, n_unknown = [], 0, 0
    total_triplets = 0

    with open(EXTRACTION_MANIFEST, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tids = [t for t in row["triplet_ids"].split(";") if t]
            if row["dataset"] != "fever":
                total_triplets += sum(1 for t in tids if t not in excluded)
                continue
            fid = int(row["unit_id"].removeprefix("fever_"))
            verdict = fever_labels.get(fid, "")
            if verdict not in VERDICTS:
                n_unknown += 1
                continue
            unit_counts[verdict] += 1
            if any(t not in excluded for t in tids):
                units_with_triplets[verdict] += 1
            for tid in tids:
                if tid in excluded:
                    n_excluded += 1
                    continue
                total_triplets += 1
                triplet_counts[verdict] += 1
                a = audit.get(tid, {})
                rows_out.append({
                    "triplet_id": tid, "fever_id": fid, "verdict": verdict,
                    "subject": a.get("subject", ""), "predicate": a.get("predicate", ""),
                    "object": a.get("object", ""), "fidelity_judge_label": a.get("label", ""),
                })

    fever_total = sum(triplet_counts.values())
    summary = {
        "population": "same as natural audit (extraction_both_20260707_173140, gt-contaminated excluded)",
        "fever_units_extracted": unit_counts,
        "fever_triplets_in_kg": triplet_counts,
        "fever_triplets_total": fever_total,
        "refuted_triplet_share_of_fever": round(triplet_counts["REFUTES"] / fever_total, 4) if fever_total else None,
        "refuted_plus_nei_share_of_fever": round(
            (triplet_counts["REFUTES"] + triplet_counts["NOT ENOUGH INFO"]) / fever_total, 4) if fever_total else None,
        "refuted_triplet_share_of_all_extraction_triplets": round(
            triplet_counts["REFUTES"] / total_triplets, 4) if total_triplets else None,
        "all_extraction_triplets": total_triplets,
        "false_triplet_bounds": {
            "upper_bound_triplets_from_refuted_claims": triplet_counts["REFUTES"],
            "lower_bound_refuted_units_with_at_least_one_triplet": units_with_triplets["REFUTES"],
        },
        "units_yielding_any_triplet": units_with_triplets,
        "triplets_per_unit_by_verdict": {
            v: round(triplet_counts[v] / unit_counts[v], 2) if unit_counts[v] else None
            for v in VERDICTS
        },
        "gt_contaminated_excluded": n_excluded,
        "units_without_fever_label": n_unknown,
    }

    # Extractor self-censoring check: do REFUTED claims yield triplets less
    # often than SUPPORTS/NEI claims? (Fisher exact on units yielding >=1.)
    from scipy.stats import fisher_exact
    ref_yes = units_with_triplets["REFUTES"]
    ref_no = unit_counts["REFUTES"] - ref_yes
    oth_yes = sum(units_with_triplets[v] for v in VERDICTS) - ref_yes
    oth_no = sum(unit_counts[v] for v in VERDICTS) - unit_counts["REFUTES"] - oth_yes
    odds, p = fisher_exact([[ref_yes, ref_no], [oth_yes, oth_no]])
    summary["extractor_self_censoring"] = {
        "refuted_units_yielding": f"{ref_yes}/{unit_counts['REFUTES']}",
        "other_units_yielding": f"{oth_yes}/{sum(unit_counts.values()) - unit_counts['REFUTES']}",
        "fisher_exact_p": round(p, 4),
        "odds_ratio": round(odds, 3),
    }

    out_csv = SUMM / "phase34_truth_channel.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
        w.writeheader()
        w.writerows(sorted(rows_out, key=lambda r: (r["verdict"], r["fever_id"])))

    with open(SUMM / "phase34_truth_channel_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(json.dumps(summary, indent=2))
    print(f"\nPer-triplet rows -> {out_csv}")


if __name__ == "__main__":
    main()
