import voluptuous as vol
import aiohttp

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_URL,
    CONF_MODEL,
    CONF_PROMPT,
    CONF_IDLE_TIMEOUT,
    DEFAULT_IDLE_TIMEOUT,
)


class LMStudioConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    VERSION = 1

    def __init__(self):
        self.data = {}
        self.models = {}

    # ─────────────────────────────
    # STEP 1: CONNECTION
    # ─────────────────────────────
    async def async_step_user(self, user_input=None):

        if user_input is not None:
            self.data.update(user_input)

            ok = await self._test_connection(
                user_input[CONF_URL],
                user_input.get("api_key"),
            )

            if not ok:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._connection_schema(),
                    errors={"base": "cannot_connect"},
                )

            self.models = await self._fetch_models(user_input[CONF_URL])

            if not self.models:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._connection_schema(),
                    errors={"base": "cannot_connect"},
                )

            return await self.async_step_options()

        return self.async_show_form(
            step_id="user",
            data_schema=self._connection_schema(),
        )

    # ─────────────────────────────
    # STEP 2: ALL OPTIONS
    # ─────────────────────────────
    async def async_step_options(self, user_input=None):

        if user_input is not None:
            self.data.update(user_input)

            return self.async_create_entry(
                title="LM Studio",
                data=self.data
            )

        schema = vol.Schema({
            vol.Required(CONF_MODEL): vol.In(self.models),

            vol.Required(
                CONF_PROMPT,
                default="You are a helpful assistant"
            ): selector.TextSelector(
                selector.TextSelectorConfig(multiline=True)
            ),

            vol.Optional(
                CONF_IDLE_TIMEOUT,
                default=DEFAULT_IDLE_TIMEOUT
            ): vol.All(int, vol.Range(min=1, max=1440)),

            vol.Optional("streaming", default=True): bool,
            vol.Optional("thinking", default=False): bool,
        })

        return self.async_show_form(
            step_id="options",
            data_schema=schema,
        )

    # ─────────────────────────────
    # CONNECTION SCHEMA
    # ─────────────────────────────
    def _connection_schema(self):
        return vol.Schema({
            vol.Required(CONF_URL, default="http://localhost:1234"): str,
            vol.Optional("api_key", default=""): str,
        })

    # ─────────────────────────────
    # FETCH MODELS (FIXED LM STUDIO API)
    # ─────────────────────────────
    async def _fetch_models(self, url):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{url}/v1/models") as resp:
                    data = await resp.json()

                    return {
                        m["id"]: m["id"]
                        for m in data.get("data", [])
                        if "id" in m
                    }

        except Exception:
            return {}

    # ─────────────────────────────
    # CONNECTION TEST
    # ─────────────────────────────
    async def _test_connection(self, url, api_key=None):
        try:
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{url}/v1/models",
                    headers=headers,
                ) as resp:
                    return resp.status == 200

        except Exception:
            return False