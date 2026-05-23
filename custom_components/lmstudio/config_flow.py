"""Config flow for LM Studio integration."""

import logging
import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigEntry, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
)

from .const import (
    DOMAIN,
    CONF_URL,
    CONF_API_KEY,
    CONF_MODEL,
    CONF_PROMPT,
    CONF_IDLE_TIMEOUT,
    CONF_USE_TOOLS,
    DEFAULT_PROMPT,
    DEFAULT_IDLE_TIMEOUT,
    DEFAULT_USE_TOOLS,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_URL, default="http://localhost:1234"): str,
    vol.Optional(CONF_API_KEY, default=""): str,
})

class LMStudioConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configuration flow for LM Studio integration."""

    VERSION = 1

    def __init__(self):
        self._data = {}
        self._models = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        return LMStudioOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            api_key = user_input.get(CONF_API_KEY, "")

            ok = await self._test_connection(url, api_key)
            if not ok:
                errors["base"] = "cannot_connect"
            else:
                self._models = await self._fetch_models(url)
                if not self._models:
                    errors["base"] = "no_models"
                else:
                    self._data.update(user_input)
                    self._data[CONF_URL] = url
                    return await self.async_step_options()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_options(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        """Handle the options step."""
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(
                title=f"LM Studio ({user_input[CONF_MODEL]})",
                data=self._data,
            )

        schema = vol.Schema({
             vol.Required(CONF_MODEL, default=self._models.get(next(iter(self._models), ""), "")): vol.In(self._models),
             vol.Required(
                 CONF_PROMPT,
                 default=DEFAULT_PROMPT,
             ): TextSelector(
                 TextSelectorConfig(multiline=True)
             ),
             vol.Optional(
                 CONF_IDLE_TIMEOUT,
                 default=DEFAULT_IDLE_TIMEOUT,
             ): vol.All(int, vol.Range(min=1, max=1440)),
             vol.Optional("streaming", default=True): bool,
             vol.Optional("thinking", default=False): bool,
             vol.Optional(CONF_USE_TOOLS, default=DEFAULT_USE_TOOLS): bool,
        })

        return self.async_show_form(
            step_id="options",
            data_schema=schema,
            description_placeholders={"model_count": str(len(self._models))},
        )

    async def _fetch_models(self, url: str) -> dict[str, str]:
        """Fetch models from the server."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}/v1/models") as resp:
                    if resp.status != 200:
                        return {}
                    data = await resp.json()
                    return {
                        m["id"]: m[ "id"]
                        for m in data.get("data", [])
                        if "id" in m
                    }
        except Exception:
            return {}

    async def _test_connection(self, url: str, api_key: str = "") -> bool:
        """Test connection to the server."""
        try:
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(
                    f"{url}/v1/models", headers=headers
                ) as resp:
                    if resp.status != 200:
                        return False
                    data = await resp.json()
                    return isinstance(data, dict) and "data" in data
        except Exception:
            return False


class LMStudioOptionsFlow(OptionsFlow):
    """Options flow for LM Studio integration."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> dict[str[str, Any]]:
        """Fetch current models from the server then show the options form."""
        url = self.config_entry.data.get(CONF_URL, "").rstrip("/")
        models = await self._fetch_models(url)

        if not models:
            current_model = self.config_entry.data.get(CONF_MODEL, "")
            models = {current_model: current_model}

        self._models = models
        return await self.async_step_options()

    async def async_step_options(self, user_input: dict[str, Any] | None = None) -> dict[str, Any]:
        """Handle the options step."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}

        schema = vol.Schema({
             vol.Required(CONF_MODEL, default=current.get(CONF_MODEL, "")): vol.In(self._models),
             vol.Required(
                 CONF_PROMPT,
                 default=current.get(CONF_PROMPT, DEFAULT_PROMPT),
             ): TextSelector(
                 TextSelectorConfig(multiline=True)
             ),
             vol.Optional(
                 CONF_IDLE_TIMEOUT,
                 default=current.get(CONF_IDLE_TIMEOUT, DEFAULT_IDLE_TIMEOUT),
             ): vol.All(int, vol.Range(min=1, max=1440)),
             vol.Optional("streaming", default=current.get("streaming", True)): bool,
             vol.Optional("thinking", default=current.get("thinking", False)): bool,
             vol.Optional(CONF_USE_TOOLS, default=current.get(CONF_USE_TOOLS, DEFAULT_USE_TOOLS)): bool,
        })

        return self.async_show_form(
            step_id="options",
            data_schema=schema,
        )

    async def _fetch_models(self, url: str) -> dict[str, str]:
        """Fetch models from the server."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}/v1/models") as resp:
                    if resp.status != 200:
                        return {}
                    data = await resp.json()
                    return {
                        m["id"]: m["id"]
                        for m in data.get("data", [])
                        if "id" in m
                    }
        except Exception:
            return {}
