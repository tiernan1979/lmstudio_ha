from __future__ import annotations
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.components.conversation import ConversationContext
from .client import LMStudioClient

_LOGGER = logging.getLogger(__name__)


class ToolExecutor:
    """Executes tools requested by the LLM using Home Assistant entities."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self.hass = hass
        self.entry_id = entry_id

    async def execute_tool_calls(self, tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Execute a list of tool calls."""
        results: list[dict[str, Any]] = []

        for call in tool_calls:
            name = call.get("function", {}).get("name")
            args = call.get("function", {}).get("arguments", {})

            if name == "get_state":
                results.append(await self._get_state(args))
            else:
                _LOGGER.warning("Unknown tool call: %s", name)
                results.append({"tool_call_id": call["id"], "content": "I don't know how to do that."})

        return results

    async def _get_state(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get the state of requested entities."""
        entity_ids = args.get("entity_id", "")
        if isinstance(entity_ids, str):
            entity_ids = [e.strip() for e in entity_ids.split(",") if e.strip()]

        results: list[dict[str, Any]] = []
        for eid in entity_ids:
            try:
                state = self.hass.states.get(eid)
                if state is None:
                    content = f"Entity {eid} not found."
                else:
                    content = f"{eid} is {state}"
                results.append({"tool_call_id": "internal", "content": content})
            except Exception as err:
                _LOGGER.error("Error getting state for %s: %s", eid, err)
                results.append({"tool_call_id": "internal", "content": "Error retrieving state."})

        return {"results": results}
