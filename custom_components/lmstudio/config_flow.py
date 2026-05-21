import voluptuous as vol
import aiohttp

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_URL,
    CONF_MODEL,
    CONF_PROMPT,
    CONF_IDLE_TIMEOUT,
    DEFAULT_IDLE_TIMEOUT,
    DEFAULT_PROMPT,
)


class LMStudioConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    VERSION = 1

    def __init__(self):
        self._data = {}
        self._models = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return LMStudioOptionsFlow()

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            api_key = user_input.get("api_key", "")

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
            data_schema=self._connection_schema(),
            errors=errors,
        )

    async def async_step_options(self, user_input=None):
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(
                title=f"LM Studio ({user_input[CONF_MODEL]})",
                data=self._data,
            )

        schema = vol.Schema({
             vol.Required(CONF_MODEL): vol.In(self._models),
             vol.Required(
                 CONF_PROMPT,
                 default=DEFAULT_PROMPT,
             ): selector.TextSelector(
                 selector.TextSelectorConfig(multiline=True)
             ),
             vol.Optional(
                 CONF_IDLE_TIMEOUT,
                 default=DEFAULT_IDLE_TIMEOUT,
             ): vol.All(int, vol.Range(min=1, max=1440)),
             vol.Optional("streaming", default=True): bool,
             vol.Optional("thinking", default=False): bool,
        })

        return self.async_show_form(
            step_id="options",
            data_schema=schema,
            description_placeholders={"model_count": str(len(self._models))},
        )

    def _connection_schema(self):
        return vol.Schema({
            vol.Required(CONF_URL, default="http://localhost:1234"): str,
            vol.Optional("api_key", default=""): str,
        })

    async def _fetch_models(self, url):
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

    async def _test_connection(self, url, api_key=None):
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


class LMStudioOptionsFlow(config_entries.OptionsFlow):

    async def async_step_init(self, user_input=None):
        """Fetch current models from the server then show the options form."""
        url = self.config_entry.data.get(CONF_URL, "").rstrip("/")
        models = await self._fetch_models(url)

        if not models:
            current_model = self.config_entry.data.get(CONF_MODEL, "")
            models = {current_model: current_model}

        self._models = models
        return await self.async_step_options()

    async def async_step_options(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}

        schema = vol.Schema({
             vol.Required(CONF_MODEL, default=current.get(CONF_MODEL)): vol.In(self._models),
             vol.Required(
                 CONF_PROMPT,
                 default=current.get(CONF_PROMPT, DEFAULT_PROMPT),
             ): selector.TextSelector(
                 selector.TextSelectorConfig(multiline=True)
             ),
             vol.Optional(
                 CONF_IDLE_TIMEOUT,
                 default=current.get(CONF_IDLE_TIMEOUT, DEFAULT_IDLE_TIMEOUT),
             ): vol.All(int, vol.Range(min=1, max=1440)),
             vol.Optional("streaming", default=current.get("streaming", True)): bool,
             vol.Optional("thinking", default=current.get("thinking", False)): bool,
        })

        return self.async_show_form(
            step_id="options",
            data_schema=schema,
        )

    async def _fetch_models(self, url):
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
