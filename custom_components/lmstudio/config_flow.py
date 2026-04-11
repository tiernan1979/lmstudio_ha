import voluptuous as vol
from homeassistant import config_entries

from .const import (
    DOMAIN,
    CONF_URL,
    CONF_MODEL,
    CONF_PROMPT,
    CONF_IDLE_TIMEOUT,
    DEFAULT_IDLE_TIMEOUT
)


class LMStudioConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="LM Studio", data=user_input)

        schema = vol.Schema({
            vol.Required(CONF_URL, default="http://localhost:1234"): str,
            vol.Required(CONF_MODEL): str,
            vol.Required(CONF_PROMPT, default="You are a helpful assistant"): str,

            # 🧠 NEW IDLE TIMEOUT
            vol.Optional(
                CONF_IDLE_TIMEOUT,
                default=DEFAULT_IDLE_TIMEOUT
            ): vol.All(int, vol.Range(min=1, max=1440)),

            vol.Optional("streaming", default=True): bool,
            vol.Optional("thinking", default=False): bool,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema
        )