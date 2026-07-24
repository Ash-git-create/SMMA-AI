"""
LLM client router — picks Mistral API, Groq, or local Ollama based on .env.

All calls are deterministic and resilient by default:
  - temperature=0.0 (reproducible experiments — override via LLM_TEMPERATURE)
  - bounded output (LLM_MAX_TOKENS, default 1024)
  - automatic retry with exponential backoff on transient API errors
  - optional audit log of every request/response (LLM_LOG_FILE)
  - optional on-disk response cache, keyed on (provider, model, temperature,
    system, prompt) — re-runs cost nothing (LLM_CACHE_DIR). Only used when
    temperature == 0, since sampled outputs are not cacheable.

Usage:
    from src.agents.llm_client import get_client, ModelRole
    client = get_client(ModelRole.EXTRACTION)
    response = client.chat("Extract SPO triplets from: ...")
"""

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from loguru import logger

load_dotenv()

_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))
_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1024"))
_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))
_MAX_RATE_LIMIT_WAIT = float(os.getenv("LLM_MAX_RATE_LIMIT_WAIT", "300"))
_LOG_FILE = os.getenv("LLM_LOG_FILE", "")
_CACHE_DIR = os.getenv("LLM_CACHE_DIR", "")


class ModelRole(Enum):
    EXTRACTION = "extraction"       # Mistral Nemo — high-accuracy SPO extraction
    ORCHESTRATION = "orchestration" # Llama 3.1 8B — fast orchestration + validation


@dataclass
class ChatResponse:
    content: str
    model: str
    provider: str
    cached: bool = False


class _BaseClient:
    """Shared chat pipeline: cache → retry loop → audit log."""

    model: str
    provider: str

    def chat(self, prompt: str, system: Optional[str] = None) -> ChatResponse:
        cache_key = self._cache_key(prompt, system)
        cached = self._cache_get(cache_key)
        if cached is not None:
            self._log(prompt, system, cached, cached=True)
            return ChatResponse(content=cached, model=self.model,
                                provider=self.provider, cached=True)

        last_exc: Optional[Exception] = None
        for attempt in range(_MAX_RETRIES):
            try:
                content = self._chat_raw(prompt, system)
                self._cache_put(cache_key, content)
                self._log(prompt, system, content, cached=False)
                return ChatResponse(content=content, model=self.model,
                                    provider=self.provider)
            except Exception as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    wait: float = 2 ** (attempt + 1)  # 2s, 4s, ...
                    # Rate-limit errors often state their own wait ("Please
                    # try again in 3m55.6992s"). Honor it (capped) instead of
                    # retrying into the same closed window — otherwise long
                    # experiment batches burn all retries in seconds and the
                    # infra failures leak into the measurements.
                    suggested = self._suggested_wait(str(exc))
                    if suggested is not None:
                        wait = min(suggested + 2.0, _MAX_RATE_LIMIT_WAIT)
                    logger.warning(
                        f"[llm:{self.provider}] attempt {attempt + 1}/{_MAX_RETRIES} "
                        f"failed ({exc}) — retrying in {wait:.0f}s"
                    )
                    time.sleep(wait)
        raise last_exc  # all retries exhausted — caller decides how to degrade

    @staticmethod
    def _suggested_wait(error_text: str) -> Optional[float]:
        """Parse 'try again in 3m55.6992s' / 'try again in 12.4s' from a
        rate-limit message. Returns seconds, or None if absent."""
        m = re.search(r"try again in (?:(\d+)m)?([\d.]+)s", error_text)
        if not m:
            return None
        minutes = int(m.group(1)) if m.group(1) else 0
        return minutes * 60 + float(m.group(2))

    def _chat_raw(self, prompt: str, system: Optional[str]) -> str:
        raise NotImplementedError

    @staticmethod
    def _messages(prompt: str, system: Optional[str]) -> list[dict]:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return messages

    # -- cache ---------------------------------------------------------------

    def _cache_key(self, prompt: str, system: Optional[str]) -> Optional[str]:
        if not _CACHE_DIR or _TEMPERATURE != 0.0:
            return None
        raw = f"{self.provider}|{self.model}|{_TEMPERATURE}|{system or ''}|{prompt}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _cache_get(key: Optional[str]) -> Optional[str]:
        if key is None:
            return None
        path = Path(_CACHE_DIR) / f"{key}.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))["content"]
            except (json.JSONDecodeError, KeyError, OSError):
                return None
        return None

    @staticmethod
    def _cache_put(key: Optional[str], content: str) -> None:
        if key is None:
            return
        cache_dir = Path(_CACHE_DIR)
        cache_dir.mkdir(parents=True, exist_ok=True)
        (cache_dir / f"{key}.json").write_text(
            json.dumps({"content": content}), encoding="utf-8"
        )

    # -- audit log -------------------------------------------------------------

    def _log(self, prompt: str, system: Optional[str], response: str, cached: bool) -> None:
        if not _LOG_FILE:
            return
        record = {
            "ts":       datetime.now(timezone.utc).isoformat(),
            "provider": self.provider,
            "model":    self.model,
            "system":   system or "",
            "prompt":   prompt,
            "response": response,
            "cached":   cached,
        }
        log_path = Path(_LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


class _MistralClient(_BaseClient):
    def __init__(self, model: str):
        from mistralai.client import Mistral
        self._client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
        self.model = model
        self.provider = "mistral"

    def _chat_raw(self, prompt: str, system: Optional[str]) -> str:
        resp = self._client.chat.complete(
            model=self.model,
            messages=self._messages(prompt, system),
            temperature=_TEMPERATURE,
            max_tokens=_MAX_TOKENS,
        )
        return resp.choices[0].message.content


class _GroqClient(_BaseClient):
    def __init__(self, model: str):
        from groq import Groq
        self._client = Groq(api_key=os.environ["GROQ_API_KEY"])
        self.model = model
        self.provider = "groq"

    def _chat_raw(self, prompt: str, system: Optional[str]) -> str:
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=self._messages(prompt, system),
            temperature=_TEMPERATURE,
            max_tokens=_MAX_TOKENS,
        )
        return resp.choices[0].message.content


class _OllamaClient(_BaseClient):
    def __init__(self, model: str):
        import requests
        self._requests = requests
        self._base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model
        self.provider = "ollama"

    def _chat_raw(self, prompt: str, system: Optional[str]) -> str:
        resp = self._requests.post(
            f"{self._base_url}/api/chat",
            json={
                "model": self.model,
                "messages": self._messages(prompt, system),
                "stream": False,
                "options": {"temperature": _TEMPERATURE, "num_predict": _MAX_TOKENS},
            },
            timeout=300,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]


class _AnthropicClient(_BaseClient):
    """Claude via the Anthropic API — used only by the offline model-scale
    replay probes (scripts/replay_propagation.py), never in the in-run
    contamination pipeline. Anthropic separates `system` from `messages`, and
    Sonnet-5/Opus rejects `temperature`/`top_p` (400) — so this client does not
    pass a sampling parameter, and disables thinking so the generation is
    apples-to-apples with Nemo's single-pass synthesis (no reasoning tokens)."""

    def __init__(self, model: str):
        import anthropic
        self._anthropic = anthropic
        self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
        self.model = model
        self.provider = "anthropic"

    def _chat_raw(self, prompt: str, system: Optional[str]) -> str:
        kwargs = dict(
            model=self.model,
            max_tokens=_MAX_TOKENS,
            thinking={"type": "disabled"},
            messages=[{"role": "user", "content": prompt}],
        )
        if system:
            kwargs["system"] = system
        resp = self._client.messages.create(**kwargs)
        return "".join(b.text for b in resp.content if b.type == "text").strip()


def get_client(role: ModelRole) -> _BaseClient:
    """Return the appropriate LLM client for the given role."""
    if role == ModelRole.EXTRACTION:
        provider = os.getenv("EXTRACTION_PROVIDER", "mistral").lower()
        model = os.getenv("EXTRACTION_MODEL", "open-mistral-nemo")
    else:
        provider = os.getenv("ORCHESTRATION_PROVIDER", "groq").lower()
        model = os.getenv("ORCHESTRATION_MODEL", "llama-3.1-8b-instant")

    if provider == "mistral":
        return _MistralClient(model)
    elif provider == "groq":
        return _GroqClient(model)
    elif provider == "ollama":
        return _OllamaClient(model)
    else:
        raise ValueError(f"Unknown provider '{provider}'. Use: mistral, groq, ollama")
