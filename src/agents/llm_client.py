"""
LLM client router — picks Mistral API, Groq, or local Ollama based on .env.

Usage:
    from src.agents.llm_client import get_client, ModelRole
    client = get_client(ModelRole.EXTRACTION)
    response = client.chat("Extract SPO triplets from: ...")
"""

import os
from dataclasses import dataclass
from enum import Enum

from dotenv import load_dotenv

load_dotenv()


class ModelRole(Enum):
    EXTRACTION = "extraction"       # Mistral Nemo — high-accuracy SPO extraction
    ORCHESTRATION = "orchestration" # Llama 3.1 8B — fast orchestration + validation


@dataclass
class ChatResponse:
    content: str
    model: str
    provider: str


class _MistralClient:
    def __init__(self, model: str):
        from mistralai.client import Mistral
        self._client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
        self.model = model
        self.provider = "mistral"

    def chat(self, prompt: str, system: str | None = None) -> ChatResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = self._client.chat.complete(model=self.model, messages=messages)
        return ChatResponse(
            content=resp.choices[0].message.content,
            model=self.model,
            provider=self.provider,
        )


class _GroqClient:
    def __init__(self, model: str):
        from groq import Groq
        self._client = Groq(api_key=os.environ["GROQ_API_KEY"])
        self.model = model
        self.provider = "groq"

    def chat(self, prompt: str, system: str | None = None) -> ChatResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = self._client.chat.completions.create(model=self.model, messages=messages)
        return ChatResponse(
            content=resp.choices[0].message.content,
            model=self.model,
            provider=self.provider,
        )


class _OllamaClient:
    def __init__(self, model: str):
        import requests
        self._requests = requests
        self._base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model
        self.provider = "ollama"

    def chat(self, prompt: str, system: str | None = None) -> ChatResponse:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = self._requests.post(
            f"{self._base_url}/api/chat",
            json={"model": self.model, "messages": messages, "stream": False},
            timeout=300,
        )
        resp.raise_for_status()
        content = resp.json()["message"]["content"]
        return ChatResponse(content=content, model=self.model, provider=self.provider)


def get_client(role: ModelRole) -> _MistralClient | _GroqClient | _OllamaClient:
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
