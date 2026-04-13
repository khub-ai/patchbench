"""
models.py — Model call abstraction for PatchBench.

Supports:
  - Anthropic API directly  (Claude models — TUTOR / VALIDATOR)
  - OpenAI-compatible API   (OpenRouter, Together, local vLLM — PUPIL models)

Usage:
    caller = ModelCaller(
        anthropic_api_key = os.environ["ANTHROPIC_API_KEY"],
        openrouter_api_key = os.environ.get("OPENROUTER_API_KEY"),
    )
    text = await caller.call(
        model   = "claude-opus-4-6",
        system  = "You are an expert.",
        content = [{"type": "text", "text": "Describe this image."}, image_block(path)],
        max_tokens = 512,
    )
"""
from __future__ import annotations

import asyncio
import base64
import os
from pathlib import Path
from typing import List, Optional


def image_block(path: str | Path) -> dict:
    """Build an Anthropic-style image content block from a file path."""
    data = base64.standard_b64encode(Path(path).read_bytes()).decode("utf-8")
    return {
        "type":   "image",
        "source": {"type": "base64", "media_type": "image/jpeg", "data": data},
    }


def _is_anthropic_model(model: str) -> bool:
    return "claude" in model.lower()


class ModelCaller:
    """Unified async model caller for Anthropic and OpenAI-compatible APIs."""

    def __init__(
        self,
        anthropic_api_key:  Optional[str] = None,
        openrouter_api_key: Optional[str] = None,
        openai_base_url:    str = "https://openrouter.ai/api/v1",
    ):
        self._anthropic_key  = anthropic_api_key  or os.environ.get("ANTHROPIC_API_KEY", "")
        self._openrouter_key = openrouter_api_key or os.environ.get("OPENROUTER_API_KEY", "")
        self._openai_base    = openai_base_url
        self._anthropic_client = None
        self._openai_client    = None

    def _get_anthropic(self):
        if self._anthropic_client is None:
            import anthropic
            self._anthropic_client = anthropic.AsyncAnthropic(api_key=self._anthropic_key)
        return self._anthropic_client

    def _get_openai(self):
        if self._openai_client is None:
            import openai
            self._openai_client = openai.AsyncOpenAI(
                api_key=self._openrouter_key or "placeholder",
                base_url=self._openai_base,
            )
        return self._openai_client

    async def call(
        self,
        model:      str,
        system:     str,
        content:    list,
        max_tokens: int = 1024,
    ) -> tuple[str, dict]:
        """Call the model. Returns (text_response, usage_dict).

        content format: list of Anthropic-style content blocks
          {"type": "text", "text": "..."}
          {"type": "image", "source": {"type": "base64", ...}}
        """
        if _is_anthropic_model(model):
            return await self._call_anthropic(model, system, content, max_tokens)
        else:
            return await self._call_openai(model, system, content, max_tokens)

    async def _call_anthropic(
        self, model: str, system: str, content: list, max_tokens: int
    ) -> tuple[str, dict]:
        client = self._get_anthropic()
        msg = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": content}],
        )
        text  = msg.content[0].text if msg.content else ""
        usage = {
            "input_tokens":  msg.usage.input_tokens,
            "output_tokens": msg.usage.output_tokens,
        }
        return text, usage

    async def _call_openai(
        self, model: str, system: str, content: list, max_tokens: int
    ) -> tuple[str, dict]:
        """Convert Anthropic-style content blocks to OpenAI format."""
        client = self._get_openai()

        oa_content = []
        for block in content:
            if block.get("type") == "text":
                oa_content.append({"type": "text", "text": block["text"]})
            elif block.get("type") == "image":
                src = block["source"]
                if src["type"] == "base64":
                    url = f"data:{src['media_type']};base64,{src['data']}"
                else:
                    url = src.get("url", "")
                oa_content.append({
                    "type":      "image_url",
                    "image_url": {"url": url},
                })

        messages = [
            {"role": "system", "content": system},
            {"role": "user",   "content": oa_content},
        ]
        resp = await client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=messages,
        )
        text  = resp.choices[0].message.content or ""
        usage = {
            "input_tokens":  getattr(resp.usage, "prompt_tokens", 0),
            "output_tokens": getattr(resp.usage, "completion_tokens", 0),
        }
        return text, usage
