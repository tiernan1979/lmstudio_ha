"""Conversation platform for LM Studio."""

import dataclasses
from typing import Literal

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LLM_HASS_API, CONF_PROMPT, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import intent
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_SHOW_TOOL_CALLS, DEFAULT_SHOW_TOOL_CALLS, DOMAIN
from .entity import LmStudioBaseLLMEntity


def _strip_tool_content(chat_log: conversation.ChatLog) -> None:
    stripped: list[conversation.Content] = []
    for c in chat_log.content:
        if isinstance(c, conversation.ToolResultContent):
            continue
        if isinstance(c, conversation.AssistantContent) and c.tool_calls:
            stripped.append(dataclasses.replace(c, tool_calls=None))
            continue
        stripped.append(c)
    chat_log.content = stripped


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    for subentry in config_entry.subentries.values():
        if subentry.subentry_type != "conversation":
            continue

        async_add_entities(
            [LmStudioConversationEntity(config_entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class LmStudioConversationEntity(
    conversation.ConversationEntity,
    conversation.AbstractConversationAgent,
    LmStudioBaseLLMEntity,
):

    _attr_supports_streaming = True

    def __init__(self, entry: ConfigEntry, subentry) -> None:
        runtime = entry.runtime_data
        super().__init__(
            entry, subentry,
            client=runtime["client"],
            model_manager=runtime["model_manager"],
        )
        if subentry.data.get(CONF_LLM_HASS_API):
            self._attr_supported_features = (
                conversation.ConversationEntityFeature.CONTROL
            )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self.entry, self)

    async def async_will_remove_from_hass(self) -> None:
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        return MATCH_ALL

    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        settings = {**self.entry.data, **self.subentry.data}
        hide_tools = not settings.get(CONF_SHOW_TOOL_CALLS, DEFAULT_SHOW_TOOL_CALLS)

        try:
            await chat_log.async_provide_llm_data(
                user_input.as_llm_context(DOMAIN),
                settings.get(CONF_LLM_HASS_API),
                settings.get(CONF_PROMPT),
                user_input.extra_system_prompt,
            )
        except conversation.ConverseError as err:
            return err.as_conversation_result()

        try:
            await self._async_handle_chat_log(chat_log)
        except HomeAssistantError:
            if not hide_tools:
                raise

        if hide_tools:
            _strip_tool_content(chat_log)
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.response_type = intent.IntentResponseType.QUERY_ANSWER

            last_content = chat_log.content[-1]
            if isinstance(last_content, conversation.AssistantContent) and last_content.content:
                intent_response.async_set_speech(last_content.content)
            else:
                intent_response.async_set_speech(
                    "Sorry, I had trouble processing your request. Please try again."
                )

            result = conversation.ConversationResult(
                response=intent_response,
                conversation_id=chat_log.conversation_id,
                continue_conversation=False,
            )
        else:
            result = conversation.async_get_result_from_chat_log(user_input, chat_log)

        return result
