from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator, AsyncIterator, Callable
from typing import Any

import voluptuous as vol
from voluptuous_openapi import convert

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.const import CONF_MODEL
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, llm
from homeassistant.helpers.entity import Entity

from .const import (
    CONF_CONTEXT_LENGTH,
    CONF_FLASH_ATTENTION,
    CONF_MAX_HISTORY,
    DEFAULT_CONTEXT_LENGTH,
    DEFAULT_FLASH_ATTENTION,
    DEFAULT_MAX_HISTORY,
    DOMAIN,
)

MAX_TOOL_ITERATIONS = 10

_LOGGER = logging.getLogger(__name__)


def _format_tool(
    tool: llm.Tool, custom_serializer: Callable[[Any], Any] | None
) -> dict[str, Any]:
    tool_spec = {
        "type": "function",
        "function": {
            "name": tool.name,
            "parameters": convert(tool.parameters, custom_serializer=custom_serializer),
        },
    }
    if tool.description:
        tool_spec["function"]["description"] = tool.description
    return tool_spec


def _convert_content(
    chat_content: (
        conversation.Content
        | conversation.ToolResultContent
        | conversation.AssistantContent
    ),
) -> dict[str, Any]:
    if isinstance(chat_content, conversation.ToolResultContent):
        return {
            "role": "tool",
            "content": json.dumps(chat_content.tool_result),
            "tool_call_id": chat_content.tool_call_id,
        }
    if isinstance(chat_content, conversation.AssistantContent):
        msg: dict[str, Any] = {
            "role": "assistant",
            "content": chat_content.content or "",
        }
        if chat_content.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.tool_name,
                        "arguments": json.dumps(tc.tool_args),
                    },
                }
                for tc in chat_content.tool_calls
            ]
        return msg
    if isinstance(chat_content, conversation.UserContent):
        return {
            "role": "user",
            "content": chat_content.content or "",
        }
    if isinstance(chat_content, conversation.SystemContent):
        return {
            "role": "system",
            "content": chat_content.content,
        }
    raise TypeError(f"Unexpected content type: {type(chat_content)}")


async def _transform_stream(
    result: AsyncIterator[dict[str, Any]],
) -> AsyncGenerator[conversation.AssistantContentDeltaDict, None]:
    new_msg = True
    async for event in result:
        chunk: conversation.AssistantContentDeltaDict = {}
        if new_msg:
            chunk["role"] = "assistant"
            new_msg = False
        if event["type"] == "content":
            chunk["content"] = event["content"]
        elif event["type"] == "tool_calls":
            chunk["tool_calls"] = [
                llm.ToolInput(
                    id=tc.get("id", ""),
                    tool_name=tc["function"]["name"],
                    tool_args=tc["function"]["arguments"],
                )
                for tc in event["tool_calls"]
            ]
        elif event["type"] == "done":
            new_msg = True
            continue
        yield chunk


class LmStudioBaseLLMEntity(Entity):

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        config_entry: ConfigEntry,
        subentry: ConfigSubentry,
        client,
        model_manager,
    ) -> None:
        self.entry = config_entry
        self.subentry = subentry
        self.client = client
        self.model_manager = model_manager
        self._attr_unique_id = subentry.subentry_id

        model, _, version = subentry.data[CONF_MODEL].partition(":")
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, subentry.subentry_id)},
            name=subentry.title,
            manufacturer="LM Studio",
            model=model,
            sw_version=version or "latest",
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    async def _async_handle_chat_log(
        self,
        chat_log: conversation.ChatLog,
        structure: vol.Schema | None = None,
    ) -> None:
        settings = {**self.entry.data, **self.subentry.data}
        model = settings[CONF_MODEL]
        context_length = int(settings.get(CONF_CONTEXT_LENGTH, DEFAULT_CONTEXT_LENGTH))
        flash_attention = settings.get(CONF_FLASH_ATTENTION, DEFAULT_FLASH_ATTENTION)

        await self.model_manager.ensure_model(
            model,
            context_length=context_length,
            flash_attention=flash_attention,
        )

        tools: list[dict[str, Any]] | None = None
        if chat_log.llm_api:
            tools = [
                _format_tool(tool, chat_log.llm_api.custom_serializer)
                for tool in chat_log.llm_api.tools
            ]

        messages = [_convert_content(c) for c in chat_log.content]
        max_messages = int(settings.get(CONF_MAX_HISTORY, DEFAULT_MAX_HISTORY))
        self._trim_history(messages, max_messages)

        if structure:
            output_format = convert(
                structure,
                custom_serializer=(
                    chat_log.llm_api.custom_serializer
                    if chat_log.llm_api
                    else llm.selector_serializer
                ),
            )
            messages[-1]["content"] = (
                messages[-1].get("content", "")
                + "\n\nReturn in JSON format matching this schema: "
                + json.dumps(output_format)
            )

        max_tokens = int(settings.get(CONF_CONTEXT_LENGTH, DEFAULT_CONTEXT_LENGTH))

        for _iteration in range(MAX_TOOL_ITERATIONS):
            try:
                result = self.client.chat_completions(
                    model=model,
                    messages=list(messages),
                    tools=tools,
                    max_tokens=max_tokens,
                )
            except Exception as err:
                _LOGGER.error("Error talking to LM Studio: %s", err)
                raise HomeAssistantError(
                    f"Sorry, I had a problem talking to LM Studio: {err}"
                ) from err

            new_contents = [
                content
                async for content in chat_log.async_add_delta_content_stream(
                    self.entity_id, _transform_stream(result)
                )
            ]
            messages.extend(_convert_content(c) for c in new_contents)

            if not chat_log.unresponded_tool_results:
                break

    def _trim_history(
        self, messages: list[dict], max_messages: int
    ) -> None:
        if max_messages < 1:
            return
        user_msgs = sum(1 for m in messages if m.get("role") == "user")
        num_previous_rounds = user_msgs - 1
        if num_previous_rounds >= max_messages:
            num_keep = 2 * max_messages + 1
            drop_index = len(messages) - num_keep
            messages[:] = [
                messages[0],
                *messages[drop_index:],
            ]
