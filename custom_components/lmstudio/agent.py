from __future__ import annotations
import logging
from typing import Any, AsyncGenerator

from homeassistant.components.conversation import (
    AbstractConversationAgent,
    AgentFormatResponseChunk,
    ConversationContext,
    ConversationResult,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from .client import LMStudioClient
from .const import DOMAIN, HA_TOOLS
from .model_manager import ModelManager
from .memory import Memory
from .model_router import ModelRouter
from .tool_executor import ToolExecutor

_LOGGER = logging.getLogger(__name__)


class LMStudioConversationAgent(AbstractConversationAgent):
    """LM Studio conversation agent for Home Assistant voice assistant."""

    @property
    def supported_languages(self) -> list[str] | None:
        return ["en"]

    def __init__(
        self,
        hass: HomeAssistant,
        client: LMStudioClient,
        entry_id: str,
        entry_data: dict[str, Any],
    ) -> None:
        super().__init__()
        self.hass = hass
        self.client = client
        self.entry_id = entry_id
        self._entry_data = entry_data
        self._memory = Memory(hass)
        self._router = ModelRouter(entry_data)
        self._tools = ToolExecutor(hass, entry_id)
        self._manager = ModelManager(hass, client, entry_id)

    @property
    def agent_id(self) -> str:
        return f"lmstudio-{self.entry_id}"

    async def async_get_summary(self) -> str | None:
        model = self._entry_data.get("model", "LM Studio")
        return f"LM Studio ({model})"

    async def async_process(
        self,
        string: str,
        context: ConversationContext,
        stream: bool = False,
    ) -> ConversationResult | AsyncGenerator[AgentFormatResponseChunk, None]:
        """Process a conversation turn."""
        cid = context.conversation_id or self.entry_id
        system_prompt = self._entry_data.get(
            "system_prompt", "You are a helpful smart home assistant."
        )
        thinking_enabled = self._entry_data.get("thinking", False)
        use_tools = self._entry_data.get("use_tools", True)
        model = self._router.pick_model(string)
        if model == "LIST_MODELS":
            models = await self.client.list_models()
            model_ids = [m["id"] for m in models.get("data", []) if "id" in m]
            speech = f"Available models: {', '.join(model_ids)}"
            intent_response = intent.IntentResponse(language=context.language)
            intent_response.async_set_speech(speech)
            return ConversationResult(
                response=intent_response,
                conversation_id=cid,
            )

        await self._manager.ensure_model(model)

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            *await self._memory.get(cid),
        ]

        if stream:
            return await self._stream_process(
                string, cid, model, messages, thinking_enabled, use_tools, context
            )

        content = ""
        try:
            content = await self._do_chat(
                model, messages, thinking_enabled, use_tools
            )
        except Exception as err:
            _LOGGER.error("LM Studio chat error: %s", err)
            content = "Sorry, I couldn't reach LM Studio right now."

        if not content:
            content = "I didn't receive a response."

        await self._memory.add(cid, "user", string)
        await self._memory.add(cid, "assistant", content)

        intent_response = intent.IntentResponse(language=context.language)
        intent_response.async_set_speech(content)

        return ConversationResult(
            response=intent_response,
            conversation_id=cid,
        )

    async def _stream_process(
        self,
        string: str,
        cid: str,
        model: str,
        messages: list[dict[str, str]],
        thinking_enabled: bool,
        use_tools: bool,
        context: ConversationContext,
    ) -> AsyncGenerator[AgentFormatResponseChunk, None]:
        """Stream tokens back to Home Assistant."""
        await self._memory.add(cid, "user", string)

        content_parts: list[str] = []
        try:
            tools = HA_TOOLS if use_tools else None

            # First check if the model wants to call tools (non-streaming check)
            if use_tools:
                try:
                    result = await self.client.chat(model, messages, tools=tools)
                    choice = result["choices"][0]

                    if choice.get("finish_reason") == "tool_calls":
                        tool_calls = choice["message"].get("tool_calls", [])
                        _LOGGER.debug("Executing %d tool call(s)", len(tool_calls))
                        tool_results = await self._tools.execute_tool_calls(tool_calls)

                        messages.append(choice["message"])
                        for tool_result in tool_results:
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_result["tool_call_id"],
                                "content": str(tool_result["content"]),
                            })

                    else:
                        text = choice["message"].get("content", "")
                        content_parts.append(text)
                        yield AgentFormatResponseChunk(
                            agent_id=self.agent_id,
                            response_chunk=text,
                        )
                        await self._memory.add(cid, "assistant", "".join(content_parts))
                        return
                except Exception as err:
                    _LOGGER.debug("Tool check failed (%s), streaming plain chat", err)

            # Stream the final response
            async for token in self.client.chat_stream(model, messages):
                content_parts.append(token)
                yield AgentFormatResponseChunk(
                    agent_id=self.agent_id,
                    response_chunk=token,
                )

        except Exception as err:
            _LOGGER.error("Streaming error: %s", err)
            error_msg = "Sorry, streaming failed."
            yield AgentFormatResponseChunk(
                agent_id=self.agent_id,
                response_chunk=error_msg,
            )
            content_parts.append(error_msg)

        full_text = "".join(content_parts)
        await self._memory.add(cid, "assistant", full_text)

    async def _do_chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        thinking_enabled: bool,
        use_tools: bool,
    ) -> str:
        """Non-streaming chat with tool support."""
        tools = HA_TOOLS if use_tools else None

        try:
            result = await self.client.chat(model, messages, tools=tools)
            choice = result["choices"][0]

            if choice.get("finish_reason") == "tool_calls":
                tool_calls = choice["message"].get("tool_calls", [])
                _LOGGER.debug("Executing %d tool call(s)", len(tool_calls))
                tool_results = await self._tools.execute_tool_calls(tool_calls)

                messages.append(choice["message"])
                for tool_result in tool_results:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_result["tool_call_id"],
                        "content": str(tool_result["content"]),
                    })

                followup = await self.client.chat(model, messages)
                return followup["choices"][0]["message"].get("content", "")

            return choice["message"].get("content", "")

        except Exception as err:
            _LOGGER.debug("Tool-aware chat failed (%s), falling back to plain chat", err)
            result = await self.client.chat(model, messages)
            return result["choices"][0]["message"].get("content", "")
