from __future__ import annotations
import logging
from collections import defaultdict

from homeassistant.core import HomeAssistant

STORAGE_KEY = "lmstudio_memory"
STORAGE_VERSION = 1

_LOGGER = logging.getLogger(__name__)


class Memory:

    def __init__(self, hass: HomeAssistant | None = None):
        self.hass = hass
        self.store = defaultdict(list)
        self._storage = None
        self._loaded = False

    async def _load(self) -> None:
        if self.hass and not self._loaded:
            from homeassistant.helpers.storage import Store
            self._storage = Store(self.hass, STORAGE_VERSION, STORAGE_KEY)
            data = await self._storage.async_load()
            if data:
                for cid, messages in data.items():
                    self.store[cid] = messages
            self._loaded = True

    async def _save(self) -> None:
        if self._storage:
            await self._storage.async_save(dict(self.store))

    async def add(self, cid, role, content) -> None:
        await self._load()
        self.store[cid].append({"role": role, "content": content})
        await self._save()

    async def get(self, cid, limit=20) -> list:
        await self._load()
        return self.store[cid][-limit:]

    async def clear(self, cid=None) -> None:
        await self._load()
        if cid:
            self.store.pop(cid, None)
        else:
            self.store.clear()
        await self._save()
