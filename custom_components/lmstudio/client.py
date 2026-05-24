from __future__ import annotations
import asyncio
import json
import logging
from typing import Any, AsyncGenerator

import aiohttp

_LOGGER = logging.getLogger(__name__)


class LMStudioClient:

    def __init__(self, url: str, api_key: str | None = None) -> None:
        self.url = url.rstrip("/")
        self.api_key = api_key
        self._session: aiohttp.ClientSession | None = None
        self._lock = asyncio.Lock()

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

    async def list_models(self) -> list[str]:
        session = await self._get_session()
        async with session.get(
            f"{self.url}/v1/models", headers=self._headers()
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return [m["id"] for m in data.get("data", []) if "id" in m]

    async def load_model(self, model_id: str) -> dict:
        session = await self._get_session()
        _LOGGER.info("Loading model %s", model_id)
        payload = {"model": model_id}
        async with session.post(
            f"{self.url}/api/v1/models/load",
            json=payload,
            headers=self._headers(),
            timeout=aiohttp.ClientTimeout(total=60),
        ) as resp:
            if resp.status >= 400:
                text = await resp.text()
                _LOGGER.error("Load model failed (%s): %s", resp.status, text)
            resp.raise_for_status()
            return await resp.json()

    async def unload_model(self, model_id: str) -> dict:
        session = await self._get_session()
        _LOGGER.info("Unloading model %s", model_id)
        payload = {"model": model_id}
        async with session.post(
            f"{self.url}/api/v1/models/unload",
            json=payload,
            headers=self._headers(),
        ) as resp:
            if resp.status >= 400:
                text = await resp.text()
                _LOGGER.error("Unload model failed (%s): %s", resp.status, text)
            resp.raise_for_status()
            return await resp.json()

    async def is_available(self) -> bool:
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

    async def chat_completions(
        self,
        model: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        if max_tokens:
            payload["max_tokens"] = max_tokens

        accumulated_tool_calls: dict[int, dict] = {}

        session = await self._get_session()
        async with session.post(
            f"{self.url}/v1/chat/completions",
            json=payload,
            headers=self._headers(),
            timeout=aiohttp.ClientTimeout(total=300),
        ) as resp:
            if resp.status == 404:
                _LOGGER.error(
                    "LM Studio returned 404 - is the server running at %s?", self.url
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
                        if accumulated_tool_calls:
                            tool_calls = _assemble_tool_calls(accumulated_tool_calls)
                            yield {"type": "tool_calls", "tool_calls": tool_calls}
                        yield {"type": "done", "finish_reason": "stop"}
                        return
                    try:
                        data = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    choices = data.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})

                    content = delta.get("content")
                    if content:
                        yield {"type": "content", "content": content}

                    tc_deltas = delta.get("tool_calls")
                    if tc_deltas:
                        for tc in tc_deltas:
                            idx = tc.get("index", 0)
                            if idx not in accumulated_tool_calls:
                                accumulated_tool_calls[idx] = {}
                            func = tc.get("function", {})
                            if "id" in tc and tc["id"]:
                                accumulated_tool_calls[idx]["id"] = tc["id"]
                            if "name" in func and func["name"]:
                                accumulated_tool_calls[idx]["name"] = func["name"]
                            if "arguments" in func and func["arguments"]:
                                accumulated_tool_calls[idx].setdefault(
                                    "arguments", ""
                                )
                                accumulated_tool_calls[idx][
                                    "arguments"
                                ] += func["arguments"]

                    finish = choices[0].get("finish_reason")
                    if finish == "stop":
                        yield {"type": "done", "finish_reason": "stop"}
                        return
                    if finish == "tool_calls":
                        tool_calls = _assemble_tool_calls(accumulated_tool_calls)
                        yield {"type": "tool_calls", "tool_calls": tool_calls}
                        yield {"type": "done", "finish_reason": "tool_calls"}
                        return


def _assemble_tool_calls(
    accumulated: dict[int, dict],
) -> list[dict[str, Any]]:
    result = []
    for idx in sorted(accumulated.keys()):
        tc = accumulated[idx]
        try:
            args = json.loads(tc.get("arguments", "{}"))
        except json.JSONDecodeError:
            args = tc.get("arguments", {})
        result.append({
            "id": tc.get("id", f"call_{idx}"),
            "type": "function",
            "function": {
                "name": tc.get("name", ""),
                "arguments": args,
            },
        })
    return result
