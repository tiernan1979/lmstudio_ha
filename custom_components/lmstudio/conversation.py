from __future__ import annotations
import json
import time
import logging

from homeassistant.components.conversation import (
    AbstractConversationAgent,
    ConversationInput,
    ConversationResult,
)
from homeassistant.helpers.intent import IntentResponse
from homeassistant.core import HomeAssistant

from .const import DOMAIN, HA_TOOLS
from .memory import Memory
from .model_router import ModelRouter
from .tool_executor import ToolExecutor

_LOGGER = logging.getLogger(__name__)


class LMStudioAgent(AbstractConversationAgent):

    def __init__(self, hass: HomeAssistant, client, entry_id: str, model_manager):
        self.hass = hass
        self.client = client
        self.entry_id = entry_id
        self.model_manager = model_manager
        self._memory = Memory()
        self._router = ModelRouter()
        self._tools = ToolExecutor(hass, entry_id)

    @property
    def supported_languages(self) -> list[str]:
        return ["*"]

    async def async_process(self, user_input: ConversationInput) -> ConversationResult:
        entry_data = self.hass.data[DOMAIN][self.entry_id]

        cid = user_input.conversation_id or self.entry_id
        text = user_input.text
        system_prompt = entry_data.get("system_prompt", "You are a helpful smart home assistant.")
        streaming_enabled = entry_data.get("streaming", True)
        model = self._router.pick_model(text, entry_data)

        entry_data["last_used"] = time.time()

        try:
            await self.model_manager.ensure_model(model)
        except Exception as err:
            _LOGGER.warning("Could not load model %s: %s", model, err)

        self._memory.add(cid, "user", text)
        messages = [
            {"role": "system", "content": system_prompt},
            *self._memory.get(cid),
        ]

        content = ""
        try:
            # First pass — send with tools so LLM can request device control
            result = await self.client.chat(model, messages, tools=HA_TOOLS)
            choice = result["choices"][0]
            finish_reason = choice.get("finish_reason")

            if finish_reason == "tool_calls":
                # Execute whatever the LLM asked for
                tool_calls = choice["message"]["tool_calls"]
                await self._tools.execute_tool_calls(tool_calls)

                # Append the assistant tool_call message + a tool result
                messages.append(choice["message"])
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_calls[0]["id"],
                    "content": "Done.",
                })

                # Second pass — get natural language confirmation
                followup = await self.client.chat(model, messages)
                content = followup["choices"][0]["message"]["content"]

            else:
                # Normal response — stream if enabled
                if streaming_enabled:
                    async for token in self.client.chat_stream(model, messages):
                        content += token
                else:
                    content = choice["message"]["content"]

        except Exception as err:
            _LOGGER.error("LM Studio chat error: %s", err)
            content = "Sorry, I couldn't reach LM Studio right now."

        self._memory.add(cid, "assistant", content)

        intent_response = IntentResponse(language=user_input.language)
        intent_response.async_set_speech(content)

        return ConversationResult(
            response=intent_response,
            conversation_id=cid,
        )

    async def async_will_remove_from_hass(self) -> None:
        pass