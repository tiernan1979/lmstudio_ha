from __future__ import annotations
import json
import logging
from typing import AsyncGenerator

import aiohttp

_LOGGER = logging.getLogger(__name__)


class LMStudioClient:

    def __init__(self, config: dict):
        self.config = config
        self.url = config["url"].rstrip("/")
        self.api_key = config.get("api_key", "")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    # ─────────────────────────────
    # NON-STREAMING CHAT
    # ─────────────────────────────
    async def chat(
        self,
        model: str,
        messages: list,
        tools: list | None = None,
        thinking: bool = False,
    ) -> dict:
        payload: dict = {
            "model": model,
            "messages": messages,
            "stream": False,
        }

        # Only add tools if provided
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        # Explicitly control thinking — pass False to disable, True to enable
        # LM Studio / llama.cpp uses "thinking" key in the payload
        payload["thinking"] = thinking

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.url}/v1/chat/completions",
                json=payload,
                headers=self._headers(),
            ) as resp:
                resp.raise_for_status()
                return await resp.json()

    # ─────────────────────────────
    # STREAMING CHAT
    # ─────────────────────────────
    async def chat_stream(
        self,
        model: str,
        messages: list,
        thinking: bool = False,
    ) -> AsyncGenerator[str, None]:
        """Async generator — yields content tokens as they arrive."""
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "thinking": thinking,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.url}/v1/chat/completions",
                json=payload,
                headers=self._headers(),
            ) as resp:
                resp.raise_for_status()
                async for raw in resp.content:
                    if not raw:
                        continue
                    try:
                        decoded = raw.decode("utf-8").strip()
                        if not decoded.startswith("data:"):
                            continue
                        data = decoded[5:].strip()
                        if data == "[DONE]":
                            break
                        chunk = json.loads(data)
                        delta = (
                            chunk.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content", "")
                        )
                        if delta:
                            yield delta
                    except Exception:
                        continue

    # ─────────────────────────────
    # MODEL MANAGEMENT
    # ─────────────────────────────
    async def list_models(self) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.url}/v1/models", headers=self._headers()
            ) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def load_model(self, model: str) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.url}/api/v1/models/load",
                json={"model": model},
                headers=self._headers(),
            ) as resp:
                resp.raise_for_status()
                return await resp.json()

    async def download_model(self, model: str) -> dict:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.url}/api/v1/models/download",
                json={"model": model},
                headers=self._headers(),
            ) as resp:
                resp.raise_for_status()
                return await resp.json()