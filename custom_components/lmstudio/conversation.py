from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .agent import LMStudioAgent
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]

    agent = LMStudioAgent(
        hass=hass,
        client=data["client"],
        entry_id=entry.entry_id,
        model_manager=data["model_manager"],
        entry=entry,
    )

    data["agent"] = agent
    async_add_entities([agent])