from __future__ import annotations
import logging
from typing import Any

from homeassistant.config_entries import ConfigFlow, ConfigSchema, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.strings import async_translate

from .const import CONF_URL, CONF_API_KEY, DOMAIN

_LOGGER = logging.getLogger(__name__)


class LMStudioConfigFlow(ConfigFlow):
    """Configuration flow for LM Studio integration."""

    DOMAIN = DOMAIN

    async def async_step_user(self, hass: HomeAssistant) -> ConfigFlowResult:
        """First step: ask for server URL and API (optional)."""
        return self.async_step_url()

    async def async_step_url(self, hass: HomeAssistant) -> ConfigFlowResult:
        """Second step: ask for LM Studio URL."""
        schema = ConfigSchema({
            CONF_URL: str,
        })
        
        return self.async_show_form(
            step_id="url",
            schema=schema,
            description="Enter the URL of your LM Studio server (e.g., http://localhost:1234)."
        )

    async def async_step_api_key(self, hass: HomeAssistant) -> ConfigFlowResult:
        """Third step: ask for API key (optional)."""
        schema = ConfigSchema({
            CONF_API_KEY: str,
        })
        
        return self.async_show_form(
            step_id="api_key",
            schema=schema,
            description="Enter your LM Studio API key if you have one (optional)."
        )

    async def async_step_confirm(self, hass: HomeAssistant) -> ConfigFlowResult:
        """Final step: confirm configuration."""
        if self.user_input.get(CONF_URL):
            hass.data[DOMAIN][self.entry_id] = {
                "client": None,  # Will be initialized in __init__.py
                "data": dict(self.user_input),
            }
            return self.async_create_entry(
                title=f"LM Studio ({self.user_input[CONF_URL]})",
                data=dict(self.user_input),
            )
        else:
            return self.async_abort()
