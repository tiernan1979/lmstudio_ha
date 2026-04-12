import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .client import LMStudioClient
from .model_manager import ModelManager
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["conversation"]


def _get_entry_config(entry: ConfigEntry) -> dict:
    """Merge entry.options over entry.data so options flow values take precedence."""
    return {**entry.data, **entry.options}


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register domain-level services once."""
    from .services import async_setup_services
    await async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    config = _get_entry_config(entry)

    try:
        client = LMStudioClient(config)
        model_manager = ModelManager(hass, client, entry.entry_id)
    except Exception as err:
        _LOGGER.error("Failed to initialise LM Studio: %s", err)
        return False

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "model_manager": model_manager,
        "model": config["model"],
        "system_prompt": config.get("system_prompt", "You are a helpful smart home assistant."),
        "streaming": config.get("streaming", True),
        "thinking": config.get("thinking", False),
        "idle_timeout": config.get("idle_timeout", 5),
        "last_used": 0,
    }

    # Reload entry when user saves new options
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("LM Studio entry set up: %s", entry.entry_id)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry_data = hass.data[DOMAIN].pop(entry.entry_id, {})
        mm = entry_data.get("model_manager")
        if mm:
            mm.stop()
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Triggered when options are saved — full reload to pick up new config."""
    await hass.config_entries.async_reload(entry.entry_id)