from __future__ import annotations
import logging
from typing import Any

from homeassistant.components.conversation import (
    AbstractConversationAgent,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .client import LMStudioClient
from .const import CONF_API_KEY, CONF_MODEL, CONF_URL, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the LM Studio integration from yaml (not required)."""
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Set up a config entry."""
    client = LMStudioClient({
        "url": entry.data[CONF_URL],
        "api_key": entry.data.get(CONF_API_KEY, ""),
    })

    available = await client.is_available()
    if not available:
        _LOGGER.warning(
            "LM Studio server at %s is not reachable. "
            "The integration will still be set up but requests may fail.",
            entry.data[CONF_URL],
        )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "data": dict(entry.data),
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    agent = _create_agent(hass, client, entry)
    manager = hass.components.conversation.async_get_manager(hass)
    await manager.async_register_agent(agent)

    entry.async_on_unload(
        lambda: asyncio.create_task(manager.async_unregister_agent(agent))
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    state = hass.data[DOMAIN].pop(entry.entry_id, None)
    if state and "client" in state:
        await state["client"].close()

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    state = hass.data[DOMAIN].pop(entry.entry_id, None)
    if state and "client" in state:
        await state["client"].close()


def _create_agent(
    hass: HomeAssistant, client: LMStudioClient, entry: ConfigEntry
) -> AbstractConversationAgent:
    """Create the conversation agent for this config entry."""
    from .agent import LMStudioConversationAgent

    return LMStudioConversationAgent(
        hass=hass,
        client=client,
        entry_id=entry.entry_id,
        entry_data=dict(entry.data),
    )
