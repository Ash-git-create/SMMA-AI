"""
Quick connectivity test — verifies both API keys work before running any agents.
Run from project root: python scripts/test_llm_connections.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.llm_client import get_client, ModelRole


def test(role: ModelRole, label: str) -> bool:
    print(f"\n[{label}]")
    try:
        client = get_client(role)
        print(f"  provider : {client.provider}")
        print(f"  model    : {client.model}")
        resp = client.chat("Reply with only the word OK.")
        print(f"  response : {resp.content.strip()}")
        print(f"  STATUS   : OK")
        return True
    except Exception as e:
        print(f"  ERROR    : {e}")
        return False


if __name__ == "__main__":
    results = [
        test(ModelRole.EXTRACTION, "Extraction agent (Mistral Nemo)"),
        test(ModelRole.ORCHESTRATION, "Orchestration agent (Llama 3.1 8B)"),
    ]
    print()
    if all(results):
        print("All connections OK. Ready to build agents.")
    else:
        print("One or more connections failed. Check your .env API keys.")
        sys.exit(1)
