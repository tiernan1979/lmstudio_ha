from __future__ import annotations
import logging

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVICE_LIST_MODELS = "list_models"
SERVICE_LOAD_MODEL = "load_model"
SERVICE_UNLOAD_MODEL = "unload_model"
SERVICE_DOWNLOAD_MODEL = "download_model"
SERVICE_CLEAR_MEMORY = "clear_memory"
SERVICE_CHAT = "chat"

MODEL_SCHEMA = vol.Schema({
    vol.Required("model"): cv.string,
    vol.Optional("entry_id"): cv.string,
})

CLEAR_MEMORY_SCHEMA = vol.Schema({
    vol.Optional("entry_id"): cv.string,
    vol.Optional("conversation_id"): cv.string,
})

CHAT_SCHEMA = vol.Schema({
    vol.Required("message"): cv.string,
    vol.Optional("model"): cv.string,
    vol.Optional("entry_id"): cv.string,
    vol.Optional("temperature"): vol.Any(vol.Range(0, 2), int),
    vol.Optional("context_length"): vol.All(cv.positive_int, vol.Range(256, 131072)),
    vol.Optional("integrations"): [vol.Schema({
        vol.Required("type"): vol.Any("ephemeral_mcp", "plugin"),
        vol.Optional("server_label"): cv.string,
        vol.Optional("server_url"): cv.string,
        vol.Optional("id"): cv.string,
        vol.Optional("allowed_tools"): [cv.string],
    })],
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

    async def unload_model(call: ServiceCall) -> None:
        model = call.data["model"]
        target_entry_id = call.data.get("entry_id")
        for entry_id, data in hass.data.get(DOMAIN, {}).items():
            if target_entry_id and entry_id != target_entry_id:
                continue
            client = data.get("client")
            if not client:
                continue
            try:
                await client.unload_model(model)
                _LOGGER.debug("Unloaded model %s for entry %s", model, entry_id)
                return
            except Exception as err:
                _LOGGER.error("unload_model failed for entry %s: %s", entry_id, err)

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

    async def chat(call: ServiceCall) -> None:
        message = call.data["message"]
        target_entry_id = call.data.get("entry_id")
        model = call.data.get("model")
        temperature = call.data.get("temperature")
        context_length = call.data.get("context_length")
        integrations = call.data.get("integrations")

        for entry_id, data in hass.data.get(DOMAIN, {}).items():
            if target_entry_id and entry_id != target_entry_id:
                continue
            client = data.get("client")
            if not client:
                continue
            try:
                result = await client.chat_native(
                    model=model,
                    input=message,
                    temperature=temperature,
                    context_length=context_length,
                    integrations=integrations,
                )
                content = result.get("content", "") or result.get("message", "")
                if content:
                    hass.states.async_set(
                        f"{DOMAIN}.chat_response",
                        content[:255],
                        {
                            "full_response": content,
                            "model": model,
                            "entry_id": entry_id,
                        },
                    )
                return
            except Exception as err:
                _LOGGER.error("chat failed for entry %s: %s", entry_id, err)

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
        schema=MODEL_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_UNLOAD_MODEL, unload_model,
        schema=MODEL_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DOWNLOAD_MODEL, download_model,
        schema=MODEL_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CLEAR_MEMORY, clear_memory,
        schema=CLEAR_MEMORY_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CHAT, chat,
        schema=CHAT_SCHEMA,
    )
