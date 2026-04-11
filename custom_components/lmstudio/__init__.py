from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components import conversation

from .client import LMStudioClient
from .conversation import LMStudioAgent
from .model_manager import ModelManager

DOMAIN = "lmstudio"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):

    hass.data.setdefault(DOMAIN, {})

    client = LMStudioClient(entry.data)

    model_manager = ModelManager(hass, client, entry.entry_id)

    agent = LMStudioAgent(
        hass=hass,
        client=client,
        entry_id=entry.entry_id,
        model_manager=model_manager,
    )

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "agent": agent,
        "model": entry.data["model"],
        "system_prompt": entry.data["system_prompt"],
        "idle_timeout": entry.data.get("idle_timeout", 300),
        "last_used": 0,

        # ✅ NEW FLAGS (FROM CONFIG FLOW)
        "streaming": entry.data.get("streaming", True),
        "thinking": entry.data.get("thinking", False),

        "model_manager": model_manager,
    }

    conversation.async_set_agent(hass, entry, agent)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    agent = hass.data[DOMAIN].pop(entry.entry_id, None)
    if agent:
        conversation.async_unset_agent(hass, entry)
    # unload other platforms if you have them
    return True