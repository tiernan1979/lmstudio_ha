from __future__ import annotations

import json
import logging
from datetime import datetime
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
    CONF_IDLE_TIMEOUT,
    CONF_MAX_HISTORY,
    CONF_STREAMING,
    DEFAULT_CONTEXT_LENGTH,
    DEFAULT_FLASH_ATTENTION,
    DEFAULT_IDLE_TIMEOUT,
    DEFAULT_MAX_HISTORY,
    DEFAULT_STREAMING,
    DOMAIN,
)

MAX_TOOL_ITERATIONS = 3

_LOGGER = logging.getLogger(__name__)

BUILTIN_TOOLS = {
    "get_current_time": {
        "description": "Get the current date and time in the user's timezone. Returns the current time, date, and timezone.",
        "parameters": {"type": "object", "properties": {}},
    },
    "get_current_date": {
        "description": "Get the current date. Returns today's date.",
        "parameters": {"type": "object", "properties": {}},
    },
    "get_live_context": {
        "description": "Search for all Home Assistant entities in a given domain (e.g. 'light', 'switch', 'sensor', 'climate'). Returns each entity's ID, state, and friendly name. Use this to discover entities before controlling them.",
        "parameters": {
            "type": "object",
            "properties": {
                "domain": {
                    "type": "string",
                    "description": "The entity domain to search (e.g., 'light', 'switch', 'sensor', 'climate', 'cover', 'lock')"
                }
            },
            "required": ["domain"],
        },
    },
}


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


def _format_builtin_tool(name: str, spec: dict) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": spec["description"],
            "parameters": spec["parameters"],
        },
    }


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


def _is_builtin_tool_error(content, tool_name: str) -> bool:
    if not isinstance(content, conversation.ToolResultContent):
        return False
    result = content.tool_result
    if isinstance(result, dict):
        err = result.get("error_text", "") or ""
        return f'Tool "{tool_name}" not found' in err
    return False


def _execute_builtin_tool(tool_name: str, args: dict, hass) -> dict:
    now = datetime.now()
    if tool_name == "get_current_time":
        return {
            "current_time": now.strftime("%I:%M %p"),
            "current_date": now.strftime("%A, %B %d, %Y"),
            "timezone": str(hass.config.time_zone),
        }
    if tool_name == "get_current_date":
        return {
            "date": now.strftime("%A, %B %d, %Y"),
        }
    if tool_name == "get_live_context":
        domain = args.get("domain", "").lower()
        entities = []
        for state in hass.states.async_all():
            if state.domain == domain:
                entities.append({
                    "entity_id": state.entity_id,
                    "state": state.state,
                    "name": state.attributes.get("friendly_name", state.entity_id),
                })
        return {
            "domain": domain,
            "count": len(entities),
            "entities": entities,
        }
    return {"error": f"Unknown builtin tool: {tool_name}"}


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
        hass = self.hass
        settings = {**self.entry.data, **self.subentry.data}
        model = settings[CONF_MODEL]
        context_length = int(settings.get(CONF_CONTEXT_LENGTH, DEFAULT_CONTEXT_LENGTH))
        flash_attention = settings.get(CONF_FLASH_ATTENTION, DEFAULT_FLASH_ATTENTION)
        streaming = settings.get(CONF_STREAMING, DEFAULT_STREAMING)
        idle_timeout = int(settings.get(CONF_IDLE_TIMEOUT, DEFAULT_IDLE_TIMEOUT))

        await self.model_manager.ensure_model(
            model,
            context_length=context_length,
            flash_attention=flash_attention,
            idle_timeout_minutes=idle_timeout,
        )

        ha_tools: list[dict[str, Any]] = []
        if chat_log.llm_api:
            ha_tools = [
                _format_tool(tool, chat_log.llm_api.custom_serializer)
                for tool in chat_log.llm_api.tools
            ]
            _LOGGER.debug(
                "HA tools available: %s",
                [t["function"]["name"] for t in ha_tools],
            )

        builtin_tools = [
            _format_builtin_tool(name, spec)
            for name, spec in BUILTIN_TOOLS.items()
        ]
        tools = ha_tools + builtin_tools if ha_tools else None

        messages = [_convert_content(c) for c in chat_log.content]
        if not tools:
            system_msgs = [m for m in messages if m.get("role") == "system"]
            no_tool_hint = (
                "You do NOT have access to any tools or function calling. "
                "Only respond with natural language text."
            )
            if system_msgs:
                system_msgs[-1]["content"] = (
                    (system_msgs[-1].get("content") or "") + "\n\n" + no_tool_hint
                )
            else:
                messages.insert(0, {"role": "system", "content": no_tool_hint})
        else:
            now = datetime.now()
            time_context = (
                f"\n\nCurrent date and time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}\n"
                f"Timezone: {hass.config.time_zone}\n"
            )
            system_msgs = [m for m in messages if m.get("role") == "system"]
            if system_msgs:
                system_msgs[-1]["content"] = (
                    (system_msgs[-1].get("content") or "") + time_context
                )

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
                    stream=streaming,
                )
            except Exception as err:
                _LOGGER.error("Error talking to LM Studio: %s", err)
                raise HomeAssistantError(
                    f"Sorry, I had a problem talking to LM Studio: {err}"
                ) from err

            new_contents = [
                c
                async for c in chat_log.async_add_delta_content_stream(
                    self.entity_id, _transform_stream(result)
                )
            ]

            for i, content in enumerate(new_contents):
                for tool_name in BUILTIN_TOOLS:
                    if _is_builtin_tool_error(content, tool_name):
                        tc_id = content.tool_call_id
                        tc_args_str = ""
                        for prev in new_contents[:i]:
                            if isinstance(prev, conversation.AssistantContent):
                                for tc in (prev.tool_calls or []):
                                    if tc.id == tc_id:
                                        tc_args_str = json.dumps(tc.tool_args)
                        try:
                            tc_args = json.loads(tc_args_str) if tc_args_str else {}
                        except json.JSONDecodeError:
                            tc_args = {}
                        result_data = _execute_builtin_tool(tool_name, tc_args, hass)
                        new_contents[i] = conversation.ToolResultContent(
                            tool_call_id=tc_id,
                            tool_result=result_data,
                        )
                        _LOGGER.debug("Executed builtin tool %s", tool_name)

            messages.extend(_convert_content(c) for c in new_contents)

            if not chat_log.unresponded_tool_results:
                break
        else:
            _LOGGER.error("Tool call iteration limit (%d) exceeded", MAX_TOOL_ITERATIONS)
            raise HomeAssistantError(
                "The model did not complete its response within the allowed number of tool call rounds. "
                "Try asking a simpler question or check the model's tool use capabilities."
            )

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
