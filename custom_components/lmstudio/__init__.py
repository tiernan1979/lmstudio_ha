"""LM Studio integration for Home Assistant."""

from __future__ import annotations
import asyncio
import logging
from typing import Any

from homeassistant.components.conversation import (
    async_set_agent,
    async_unset_agent,
)
from homeassistant.components.conversation.models import (
    AbstractConversationAgent,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .client import LMStudioClient
from .const import CONF_API_KEY, CONF_MODEL, CONF_URL, DOMAIN, PLATFORMS
from .model_manager import ModelManager
from .services import async_setup_services

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the LM Studio integration from yaml (not required)."""
    hass.data.setdefault(DOMAIN, {})
    await async_setup_services(hass)
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

    model_manager = ModelManager(hass, client, entry.entry_id)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "data": dict(entry.data),
        "model_manager": model_manager,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    agent = _create_agent(hass, client, model_manager, entry)
    hass.data[DOMAIN][entry.entry_id]["agent"] = agent
    async_set_agent(hass, entry, agent)

    entry.async_on_unload(
        lambda: async_unset_agent(hass, entry)
    )

    await _async_setup_ai_task_entity(hass, client, model_manager, entry)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    state = hass.data[DOMAIN].pop(entry.entry_id, None)
    if state:
        if "model_manager" in state:
            state["model_manager"].stop()
        if "client" in state:
            await state["client"].close()
        if "ai_task_entity" in state:
            await _async_remove_ai_task_entity(hass, state["ai_task_entity"])

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle removal of an entry."""
    state = hass.data[DOMAIN].pop(entry.entry_id, None)
    if state:
        if "model_manager" in state:
            state["model_manager"].stop()
        if "client" in state:
            await state["client"].close()


def _create_agent(
    hass: HomeAssistant,
    client: LMStudioClient,
    model_manager: ModelManager,
    entry: ConfigEntry,
) -> AbstractConversationAgent:
    """Create the conversation agent for this config entry."""
    from .agent import LMStudioConversationAgent

    return LMStudioConversationAgent(
        hass=hass,
        client=client,
        model_manager=model_manager,
        entry_id=entry.entry_id,
        entry_data=dict(entry.data),
    )


async def _async_setup_ai_task_entity(
    hass: HomeAssistant,
    client: LMStudioClient,
    model_manager: ModelManager,
    entry: ConfigEntry,
) -> None:
    """Register the AI Task entity if the ai_task integration is loaded."""
    try:
        from homeassistant.components.ai_task.const import DATA_COMPONENT
        from homeassistant.helpers.entity_component import EntityComponent
        from homeassistant.components.ai_task.entity import AITaskEntity

        from .ai_task_entity import LMStudioAITaskEntity

        component: EntityComponent[AITaskEntity] = hass.data.get(DATA_COMPONENT)
        if component is None:
            _LOGGER.debug(
                "ai_task integration not loaded, skipping AI Task entity registration"
            )
            return

        entity = LMStudioAITaskEntity(
            hass=hass,
            client=client,
            model_manager=model_manager,
            entry_id=entry.entry_id,
            entry_data=dict(entry.data),
        )
        await component.async_add_entities([entity])

        hass.data[DOMAIN][entry.entry_id]["ai_task_entity"] = entity
        _LOGGER.debug("Registered LM Studio AI Task entity")
    except Exception as err:
        _LOGGER.warning("Failed to register AI Task entity: %s", err)


async def _async_remove_ai_task_entity(
    hass: HomeAssistant, entity: Any
) -> None:
    """Remove the AI Task entity."""
    try:
        from homeassistant.components.ai_task.const import DATA_COMPONENT
        from homeassistant.helpers.entity_component import EntityComponent
        from homeassistant.components.ai_task.entity import AITaskEntity

        component: EntityComponent[AITaskEntity] = hass.data.get(DATA_COMPONENT)
        if component is not None:
            await component.async_remove_entity(entity.entity_id)
    except Exception as err:
        _LOGGER.debug("Error removing AI Task entity: %s", err)
