from __future__ import annotations
import asyncio
import logging
import time

_LOGGER = logging.getLogger(__name__)


class ModelManager:

    def __init__(self, hass, client, entry_id: str, idle_timeout_minutes: int = 5):
        self.hass = hass
        self.client = client
        self.entry_id = entry_id
        self._idle_timeout = idle_timeout_minutes * 60
        self._watch_task: asyncio.Task | None = None
        self._loaded_model: str | None = None
        self._last_used: float = 0

    async def ensure_model(
        self,
        model: str,
        context_length: int | None = None,
        flash_attention: bool | None = None,
    ) -> None:
        self._last_used = time.time()

        if self._watch_task is None:
            self._watch_task = self.hass.async_create_task(self._idle_loop())

        if self._loaded_model == model and self._loaded_model is not None:
            return

        already_loaded = await self.client.is_model_loaded(model)
        if already_loaded:
            _LOGGER.debug("Model %s is already loaded on server", model)
            self._loaded_model = model
            return

        if self._loaded_model:
            _LOGGER.debug("Unloading previous model: %s", self._loaded_model)
            try:
                await self.client.unload_model(self._loaded_model)
            except Exception:
                _LOGGER.debug("Failed to unload previous model %s, proceeding", self._loaded_model)

        _LOGGER.debug("Loading model: %s", model)
        await self.client.load_model(
            model,
            context_length=context_length,
            flash_attention=flash_attention,
        )
        self._loaded_model = model

    async def _idle_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(30)
                if not self._loaded_model:
                    continue
                idle_time = time.time() - self._last_used
                if idle_time > self._idle_timeout:
                    _LOGGER.debug(
                        "Model idle timeout (%ss > %ss) - unloading: %s",
                        idle_time, self._idle_timeout, self._loaded_model,
                    )
                    try:
                        await self.client.unload_model(self._loaded_model)
                    except Exception as err:
                        _LOGGER.debug(
                            "Unload API call failed (%s), clearing local tracking only", err
                        )
                    self._loaded_model = None
        except asyncio.CancelledError:
            return

    def stop(self) -> None:
        if self._watch_task:
            self._watch_task.cancel()
            self._watch_task = None
