from homeassistant.components.conversation import AbstractConversationAgent
from homeassistant.helpers.intent import IntentResponse

from .model_manager import ModelManager
from .model_router import ModelRouter
from .tool_executor import ToolExecutor
from .memory import Memory

class LMStudioAgent(AbstractConversationAgent):

    def __init__(self, hass, client):
        self.hass = hass
        self.client = client
        self.memory = Memory()
        self.router = ModelRouter(hass)
        self.manager = ModelManager(hass, client)
        self.tools = ToolExecutor(hass)

    async def async_process(self, text, context, conversation_id=None):

        state = self.hass.data["lmstudio"]

        # ✅ THIS IS THE TIMER RESET (EVERY REQUEST)
        state["last_used"] = time.time()

        cid = conversation_id or "default"
        state = self.hass.data["lmstudio"]

        model = self.router.pick_model(text, state)

        await self.manager.ensure_model(model)

        self.memory.add(cid, "user", text)

        messages = [
            {"role": "system", "content": state["system_prompt"]},
            *self.memory.get(cid, limit=10)
        ]

        # 🔥 OPENAI-COMPATIBLE CALL (LM Studio)
        result = await self.client.chat(model, messages)

        message = result["choices"][0]["message"]

        content = message.get("content")
        tool_calls = message.get("tool_calls")

        # ─────────────────────────────
        # TOOL EXECUTION V2
        # ─────────────────────────────
        if tool_calls:
            await self.tools.execute_tool_calls(tool_calls)
            response_text = "Done."
        else:
            response_text = content or ""

        self.memory.add(cid, "assistant", response_text)

        response = IntentResponse(language="en")
        response.async_set_speech(response_text)

        return response