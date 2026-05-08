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
python -c "import neo4j, ollama, datasets, pandas; print('All core packages OK')"
```

---

## Step 2 — Ollama (Local Model Serving)

1. Download Ollama from https://ollama.com/download — install the Windows version.
2. Verify installation:
   ```powershell
   ollama --version
   ```
3. Pull both models (this will take a while — Mistral is ~7GB, Llama 3.1 8B is ~5GB):
   ```powershell
   ollama pull mistral-nemo
   ollama pull llama3.1:8b
   ```
4. Verify both models are available:
   ```powershell
   ollama list
   ```
5. Quick sanity check (Ollama must be running):
   ```powershell
   ollama run mistral-nemo "Reply with only the word OK."
   ```

> **Note:** Ollama runs as a background service after installation. Models run CPU-only on this machine (~3–5 tokens/sec for Mistral 12B). This is expected.

> **Model name note:** `mistral-nemo` in Ollama refers to Mistral Nemo 12B. Confirm the exact tag with `ollama list` after pulling.

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

Copy `.env.example` to `.env` and fill in your Neo4j password:

```powershell
Copy-Item .env.example .env
```

Then edit `.env` with your actual values (especially `NEO4J_PASSWORD`).

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

This checks: venv packages, Ollama connectivity, Neo4j connectivity, and processed dataset files.

---

## Hardware Notes

- **GPU:** RX 560X — no ROCm on Windows. All inference runs on CPU.
- **RAM:** 16GB — Mistral 12B Q4_K_M uses ~8GB RAM. Avoid running Neo4j + both models simultaneously without monitoring memory.
- **Inference speed:** Expect 3–5 tok/s for Mistral 12B, 8–12 tok/s for Llama 3.1 8B on this CPU.
- **Large experiments:** Run on Google Colab (GPU) or Groq API. Local is for development and small-scale tests.
