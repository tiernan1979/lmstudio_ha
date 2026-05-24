"""LM Studio conversation agent for Home Assistant."""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from .model_manager import ModelManager

from homeassistant.components.conversation.models import (
    AbstractConversationAgent,
    ConversationInput,
    ConversationResult,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from .client import LMStudioClient
from .const import (
    CONF_PROMPT,
    CONF_THINKING,
    CONF_USE_TOOLS,
    DEFAULT_PROMPT,
    DEFAULT_THINKING,
    DEFAULT_USE_TOOLS,
    HA_TOOLS,
)
from .memory import Memory
from .model_router import ModelRouter, LIST_MODELS
from .tool_executor import ToolExecutor

_LOGGER = logging.getLogger(__name__)


class LMStudioConversationAgent(AbstractConversationAgent):
    """LM Studio conversation agent for Home Assistant voice assistant."""

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        return ["en"]

    def __init__(
        self,
        hass: HomeAssistant,
        client: LMStudioClient,
        model_manager: ModelManager,
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
        self._manager = model_manager

    async def async_process(
        self,
        user_input: ConversationInput,
    ) -> ConversationResult:
        """Process a conversation turn."""
        cid = user_input.conversation_id or self.entry_id
        text = user_input.text
        language = user_input.language
        system_prompt = self._entry_data.get(CONF_PROMPT, DEFAULT_PROMPT)
        use_tools = self._entry_data.get(CONF_USE_TOOLS, DEFAULT_USE_TOOLS)
        thinking = self._entry_data.get(CONF_THINKING, DEFAULT_THINKING)
        model = self._router.pick_model(text)

        if model == LIST_MODELS:
            models = await self.client.list_models()
            model_ids = [m["id"] for m in models.get("data", []) if "id" in m]
            speech = f"Available models: {', '.join(model_ids)}"
            intent_response = intent.IntentResponse(language=language)
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

        content = ""
        try:
            content = await self._do_chat(model, messages, use_tools)
        except Exception as err:
            _LOGGER.error("LM Studio chat error: %s", err)
            content = "Sorry, I couldn't reach LM Studio right now."

        if not content:
            content = "I didn't receive a response."

        await self._memory.add(cid, "user", text)
        await self._memory.add(cid, "assistant", content)

        intent_response = intent.IntentResponse(language=language)
        intent_response.async_set_speech(content)

        return ConversationResult(
            response=intent_response,
            conversation_id=cid,
        )

    async def _do_chat(
        self,
        model: str,
        messages: list[dict[str, str]],
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
