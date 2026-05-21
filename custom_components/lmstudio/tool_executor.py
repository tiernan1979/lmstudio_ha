from __future__ import annotations
import json
import logging
import time

from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ToolExecutor:

    def __init__(self, hass: HomeAssistant, entry_id: str):
        self.hass = hass
        self.entry_id = entry_id

    async def execute_tool_calls(self, tool_calls: list) -> list[dict]:
        """Execute tool calls and return results for each."""
        state = self.hass.data[DOMAIN][self.entry_id]
        state["tool_running"] = True

        results = []
        try:
            for call in tool_calls:
                call_id = call["id"]
                name = call["function"]["name"]
                raw_args = call["function"]["arguments"]

                if isinstance(raw_args, str):
                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        _LOGGER.warning(
                            "Could not parse tool args for %s: %r", name, raw_args
                        )
                        results.append({
                            "tool_call_id": call_id,
                            "content": f"Error: could not parse arguments: {raw_args}",
                        })
                        continue
                else:
                    args = raw_args

                state["last_used"] = time.time()

                try:
                    result_text = await self._dispatch(name, args)
                    results.append({
                        "tool_call_id": call_id,
                        "content": result_text,
                    })
                except Exception as err:
                    _LOGGER.error("Tool call '%s' failed: %s", name, err)
                    results.append({
                        "tool_call_id": call_id,
                        "content": f"Error: {err}",
                    })

        finally:
            state["tool_running"] = False
            state["last_used"] = time.time()

        return results

    async def _dispatch(self, name: str, args: dict) -> str:
        if name == "turn_on":
            await self.hass.services.async_call(
                "homeassistant", "turn_on", args
            )
            entity_id = args.get("entity_id", "entity")
            return f"Turned on {entity_id}."

        elif name == "turn_off":
            await self.hass.services.async_call(
                "homeassistant", "turn_off", args
            )
            entity_id = args.get("entity_id", "entity")
            return f"Turned off {entity_id}."

        elif name == "call_service":
            domain = args.get("domain", "")
            service = args.get("service", "")
            data = args.get("data", {})
            await self.hass.services.async_call(domain, service, data)
            return f"Called {domain}.{service} with data: {json.dumps(data)}."

        else:
            _LOGGER.warning("Unknown tool call received: %s with args %s", name, args)
            return f"Error: unknown tool '{name}'."
