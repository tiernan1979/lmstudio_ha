from __future__ import annotations
import asyncio
import logging
import time

from .const import CONF_IDLE_TIMEOUT, DEFAULT_IDLE_TIMEOUT, DOMAIN

_LOGGER = logging.getLogger(__name__)


class ModelManager:

    def __init__(self, hass, client, entry_id: str):
        self.hass = hass
        self.client = client
        self.entry_id = entry_id
        self._watch_task: asyncio.Task | None = None
        self._initialized = False

    async def ensure_model(self, model: str) -> None:
        state = self.hass.data[DOMAIN][self.entry_id]
        state["last_used"] = time.time()

        if not self._initialized:
            self._initialized = True
            self._watch_task = self.hass.async_create_task(self._idle_loop())

        if state.get("loaded_model") == model:
            return

        _LOGGER.debug("Loading model: %s", model)
        await self.client.load_model(model)
        state["loaded_model"] = model

    async def _idle_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(30)
                state = self.hass.data[DOMAIN].get(self.entry_id)

                if state is None:
                    return

                loaded_model = state.get("loaded_model")
                if not loaded_model:
                    continue

                timeout_seconds = state.get(CONF_IDLE_TIMEOUT, DEFAULT_IDLE_TIMEOUT) * 60
                idle_time = time.time() - state.get("last_used", 0)

                if idle_time > timeout_seconds:
                    _LOGGER.debug("Model idle timeout — unloading model: %s", loaded_model)
                    try:
                        await self.client.unload_model(loaded_model)
                    except Exception as err:
                        _LOGGER.debug("Unload API call failed (%s), clearing local tracking only", err)
                    state["loaded_model"] = None

        except asyncio.CancelledError:
            return

    def stop(self) -> None:
        if self._watch_task:
            self._watch_task.cancel()
            self._watch_task = None
