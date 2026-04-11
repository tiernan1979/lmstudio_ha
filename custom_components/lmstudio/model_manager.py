import asyncio
import time


class ModelManager:
    def __init__(self, hass, client):
        self.hass = hass
        self.client = client
        self._watch_task = None
        self._initialized = False

        # single background task handle
        self._watch_task = None


    def _ensure_watcher_started(self):
        if self._initialized:
            return

        self._initialized = True
        self._start_idle_watcher()
    # ─────────────────────────────────────────
    # CALLED BEFORE EVERY CHAT
    # ─────────────────────────────────────────
    async def ensure_model(self, model: str):
        state = self.hass.data["lmstudio"]

        # mark activity (THIS IS IMPORTANT)
        state["last_used"] = time.time()

        self._ensure_watcher_started()  # ✅ ALWAYS RUNS
        
        # already loaded → do nothing
        if state.get("loaded_model") == model:
            return

        # load model into LM Studio
        await self.client.load_model(model)

        state["loaded_model"] = model
        state["selected_model"] = model

        # start / restart idle watcher
        self._start_idle_watcher()

    # ─────────────────────────────────────────
    # START WATCHER (ONLY ONE RUNNING)
    # ─────────────────────────────────────────
    def _start_idle_watcher(self):
        if self._watch_task:
            self._watch_task.cancel()

        self._watch_task = asyncio.create_task(self._idle_loop())

    # ─────────────────────────────────────────
    # IDLE WATCHER LOOP  ⭐ THIS IS THE WATCHER
    # ─────────────────────────────────────────
    async def _idle_loop(self):
        state = self.hass.data["lmstudio"]

        try:
            while True:
                await asyncio.sleep(30)  # check interval

                # 🧠 DO NOT UNLOAD DURING TOOL EXECUTION
                if state.get("tool_running"):
                    continue

                timeout_minutes = state.get("idle_timeout", 5)
                timeout_seconds = timeout_minutes * 60

                last_used = state.get("last_used", 0)
                loaded_model = state.get("loaded_model")

                # nothing loaded → nothing to do
                if not loaded_model:
                    continue

                # idle check
                idle_time = time.time() - last_used
                if idle_time > timeout_seconds:
                    await self._unload_model()
                    return

        except asyncio.CancelledError:
            return

    # ─────────────────────────────────────────
    # UNLOAD MODEL (LM Studio STYLE)
    # ─────────────────────────────────────────
    async def _unload_model(self):
        state = self.hass.data["lmstudio"]

        try:
            # LM Studio "unload" pattern = load empty / switch away
            await self.client.load_model("")
        except Exception:
            pass

        state["loaded_model"] = None