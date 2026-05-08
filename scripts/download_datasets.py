"""
Download T-REx, HotpotQA, and FEVER datasets into data/raw/.

Run from project root with venv active:
    python scripts/download_datasets.py
"""

import json
import os
import sys
from pathlib import Path

from datasets import load_dataset
from loguru import logger


ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{message}</level>")


def save_jsonl(records, path: Path) -> int:
    with open(path, "w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path.stat().st_size


# ---------------------------------------------------------------------------
# T-REx  (via relbert/t_rex raw JSONL — bypasses loading script)
# Downloads the train JSONL directly from HuggingFace Hub file storage.
# We cap at MAX_TREX_RECORDS for Phase 1 (50K is ample for SIR modelling).
# ---------------------------------------------------------------------------
MAX_TREX_RECORDS = 50_000


def download_trex() -> None:
    out_path = RAW_DIR / "trex.jsonl"
    if out_path.exists():
        logger.info(f"T-REx already downloaded ({out_path}). Skipping.")
        return

    logger.info(f"Downloading T-REx raw JSONL from HuggingFace Hub (first {MAX_TREX_RECORDS:,} records)...")
    try:
        from huggingface_hub import hf_hub_download
        cached = hf_hub_download(
            repo_id="relbert/t_rex",
            filename="data/t_rex.filter_unified.min_entity_5.train.jsonl",
            repo_type="dataset",
        )
    except Exception as e:
        logger.error(f"Failed to download T-REx: {e}")
        return

    count = 0
    with open(cached, encoding="utf-8") as src, open(out_path, "w", encoding="utf-8") as dst:
        for line in src:
            if not line.strip():
                continue
            dst.write(line)
            count += 1
            if count >= MAX_TREX_RECORDS:
                break

    size = out_path.stat().st_size
    logger.success(f"T-REx saved: {count:,} triples → {out_path} ({size / 1e6:.1f} MB)")


# ---------------------------------------------------------------------------
# HotpotQA  (distractor setting — multi-hop Q&A with 10 context paragraphs)
# We use the validation split for evaluation (dev set is public; test is hidden).
# ---------------------------------------------------------------------------
def download_hotpotqa() -> None:
    train_path = RAW_DIR / "hotpotqa_train.jsonl"
    val_path = RAW_DIR / "hotpotqa_validation.jsonl"

    if train_path.exists() and val_path.exists():
        logger.info("HotpotQA already downloaded. Skipping.")
        return

    logger.info("Downloading HotpotQA (distractor setting)...")
    try:
        ds = load_dataset("hotpot_qa", "distractor")
    except Exception as e:
        logger.error(f"Failed to load HotpotQA: {e}")
        return

    for split_name, out_path in [("train", train_path), ("validation", val_path)]:
        if split_name not in ds:
            logger.warning(f"Split '{split_name}' not found in HotpotQA.")
            continue
        records = list(ds[split_name])
        size = save_jsonl(records, out_path)
        logger.success(
            f"HotpotQA {split_name}: {len(records):,} examples → {out_path} ({size / 1e6:.1f} MB)"
        )


# ---------------------------------------------------------------------------
# FEVER  (via copenlu/fever_gold_evidence — Parquet, no loading script)
# Labels: SUPPORTS, REFUTES, NOT ENOUGH INFO
# Gold evidence version: each claim already has evidence sentences attached.
# ---------------------------------------------------------------------------
def download_fever() -> None:
    train_path = RAW_DIR / "fever_train.jsonl"
    dev_path = RAW_DIR / "fever_dev.jsonl"

    if train_path.exists() and dev_path.exists():
        logger.info("FEVER already downloaded. Skipping.")
        return

    logger.info("Downloading FEVER (copenlu/fever_gold_evidence)...")
    try:
        ds = load_dataset("copenlu/fever_gold_evidence")
    except Exception as e:
        logger.error(f"Failed to load FEVER: {e}")
        return

    split_map = {
        "train": train_path,
        "validation": dev_path,
    }

    for split_name, out_path in split_map.items():
        if split_name in ds:
            records = list(ds[split_name])
            size = save_jsonl(records, out_path)
            logger.success(
                f"FEVER {split_name}: {len(records):,} examples → {out_path} ({size / 1e6:.1f} MB)"
            )


def print_summary() -> None:
    logger.info("\n--- Download Summary ---")
    for fname in sorted(RAW_DIR.glob("*.jsonl")):
        n_lines = sum(1 for _ in open(fname, encoding="utf-8"))
        size_mb = fname.stat().st_size / 1e6
        logger.info(f"  {fname.name:<35} {n_lines:>8,} records   {size_mb:>6.1f} MB")


if __name__ == "__main__":
    logger.info(f"Saving raw datasets to: {RAW_DIR}")
    download_trex()
    download_hotpotqa()
    download_fever()
    print_summary()
    logger.success("Done. Run `python scripts/preprocess_datasets.py` next.")
