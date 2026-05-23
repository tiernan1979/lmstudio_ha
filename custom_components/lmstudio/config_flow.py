"""Config flow for LM Studio integration."""

from __future__ import annotations
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
)

from .const import CONF_API_KEY, CONF_MODEL, CONF_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_URL, default="http://localhost:1234"): TextSelector(
        TextSelectorConfig(type="url")
    ),
    vol.Optional(CONF_API_KEY): TextSelector(
        TextSelectorConfig(type="password")
    ),
})


class LMStudioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configuration flow for LM Studio integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            user_input[CONF_URL] = url

            if not url.startswith("http://") and not url.startswith("https://"):
                errors[CONF_URL] = "invalid_url"
            else:
                return self.async_create_entry(
                    title=f"LM Studio ({url})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
