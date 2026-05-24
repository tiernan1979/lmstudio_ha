"""LM Studio integration for Home Assistant."""

from __future__ import annotations

import asyncio
import logging
from types import MappingProxyType

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .client import LMStudioClient
from .const import CONF_IDLE_TIMEOUT, DEFAULT_IDLE_TIMEOUT, DEFAULT_TIMEOUT, DOMAIN, PLATFORMS
from .model_manager import ModelManager

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    url = entry.data[CONF_URL]
    api_key = entry.data.get(CONF_API_KEY)
    client = LMStudioClient(url, api_key)

    try:
        async with asyncio.timeout(DEFAULT_TIMEOUT):
            await client.list_models()
    except (TimeoutError, aiohttp.ClientError) as err:
        await client.close()
        raise ConfigEntryNotReady(f"Cannot connect to LM Studio at {url}: {err}") from err

    model_manager = ModelManager(
        hass, client, entry.entry_id,
        idle_timeout_minutes=entry.options.get(CONF_IDLE_TIMEOUT, DEFAULT_IDLE_TIMEOUT),
    )

    entry.runtime_data = {
        "client": client,
        "model_manager": model_manager,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False

    runtime = entry.runtime_data
    if "model_manager" in runtime:
        runtime["model_manager"].stop()
    if "client" in runtime:
        await runtime["client"].close()

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
