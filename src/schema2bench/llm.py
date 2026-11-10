from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class LlmResponse:
    text: str
    provider: str


class LlmProvider:
    def complete(self, prompt: str) -> LlmResponse:
        raise NotImplementedError


class NoLlmProvider(LlmProvider):
    def complete(self, prompt: str) -> LlmResponse:
        raise RuntimeError("No LLM provider configured. Use --llm-provider ollama/openai or omit LLM methods.")


class OllamaProvider(LlmProvider):
    def __init__(self, model: str, endpoint: str = "http://localhost:11434/api/generate", temperature: float = 0.2):
        self.model = model
        self.endpoint = endpoint
        self.temperature = temperature

    def complete(self, prompt: str) -> LlmResponse:
        payload = json.dumps({"model": self.model, "prompt": prompt, "stream": False, "options": {"temperature": self.temperature}}).encode("utf-8")
        req = urllib.request.Request(self.endpoint, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return LlmResponse(data.get("response", ""), f"ollama:{self.model}")


class OpenAICompatibleProvider(LlmProvider):
    def __init__(self, model: str, endpoint: str | None = None, api_key: str | None = None, temperature: float = 0.2):
        self.model = model
        self.endpoint = endpoint or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1") + "/chat/completions"
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.temperature = temperature

    def complete(self, prompt: str) -> LlmResponse:
        payload = json.dumps(
            {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": self.temperature,
            }
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(self.endpoint, data=payload, headers=headers)
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        text = data["choices"][0]["message"]["content"]
        return LlmResponse(text, f"openai_compatible:{self.model}")


def build_provider(name: str, model: str | None = None, endpoint: str | None = None, temperature: float = 0.2) -> LlmProvider:
    if name == "none":
        return NoLlmProvider()
    if name == "ollama":
        return OllamaProvider(model or "qwen2.5:7b", endpoint or "http://localhost:11434/api/generate", temperature=temperature)
    if name == "openai":
        return OpenAICompatibleProvider(model or "gpt-4.1-mini", endpoint, temperature=temperature)
    raise ValueError(f"Unknown LLM provider {name}")


def extract_json_object(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("LLM response does not contain a JSON object")
    return json.loads(text[start : end + 1])
