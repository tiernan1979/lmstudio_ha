from homeassistant.components import conversation as ha_conversation  # ← alias it
from .agent import LMStudioAgent
from .const import DOMAIN
from .model_manager import ModelManager
from .client import LMStudioClient
import logging as _LOGGER


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    try:
        client = LMStudioClient(entry.data)
        model_manager = ModelManager(hass, client, entry.entry_id)
        lmstudio_agent = LMStudioAgent(      # ← renamed variable
            hass=hass,
            client=client,
            entry_id=entry.entry_id,
            model_manager=model_manager,
        )
    except Exception as err:
        _LOGGER.error("Failed to initialise LM Studio: %s", err)
        return False

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "agent": lmstudio_agent,
        "model_manager": model_manager,
        "model": entry.data["model"],
        "system_prompt": entry.data["system_prompt"],
        "streaming": entry.data.get("streaming", True),
        "thinking": entry.data.get("thinking", False),
        "idle_timeout": entry.data.get("idle_timeout", 5),
        "last_used": 0,
    }

    ha_conversation.async_set_agent(hass, entry, lmstudio_agent)  # ← uses alias
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    ha_conversation.async_unset_agent(hass, entry)
    entry_data = hass.data[DOMAIN].pop(entry.entry_id, {})
    mm = entry_data.get("model_manager")
    if mm:
        mm.stop()
    return True