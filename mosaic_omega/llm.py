"""Optional LLM backends.

MOSAIC-Omega runs end to end with no network access and no API key: agents fall
back to `HeuristicReasoner`, which is deterministic. Attach `AnthropicBackend`
to route agent cognition through a real model instead.
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol


class LLMBackend(Protocol):
    def complete(self, system: str, prompt: str, max_tokens: int = 1024) -> str: ...


@dataclass
class NullBackend:
    """No-op backend. Agents use their heuristic reasoner."""
    def complete(self, system: str, prompt: str, max_tokens: int = 1024) -> str:
        return ""


@dataclass
class AnthropicBackend:
    """Minimal stdlib client for the Anthropic Messages API."""
    model: str = "claude-sonnet-4-6"
    api_key: Optional[str] = None
    base_url: str = "https://api.anthropic.com/v1/messages"
    timeout_s: float = 60.0
    last_usage: Dict[str, int] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.last_usage = {"input_tokens": 0, "output_tokens": 0}

    def complete(self, system: str, prompt: str, max_tokens: int = 1024) -> str:
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        req = urllib.request.Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "content-type": "application/json",
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        self.last_usage = data.get("usage", self.last_usage)
        return "".join(
            block.get("text", "") for block in data.get("content", [])
            if block.get("type") == "text"
        )


def parse_json_block(text: str) -> Any:
    """Tolerant JSON extraction from a model reply."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.lstrip().lower().startswith("json"):
            cleaned = cleaned.lstrip()[4:]
    start = cleaned.find("{")
    alt = cleaned.find("[")
    if alt != -1 and (start == -1 or alt < start):
        start = alt
    if start == -1:
        raise ValueError("no JSON object found")
    end = max(cleaned.rfind("}"), cleaned.rfind("]"))
    return json.loads(cleaned[start:end + 1])
