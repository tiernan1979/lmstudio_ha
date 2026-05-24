"""Config flow for LM Studio integration."""

import asyncio
import logging
from collections.abc import Mapping
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_API_KEY, CONF_LLM_HASS_API, CONF_MODEL, CONF_NAME, CONF_PROMPT, CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, llm
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TemplateSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .client import LMStudioClient
from .const import (
    CONF_CONTEXT_LENGTH,
    CONF_FLASH_ATTENTION,
    CONF_IDLE_TIMEOUT,
    CONF_MAX_HISTORY,
    CONF_NUM_CTX,
    DEFAULT_AI_TASK_NAME,
    DEFAULT_CONVERSATION_NAME,
    DEFAULT_CONTEXT_LENGTH,
    DEFAULT_FLASH_ATTENTION,
    DEFAULT_IDLE_TIMEOUT,
    DEFAULT_MAX_HISTORY,
    DEFAULT_NAME,
    DEFAULT_NUM_CTX,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): TextSelector(
            TextSelectorConfig(type=TextSelectorType.URL)
        ),
        vol.Optional(CONF_API_KEY): TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        ),
    }
)


class LMStudioConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _async_validate_connection(
        self, url: str, api_key: str | None
    ) -> dict[str, str]:
        errors: dict[str, str] = {}
        client = LMStudioClient(url, api_key)
        try:
            async with asyncio.timeout(DEFAULT_TIMEOUT):
                await client.list_models()
        except (TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.warning("Cannot connect to LM Studio at %s: %s", url, err)
            errors["base"] = "cannot_connect"
        except Exception as err:
            _LOGGER.exception("Unexpected error connecting to LM Studio at %s: %s", url, err)
            errors["base"] = "unknown"
        finally:
            await client.close()
        return errors

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}
        url = user_input[CONF_URL].strip()
        api_key = user_input.get(CONF_API_KEY)
        if api_key:
            api_key = api_key.strip()

        try:
            url = cv.url(url)
        except vol.Invalid:
            errors["base"] = "invalid_url"
            return self.async_show_form(
                step_id="user",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_USER_DATA_SCHEMA, user_input
                ),
                errors=errors,
            )

        self._async_abort_entries_match({CONF_URL: url})
        errors = await self._async_validate_connection(url, api_key)

        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=self.add_suggested_values_to_schema(
                    STEP_USER_DATA_SCHEMA, user_input
                ),
                errors=errors,
            )

        entry_data: dict[str, str] = {CONF_URL: url}
        if api_key:
            entry_data[CONF_API_KEY] = api_key

        return self.async_create_entry(title=DEFAULT_NAME, data=entry_data)

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {
            "conversation": LMStudioSubentryFlowHandler,
            "ai_task_data": LMStudioSubentryFlowHandler,
        }


class LMStudioSubentryFlowHandler(ConfigSubentryFlow):

    def __init__(self) -> None:
        super().__init__()
        self._name: str | None = None

    @property
    def _is_new(self) -> bool:
        return self.source == "user"

    @property
    def _client(self) -> LMStudioClient:
        entry = self._get_entry()
        if "client" in entry.runtime_data:
            return entry.runtime_data["client"]
        return LMStudioClient(
            url=entry.data[CONF_URL],
            api_key=entry.data.get(CONF_API_KEY),
        )

    async def async_step_set_options(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        if user_input is None:
            models = await self._fetch_models()

            if self._is_new:
                options = {}
            else:
                options = self._get_reconfigure_subentry().data.copy()

            return self.async_show_form(
                step_id="set_options",
                data_schema=vol.Schema(
                    _subentry_config_option_schema(
                        self.hass,
                        self._is_new,
                        self._subentry_type,
                        options,
                        models,
                    )
                ),
            )

        if self._is_new:
            self._name = user_input.pop(CONF_NAME)

            return self.async_create_entry(
                title=self._name,
                data=user_input,
            )

        return self.async_update_and_abort(
            self._get_entry(),
            self._get_reconfigure_subentry(),
            data=user_input,
        )

    async def _fetch_models(self) -> list[SelectOptionDict]:
        try:
            client = self._client
            models = await client.list_models()
            return [
                SelectOptionDict(label=m, value=m)
                for m in sorted(models)
            ]
        except Exception:
            _LOGGER.exception("Failed to fetch models from LM Studio")
            return []

    async_step_user = async_step_set_options
    async_step_reconfigure = async_step_set_options


def _subentry_config_option_schema(
    hass: HomeAssistant,
    is_new: bool,
    subentry_type: str,
    options: Mapping[str, Any],
    models: list[SelectOptionDict],
) -> dict:
    schema: dict = {}

    if is_new:
        default_name = (
            DEFAULT_AI_TASK_NAME if subentry_type == "ai_task_data"
            else DEFAULT_CONVERSATION_NAME
        )
        schema[vol.Required(CONF_NAME, default=default_name)] = str

    schema[vol.Required(
        CONF_MODEL,
        description={"suggested_value": options.get(CONF_MODEL)},
    )] = SelectSelector(
        SelectSelectorConfig(options=models, custom_value=True)
    )

    if subentry_type == "conversation":
        schema[vol.Optional(
            CONF_PROMPT,
            description={"suggested_value": options.get(CONF_PROMPT)},
        )] = TemplateSelector()

        selected_llm_apis = [
            api.id for api in llm.async_get_apis(hass)
            if api.id in options.get(CONF_LLM_HASS_API, [])
        ]
        schema[vol.Optional(
            CONF_LLM_HASS_API,
            description={"suggested_value": selected_llm_apis},
        )] = SelectSelector(
            SelectSelectorConfig(
                options=[
                    SelectOptionDict(label=api.name, value=api.id)
                    for api in llm.async_get_apis(hass)
                ],
                multiple=True,
            )
        )

    schema[vol.Optional(
        CONF_CONTEXT_LENGTH,
        default=options.get(CONF_CONTEXT_LENGTH, DEFAULT_CONTEXT_LENGTH),
        description={"suggested_value": options.get(CONF_CONTEXT_LENGTH, DEFAULT_CONTEXT_LENGTH)},
    )] = NumberSelector(
        NumberSelectorConfig(
            min=256,
            max=131072,
            step=1,
            mode=NumberSelectorMode.BOX,
        )
    )

    schema[vol.Optional(
        CONF_FLASH_ATTENTION,
        default=options.get(CONF_FLASH_ATTENTION, DEFAULT_FLASH_ATTENTION),
    )] = BooleanSelector()

    schema[vol.Optional(
        CONF_MAX_HISTORY,
        default=options.get(CONF_MAX_HISTORY, DEFAULT_MAX_HISTORY),
        description={"suggested_value": options.get(CONF_MAX_HISTORY, DEFAULT_MAX_HISTORY)},
    )] = NumberSelector(
        NumberSelectorConfig(min=0, max=200, step=1, mode=NumberSelectorMode.BOX)
    )

    return schema
