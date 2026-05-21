from __future__ import annotations
import logging

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVICE_LIST_MODELS = "list_models"
SERVICE_LOAD_MODEL = "load_model"
SERVICE_DOWNLOAD_MODEL = "download_model"
SERVICE_CLEAR_MEMORY = "clear_memory"

LOAD_MODEL_SCHEMA = vol.Schema({
    vol.Required("model"): cv.string,
    vol.Optional("entry_id"): cv.string,
})

DOWNLOAD_MODEL_SCHEMA = vol.Schema({
    vol.Required("model"): cv.string,
    vol.Optional("entry_id"): cv.string,
})

CLEAR_MEMORY_SCHEMA = vol.Schema({
    vol.Optional("entry_id"): cv.string,
    vol.Optional("conversation_id"): cv.string,
})


async def async_setup_services(hass: HomeAssistant) -> None:

    async def list_models(call: ServiceCall) -> None:
        for entry_id, data in hass.data.get(DOMAIN, {}).items():
            client = data.get("client")
            if not client:
                continue
            try:
                models = await client.list_models()
                model_ids = [m["id"] for m in models.get("data", [])]
                hass.states.async_set(
                    f"{DOMAIN}.models",
                    ", ".join(model_ids),
                    {"models": model_ids, "entry_id": entry_id},
                )
                return
            except Exception as err:
                _LOGGER.error("list_models failed for entry %s: %s", entry_id, err)

    async def load_model(call: ServiceCall) -> None:
        model = call.data["model"]
        target_entry_id = call.data.get("entry_id")

        for entry_id, data in hass.data.get(DOMAIN, {}).items():
            if target_entry_id and entry_id != target_entry_id:
                continue
            client = data.get("client")
            if not client:
                continue
            try:
                await client.load_model(model)
                data["model"] = model
                data["loaded_model"] = model
                _LOGGER.debug("Loaded model %s for entry %s", model, entry_id)
                return
            except Exception as err:
                _LOGGER.error("load_model failed for entry %s: %s", entry_id, err)

    async def download_model(call: ServiceCall) -> None:
        model = call.data["model"]
        target_entry_id = call.data.get("entry_id")
        for entry_id, data in hass.data.get(DOMAIN, {}).items():
            if target_entry_id and entry_id != target_entry_id:
                continue
            client = data.get("client")
            if not client:
                continue
            try:
                await client.download_model(model)
                return
            except Exception as err:
                _LOGGER.error("download_model failed for entry %s: %s", entry_id, err)

    async def clear_memory(call: ServiceCall) -> None:
        target_entry_id = call.data.get("entry_id")
        conversation_id = call.data.get("conversation_id")

        for entry_id, data in hass.data.get(DOMAIN, {}).items():
            if target_entry_id and entry_id != target_entry_id:
                continue
            agent = data.get("agent")
            if not agent:
                continue
            try:
                await agent._memory.clear(conversation_id)
                _LOGGER.debug("Cleared memory for entry %s", entry_id)
                return
            except Exception as err:
                _LOGGER.error("clear_memory failed for entry %s: %s", entry_id, err)

    hass.services.async_register(
        DOMAIN, SERVICE_LIST_MODELS, list_models
    )
    hass.services.async_register(
        DOMAIN, SERVICE_LOAD_MODEL, load_model,
        schema=LOAD_MODEL_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DOWNLOAD_MODEL, download_model,
        schema=DOWNLOAD_MODEL_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CLEAR_MEMORY, clear_memory,
        schema=CLEAR_MEMORY_SCHEMA,
    )
