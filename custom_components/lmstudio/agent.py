from __future__ import annotations
import time
import logging

from homeassistant.components.conversation import (
    ConversationEntity,
    ConversationEntityFeature,
    ConversationInput,
    ConversationResult,
    ChatLog,
)
from homeassistant.helpers.intent import IntentResponse
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, HA_TOOLS
from .memory import Memory
from .model_router import ModelRouter
from .tool_executor import ToolExecutor

_LOGGER = logging.getLogger(__name__)


class LMStudioAgent(ConversationEntity):
    """LM Studio conversation agent."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_supported_features = ConversationEntityFeature.CONTROL | ConversationEntityFeature.CHAT
    _attr_icon = "mdi:robot-confused"
    _attr_available = True

    def __init__(
        self,
        hass: HomeAssistant,
        client,
        entry_id: str,
        model_manager,
        entry: ConfigEntry,
    ):
        super().__init__()
        self.hass = hass
        self.client = client
        self.entry_id = entry_id
        self.model_manager = model_manager
        self._entry = entry
        self._memory = Memory(hass)
        self._router = ModelRouter()
        self._tools = ToolExecutor(hass, entry_id)

        model = entry.data.get("model", "LM Studio")
        self._attr_name = f"LM Studio ({model})"
        self._attr_unique_id = entry.entry_id

    @property
    def supported_languages(self) -> list[str]:
        return ["*"]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._attr_available = True
        self.async_write_ha_state()

    async def async_prepare(self, language: str | None = None) -> None:
        """Pre-load the model when HA knows a request is coming."""
        entry_data = self.hass.data[DOMAIN][self.entry_id]
        model = entry_data.get("model")
        if model:
            try:
                await self.model_manager.ensure_model(model)
            except Exception as err:
                _LOGGER.warning("async_prepare: could not load model %s: %s", model, err)

    async def _async_handle_message(
        self,
        user_input: ConversationInput,
        chat_log: ChatLog,
    ) -> ConversationResult:
        """Handle incoming message - HA 2024.6+ API."""
        entry_data = self.hass.data[DOMAIN][self.entry_id]

        cid = user_input.conversation_id or self.entry_id
        text = user_input.text
        system_prompt = entry_data.get("system_prompt", "You are a helpful smart home assistant.")
        streaming_enabled = entry_data.get("streaming", True)
        thinking_enabled = entry_data.get("thinking", False)
        model = self._router.pick_model(text, entry_data)

        entry_data["last_used"] = time.time()

        try:
            await self.model_manager.ensure_model(model)
        except Exception as err:
            _LOGGER.warning("Could not load model %s: %s", model, err)

        await self._memory.add(cid, "user", text)
        messages = [
            {"role": "system", "content": system_prompt},
            *await self._memory.get(cid),
        ]

        content = ""
        try:
            content = await self._do_chat(model, messages, streaming_enabled, thinking_enabled, chat_log)
        except Exception as err:
            _LOGGER.error("LM Studio chat error: %s", err)
            content = "Sorry, I couldn't reach LM Studio right now."

        await self._memory.add(cid, "assistant", content)

        intent_response = IntentResponse(language=user_input.language)
        intent_response.async_set_speech(content)

        return ConversationResult(
            response=intent_response,
            conversation_id=cid,
            continue_conversation=False,
        )

    async def _do_chat(
        self,
        model: str,
        messages: list,
        streaming: bool,
        thinking: bool,
        chat_log: ChatLog | None = None,
    ) -> str:
        try:
            result = await self.client.chat(
                model, messages, tools=HA_TOOLS, thinking=thinking
            )
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
                        "content": tool_result["content"],
                    })

                if streaming:
                    return await self._stream_response(model, messages, thinking, chat_log)

                followup = await self.client.chat(model, messages, thinking=thinking)
                return followup["choices"][0]["message"].get("content", "")

            if streaming:
                return await self._stream_response(model, messages, thinking, chat_log)

            return choice["message"].get("content", "")

        except Exception as err:
            _LOGGER.debug("Tool-aware chat failed (%s), falling back to plain chat", err)

            if streaming:
                return await self._stream_response(model, messages, thinking, chat_log)

            result = await self.client.chat(model, messages, thinking=thinking)
            return result["choices"][0]["message"].get("content", "")

    async def _stream_response(
        self,
        model: str,
        messages: list,
        thinking: bool,
        chat_log: ChatLog | None = None,
    ) -> str:
        """Stream response tokens and optionally send them progressively to HA."""
        content = ""
        async for token in self.client.chat_stream(model, messages, thinking=thinking):
            content += token
            if chat_log:
                try:
                    await chat_log.async_add_delta(content)
                except Exception:
                    pass
        return content
