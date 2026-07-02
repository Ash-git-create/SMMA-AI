# Environment Setup Guide

Complete setup for the SMMA-AI Systems thesis project on Windows 11.

---

## Prerequisites

- Python 3.11+ (verify: `python --version`)
- Git (already done)
- ~15GB free disk space (models + datasets)

---

## Step 1 — Python Virtual Environment

Run from the project root (`D:\Master Thesis\SMMA_AI_Systems`):

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

> If `Activate.ps1` is blocked by execution policy, run:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`

Verify the install:
```powershell
python -c "import neo4j, mistralai, groq, datasets, pandas; print('All core packages OK')"
```

---

## Step 2 — LLM API Keys (Mistral + Groq)

The pipeline calls hosted APIs by default — local CPU inference proved too slow
(~3–5 tok/s for Mistral 12B) for experiment-scale runs.

1. **Mistral La Plateforme** (extraction — Mistral Nemo):
   - Create an account at https://console.mistral.ai
   - Generate an API key under *API Keys*
2. **Groq** (orchestration/validation — Llama 3.1 8B):
   - Create an account at https://console.groq.com
   - Generate an API key under *API Keys*
3. Both keys go into `.env` (Step 4).

> **Optional local fallback — Ollama:** for offline development you can install
> Ollama (https://ollama.com/download), `ollama pull mistral-nemo` and
> `ollama pull llama3.1:8b`, then set `EXTRACTION_PROVIDER=ollama` /
> `ORCHESTRATION_PROVIDER=ollama` in `.env`. Expect ~3–5 tok/s on this CPU —
> fine for smoke tests, not for experiments.

---

## Step 3 — Neo4j Community Edition

1. Download Neo4j Desktop or Neo4j Community Server 5.x from https://neo4j.com/download/
2. Recommended: **Neo4j Desktop** (easiest on Windows — GUI + one-click start)
3. Create a new project and database in Neo4j Desktop
4. Set a password for the `neo4j` user
5. Start the database
6. Verify it's running by opening http://localhost:7474 in your browser

Default connection settings (used in `.env`):
- URI: `bolt://localhost:7687`
- Username: `neo4j`
- Password: whatever you set

---

## Step 4 — Project Configuration

Copy `.env.example` to `.env` and fill in your values:

```powershell
Copy-Item .env.example .env
```

Then edit `.env` and set at minimum:
- `NEO4J_PASSWORD` — from Step 3
- `MISTRAL_API_KEY` and `GROQ_API_KEY` — from Step 2

Reproducibility settings (`LLM_TEMPERATURE=0.0`, `LLM_LOG_FILE`, `LLM_CACHE_DIR`)
have sensible defaults in `.env.example` — keep them for experiment runs.

---

## Step 5 — Download Datasets

With venv active and `.env` configured:

```powershell
python scripts/download_datasets.py
```

This downloads T-REx (via LAMA), HotpotQA (distractor split), and FEVER (v1.0) into `data/raw/`.
Expected size: ~2–4GB. Requires internet connection.

---

## Step 6 — Preprocess Datasets

```powershell
python scripts/preprocess_datasets.py
```

This normalizes all three datasets into unified JSONL files in `data/processed/`.

---

## Step 7 — Verify Full Stack

```powershell
python scripts/verify_setup.py
```

This checks: venv packages, Mistral/Groq API connectivity, Neo4j connectivity, and processed dataset files.

---

## Hardware Notes

- **Default inference is via hosted APIs** (Mistral + Groq) — local hardware only runs Neo4j and the Python pipeline.
- **GPU:** RX 560X — no ROCm on Windows, so no local GPU inference. This is why the API pivot happened.
- **RAM:** 16GB — fine for Neo4j + pipeline. Only relevant to models if using the Ollama fallback (Mistral 12B Q4_K_M needs ~8GB, 3–5 tok/s).
- **Rate limits:** Groq/Mistral free tiers rate-limit aggressively. The LLM client retries with backoff automatically; the response cache (`LLM_CACHE_DIR`) makes re-runs free.
