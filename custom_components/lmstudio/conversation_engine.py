from homeassistant.components import conversation


async def async_get_engine(hass, config_entry):
    """Return conversation engine per config entry (Ollama-style behavior)."""

    return hass.data["lmstudio"][config_entry.entry_id]["agent"]