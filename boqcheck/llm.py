"""LLM client abstraction (Anthropic Messages API format). One adapter per provider."""
from __future__ import annotations

import itertools
import os
from typing import Protocol


class LLMClient(Protocol):
    def create(self, system: str, messages: list[dict], tools: list[dict]) -> dict: ...


class AnthropicClient:
    def __init__(self, model: str | None = None, max_tokens: int = 2500):
        try:
            import anthropic
        except ImportError as e:                                   # pragma: no cover
            raise RuntimeError("pip install anthropic") from e
        self._client = anthropic.Anthropic()
        self.model = model or os.getenv("AGENT_MODEL", "claude-sonnet-5-5")
        self.max_tokens = max_tokens

    def create(self, system, messages, tools):                     # pragma: no cover
        resp = self._client.messages.create(model=self.model, max_tokens=self.max_tokens,
                                            system=system, tools=tools, messages=messages)
        content = []
        for b in resp.content:
            if b.type == "text":
                content.append({"type": "text", "text": b.text})
            elif b.type == "tool_use":
                content.append({"type": "tool_use", "id": b.id, "name": b.name, "input": dict(b.input)})
        u = getattr(resp, "usage", None)
        return {"content": content, "stop_reason": resp.stop_reason,
                "usage": {"input_tokens": getattr(u, "input_tokens", 0), "output_tokens": getattr(u, "output_tokens", 0)}}


class ScriptedLLM:
    """Test double: returns pre-written responses in order. Not a measure of model quality."""
    _ids = itertools.count(1)

    def __init__(self, script):
        self.script, self.calls = list(script), 0

    def create(self, system, messages, tools):
        r = self.script[min(self.calls, len(self.script) - 1)]
        self.calls += 1
        return r

    @staticmethod
    def tool(name, args):
        return {"content": [{"type": "tool_use", "id": f"toolu_{next(ScriptedLLM._ids)}", "name": name, "input": args}],
                "stop_reason": "tool_use", "usage": {"input_tokens": 0, "output_tokens": 0}}

    @staticmethod
    def text(msg):
        return {"content": [{"type": "text", "text": msg}], "stop_reason": "end_turn", "usage": {"input_tokens": 0, "output_tokens": 0}}
