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

LOAD_MODEL_SCHEMA = vol.Schema({
    vol.Required("model"): cv.string,
    vol.Optional("entry_id"): cv.string,
})

DOWNLOAD_MODEL_SCHEMA = vol.Schema({
    vol.Required("model"): cv.string,
    vol.Optional("entry_id"): cv.string,
})


async def async_setup_services(hass: HomeAssistant) -> None:

    async def list_models(call: ServiceCall) -> None:
        # Try all loaded entries, use first available client
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
        # Optional: target a specific entry, otherwise use first
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

    # inside async_setup_services:
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

    hass.services.async_register(
        DOMAIN, SERVICE_DOWNLOAD_MODEL, download_model,
        schema=DOWNLOAD_MODEL_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN, SERVICE_LIST_MODELS, list_models
    )
    hass.services.async_register(
        DOMAIN, SERVICE_LOAD_MODEL, load_model,
        schema=LOAD_MODEL_SCHEMA,
    )