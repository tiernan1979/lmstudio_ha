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
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    # ------------------------------------------------------------------
    # OpenAI-compatible endpoints (chat completions)
    # ------------------------------------------------------------------

    async def chat(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> dict:
        """Non-streaming chat completion."""
        payload: dict[str, object] = {
            "model": model,
            "messages": messages,
            "stream": False,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        session = await self._get_session()
        async with session.post(
            f"{self.url}/v1/chat/completions",
            json=payload,
            headers=self._headers(),
        ) as resp:
            if resp.status == 404:
                _LOGGER.error(
                    "LM Studio returned 404 — is the server running at %s?", self.url
                )
            resp.raise_for_status()
            return await resp.json()

    async def chat_stream(
        self,
        model: str,
        messages: list[dict],
    ) -> AsyncGenerator[str, None]:
        """Async generator that yields content tokens as they arrive."""
        payload: dict[str, object] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }

        session = await self._get_session()
        async with session.post(
            f"{self.url}/v1/chat/completions",
            json=payload,
            headers=self._headers(),
            timeout=aiohttp.ClientTimeout(total=300),
        ) as resp:
            if resp.status == 404:
                _LOGGER.error(
                    "LM Studio returned 404 — is the server running at %s?", self.url
                )
            resp.raise_for_status()
            buffer = ""
            async for chunk in resp.content:
                buffer += chunk.decode("utf-8")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    decoded = line.strip()
                    if not decoded or not decoded.startswith("data:"):
                        continue
                    data_str = decoded[5:].strip()
                    if data_str == "[DONE]":
                        return
                    try:
                        data = json.loads(data_str)
                        content = (
                            data.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content", "")
                        )
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

    async def list_models(self) -> dict:
        """List available models via OpenAI-compatible endpoint."""
        session = await self._get_session()
        async with session.get(
            f"{self.url}/v1/models", headers=self._headers()
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    # ------------------------------------------------------------------
    # LM Studio native API endpoints (model management)
    # ------------------------------------------------------------------

    async def load_model(self, model_id: str) -> dict:
        """Load a model via LM Studio native API.

        POST /api/v1/models/load
        Body: {"instance_id": "<model>"}
        """
        session = await self._get_session()
        _LOGGER.info("Loading model %s via LM Studio API", model_id)
        async with session.post(
            f"{self.url}/api/v1/models/load",
            json={"instance_id": model_id},
            headers=self._headers(),
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def unload_model(self, model_id: str) -> dict:
        """Unload a model via LM Studio native API.

        POST /api/v1/models/unload
        Body: {"instance_id": "<model>"}
        """
        session = await self._get_session()
        _LOGGER.info("Unloading model %s via LM Studio API", model_id)
        async with session.post(
            f"{self.url}/api/v1/models/unload",
            json={"instance_id": model_id},
            headers=self._headers(),
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def get_chat_state(self) -> dict:
        """Get current chat / model state via LM Studio native API.

        GET /api/v1/chat/get
        Returns info about currently loaded model, context, etc.
        """
        session = await self._get_session()
        async with session.get(
            f"{self.url}/api/v1/chat/get", headers=self._headers()
        ) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def get_loaded_models(self) -> dict:
        """Get list of currently loaded model instances.

        GET /api/v1/models
        (LM Studio native endpoint, different from OpenAI /v1/models)
        """
        session = await self._get_session()
        async with session.get(
            f"{self.url}/api/v1/models", headers=self._headers()
        ) as resp:
            if resp.status == 404:
                _LOGGER.debug("Native /api/v1/models not available, falling back")
                return {"data": []}
            resp.raise_for_status()
            return await resp.json()

    async def download_model(self, model_id: str) -> dict:
        """Trigger a model download via LM Studio native API.

        POST /api/v1/models/download
        Body: {"instance_id": "<model>"}
        """
        session = await self._get_session()
        _LOGGER.info("Downloading model %s via LM Studio API", model_id)
        async with session.post(
            f"{self.url}/api/v1/models/download",
            json={"instance_id": model_id},
            headers=self._headers(),
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            if resp.status == 404:
                _LOGGER.warning(
                    "Download endpoint not available on this LM Studio version. "
                    "Download the model through the LM Studio UI instead."
                )
                return {"status": "not_supported"}
            resp.raise_for_status()
            return await resp.json()

    async def is_available(self) -> bool:
        """Check if LM Studio server is reachable."""
        try:
            session = await self._get_session()
            async with session.get(
                f"{self.url}/v1/models",
                headers=self._headers(),
                timeout=aiohttp.ClientTimeout(total=5),
            ) as resp:
                return resp.status == 200
        except Exception:
            return False
