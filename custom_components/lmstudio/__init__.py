from .api import LMStudioClient
from .conversation import LMStudioAgent
from .const import DOMAIN, CONF_IDLE_TIMEOUT


async def async_setup_entry(hass, entry):
    client = LMStudioClient(entry.data["url"])

    hass.data[DOMAIN] = {
        "client": client,
        "selected_model": entry.data["model"],
        "loaded_model": None,
        "system_prompt": entry.data["system_prompt"],

        "streaming": entry.data.get("streaming", True),
        "thinking": entry.data.get("thinking", False),

        # 🧠 NEW
        "idle_timeout": entry.data.get(CONF_IDLE_TIMEOUT, 5),
        "last_used": 0,
    }

    hass.data[DOMAIN]["manager"] = None  # set later

    agent = LMStudioAgent(hass, client)
    hass.data["conversation"] = agent

    return True