from __future__ import annotations
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        LMStudioModelSelect(
            hass=hass,
            client=data["client"],
            model_manager=data["model_manager"],
            entry_id=entry.entry_id,
            entry=entry,
        )
    ])


class LMStudioModelSelect(SelectEntity):
    """Dropdown to select and load models from LM Studio."""

    _attr_has_entity_name = True
    _attr_name = "Model"
    _attr_icon = "mdi:list-box-outline"

    def __init__(self, hass, client, model_manager, entry_id: str, entry: ConfigEntry):
        self.hass = hass
        self.client = client
        self.model_manager = model_manager
        self.entry_id = entry_id
        self._entry = entry
        self._attr_options = []
        self._attr_current_option = entry.data.get("model", "")
        self._attr_unique_id = f"{entry.entry_id}_model_select"

    async def async_added_to_hass(self) -> None:
        await self._refresh_options()

    async def _refresh_options(self) -> None:
        try:
            result = await self.client.list_models()
            model_ids = [m["id"] for m in result.get("data", []) if "id" in m]
            if model_ids:
                self._attr_options = model_ids
                if self._attr_current_option not in model_ids:
                    self._attr_current_option = model_ids[0]
                self.async_write_ha_state()
        except Exception as err:
            _LOGGER.warning("Could not refresh model list: %s", err)

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        state = self.hass.data[DOMAIN][self.entry_id]
        state["model"] = option
        try:
            await self.model_manager.ensure_model(option)
        except Exception as err:
            _LOGGER.error("Failed to load model %s: %s", option, err)
        self.hass.config_entries.async_update_entry(
            self._entry,
            data={**self._entry.data, "model": option},
        )
        self.async_write_ha_state()
