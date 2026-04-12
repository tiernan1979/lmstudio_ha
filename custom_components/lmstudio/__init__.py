import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components import conversation

from .client import LMStudioClient
from .agent import LMStudioAgent
from .model_manager import ModelManager
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    try:
        client = LMStudioClient(entry.data)
        model_manager = ModelManager(hass, client, entry.entry_id)
        agent = LMStudioAgent(
            hass=hass,
            client=client,
            entry_id=entry.entry_id,
            model_manager=model_manager,
        )
    except Exception as err:
        _LOGGER.error("Failed to initialise LM Studio integration: %s", err)
        return False

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "agent": agent,
        "model_manager": model_manager,
    }

    from .services import async_setup_services

    async def async_setup(hass: HomeAssistant, config: dict) -> bool:
        """Called once when the integration domain loads."""
        await async_setup_services(hass)
        return True
    
    agent.async_set_agent(hass, entry, agent)
    _LOGGER.debug("LM Studio conversation agent registered for entry %s", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    agent.async_unset_agent(hass, entry)
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True