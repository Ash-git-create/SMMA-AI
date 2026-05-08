"""
Verify that the full local stack is operational.

Run from project root with venv active:
    python scripts/verify_setup.py

Checks:
  1. Required Python packages installed
  2. .env file present and readable
  3. LLM API connections (Mistral + Groq)
  4. Neo4j reachable + authenticated
  5. Processed dataset files present
"""

import importlib
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}")

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"

results = []


def check(label: str, status: str, detail: str = "") -> None:
    icon = {"PASS": "✓", "FAIL": "✗", "WARN": "!"}.get(status, "?")
    color = {"PASS": "green", "FAIL": "red", "WARN": "yellow"}.get(status, "white")
    msg = f"[{icon}] {label}"
    if detail:
        msg += f"  —  {detail}"
    getattr(logger, {"PASS": "success", "FAIL": "error", "WARN": "warning"}[status])(msg)
    results.append((label, status))


# ---------------------------------------------------------------------------
# 1. Python packages
# ---------------------------------------------------------------------------
REQUIRED_PACKAGES = ["neo4j", "mistralai", "groq", "datasets", "pandas", "numpy",
                     "sklearn", "evaluate", "loguru", "dotenv", "yaml"]

for pkg in REQUIRED_PACKAGES:
    mod = "sklearn" if pkg == "sklearn" else ("dotenv" if pkg == "dotenv" else pkg)
    try:
        importlib.import_module(mod)
        check(f"Package: {pkg}", PASS)
    except ImportError:
        check(f"Package: {pkg}", FAIL, "run: pip install -r requirements.txt")


# ---------------------------------------------------------------------------
# 2. .env file
# ---------------------------------------------------------------------------
env_path = ROOT / ".env"
if env_path.exists():
    check(".env file", PASS, str(env_path))
else:
    check(".env file", FAIL, "Copy .env.example to .env and fill in your values")


# ---------------------------------------------------------------------------
# 3. LLM API connectivity
# ---------------------------------------------------------------------------
sys.path.insert(0, str(ROOT))
try:
    from src.agents.llm_client import get_client, ModelRole
    for role, label in [(ModelRole.EXTRACTION, "Extraction (Mistral Nemo)"),
                        (ModelRole.ORCHESTRATION, "Orchestration (Llama 3.1 8B)")]:
        try:
            client = get_client(role)
            resp = client.chat("Reply with only the word OK.")
            if "ok" in resp.content.strip().lower():
                check(f"LLM API: {label}", PASS, f"{client.provider} / {client.model}")
            else:
                check(f"LLM API: {label}", WARN, f"Unexpected response: {resp.content.strip()[:60]}")
        except Exception as e:
            check(f"LLM API: {label}", FAIL, str(e))
except ImportError as e:
    check("LLM API clients", FAIL, str(e))


# ---------------------------------------------------------------------------
# 4. Neo4j connectivity
# ---------------------------------------------------------------------------
try:
    from neo4j import GraphDatabase
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USERNAME", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    driver.verify_connectivity()
    driver.close()
    check("Neo4j connection", PASS, uri)
except Exception as e:
    check("Neo4j connection", FAIL, str(e))


# ---------------------------------------------------------------------------
# 5. Processed dataset files
# ---------------------------------------------------------------------------
PROC_DIR = ROOT / "data" / "processed"
expected_files = ["trex_triplets.jsonl", "hotpotqa.jsonl", "fever.jsonl"]
for fname in expected_files:
    fpath = PROC_DIR / fname
    if fpath.exists():
        n = sum(1 for _ in open(fpath, encoding="utf-8"))
        check(f"Dataset: {fname}", PASS, f"{n:,} records")
    else:
        check(f"Dataset: {fname}", WARN, "Run scripts/preprocess_datasets.py first")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
logger.info("\n--- Verification Summary ---")
passed = sum(1 for _, s in results if s == PASS)
warned = sum(1 for _, s in results if s == WARN)
failed = sum(1 for _, s in results if s == FAIL)
logger.info(f"  PASS: {passed}  WARN: {warned}  FAIL: {failed}  TOTAL: {len(results)}")

if failed > 0:
    logger.error("Setup incomplete — fix the FAIL items above before proceeding.")
    sys.exit(1)
elif warned > 0:
    logger.warning("Setup mostly complete — review WARN items above.")
else:
    logger.success("All checks passed. Environment is ready.")
