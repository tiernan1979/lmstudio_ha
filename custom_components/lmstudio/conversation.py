from __future__ import annotations
import logging
from typing import Any

from homeassistant.components.conversation import async_get_manager
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .agent import LMStudioConversationAgent
from .client import LMStudioClient
from .const import CONF_API_KEY, CONF_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Set up the conversation platform."""
    state = hass.data[DOMAIN][entry.entry_id]
    client: LMStudioClient = state["client"]

    agent = LMStudioConversationAgent(
        hass=hass,
        client=client,
        entry_id=entry.entry_id,
        entry_data=state["data"],
    )

    manager = async_get_manager(hass)
    await manager.async_register_agent(agent)
    entry.async_on_unload(
        lambda: asyncio.create_task(manager.async_unregister_agent(agent))
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the conversation platform."""
    state = hass.data[DOMAIN].get(entry.entry_id)
    if not state:
        return False

    client: LMStudioClient = state["client"]
    agent = LMStudioConversationAgent(
        hass=hass,
        client=client,
        entry_id=entry.entry_id,
        entry_data=state["data"],
    )

    manager = async_get_manager(hass)
    await manager.async_unregister_agent(agent)
    return True
