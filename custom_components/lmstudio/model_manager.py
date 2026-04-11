import asyncio
import time


class ModelManager:

    def __init__(self, hass, client, entry_id):
        self.hass = hass
        self.client = client
        self.entry_id = entry_id

        self._watch_task = None
        self._initialized = False

    # ─────────────────────────────────────────
    # CALLED BEFORE EVERY CHAT
    # ─────────────────────────────────────────
    async def ensure_model(self, model: str):

        state = self.hass.data["lmstudio"][self.entry_id]

        # mark activity
        state["last_used"] = time.time()

        self._ensure_watcher_started()

        # already loaded → skip
        if state.get("loaded_model") == model:
            return

        # load model into LM Studio
        await self.client.load_model(model)

        state["loaded_model"] = model
        state["selected_model"] = model

    # ─────────────────────────────────────────
    # START WATCHER ONCE
    # ─────────────────────────────────────────
    def _ensure_watcher_started(self):

        if self._initialized:
            return

        self._initialized = True
        self._start_idle_watcher()

    # ─────────────────────────────────────────
    # START WATCHER (SINGLE TASK ONLY)
    # ─────────────────────────────────────────
    def _start_idle_watcher(self):

        if self._watch_task:
            self._watch_task.cancel()

        self._watch_task = asyncio.create_task(self._idle_loop())

    # ─────────────────────────────────────────
    # IDLE WATCHER LOOP
    # ─────────────────────────────────────────
    async def _idle_loop(self):

        state = self.hass.data["lmstudio"][self.entry_id]

        try:
            while True:
                await asyncio.sleep(30)

                if state.get("tool_running"):
                    continue

                timeout_minutes = state.get("idle_timeout", 5)
                timeout_seconds = timeout_minutes * 60

                loaded_model = state.get("loaded_model")

                if not loaded_model:
                    continue

                idle_time = time.time() - state.get("last_used", 0)

                if idle_time > timeout_seconds:
                    await self._unload_model()
                    return

        except asyncio.CancelledError:
            return

    # ─────────────────────────────────────────
    # UNLOAD MODEL
    # ─────────────────────────────────────────
    async def _unload_model(self):

        state = self.hass.data["lmstudio"][self.entry_id]

        try:
            # safest LM Studio pattern: just clear state
            # (real unload depends on server implementation)
            await self.client.load_model("")
        except Exception:
            pass

        state["loaded_model"] = None