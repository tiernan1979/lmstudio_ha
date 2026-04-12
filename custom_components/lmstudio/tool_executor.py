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

    async def execute_tool_calls(self, tool_calls: list) -> None:
        state = self.hass.data[DOMAIN][self.entry_id]
        state["tool_running"] = True

        try:
            for call in tool_calls:
                name = call["function"]["name"]
                raw_args = call["function"]["arguments"]

                # LLM returns arguments as a JSON string
                if isinstance(raw_args, str):
                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        _LOGGER.warning("Could not parse tool args for %s: %r", name, raw_args)
                        continue
                else:
                    args = raw_args

                state["last_used"] = time.time()

                try:
                    await self._dispatch(name, args)
                except Exception as err:
                    _LOGGER.error("Tool call %s failed: %s", name, err)

        finally:
            state["tool_running"] = False
            state["last_used"] = time.time()

    async def _dispatch(self, name: str, args: dict) -> None:
        if name == "turn_on":
            await self.hass.services.async_call(
                "homeassistant", "turn_on", args
            )

        elif name == "turn_off":
            await self.hass.services.async_call(
                "homeassistant", "turn_off", args
            )

        elif name == "call_service":
            await self.hass.services.async_call(
                args["domain"],
                args["service"],
                args.get("data", {}),
            )

        else:
            _LOGGER.warning("Unknown tool call: %s", name)