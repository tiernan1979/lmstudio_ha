from homeassistant.components.conversation import AbstractConversationAgent
from homeassistant.helpers.intent import IntentResponse

import time

from .model_manager import ModelManager
from .tool_executor import ToolExecutor
from .memory import Memory


class LMStudioAgent(AbstractConversationAgent):

    # ─────────────────────────────
    # REQUIRED BY HOME ASSISTANT
    # ─────────────────────────────
    @property
    def supported_languages(self):
        return ["en"]

    # ─────────────────────────────
    def __init__(self, hass, client):
        self.hass = hass
        self.client = client

        self.memory = Memory()
        self.manager = ModelManager(hass, client)
        self.tools = ToolExecutor(hass)

    # ─────────────────────────────
    # MAIN ENTRY
    # ─────────────────────────────
    async def async_process(self, text, context, conversation_id=None):

        state = self.hass.data["lmstudio"]

        # activity timer (idle unload system)
        state["last_used"] = time.time()

        cid = conversation_id or "default"

        # ─────────────────────────────
        # SINGLE SOURCE OF TRUTH MODEL
        # ─────────────────────────────
        model = state.get("selected_model")

        await self.manager.ensure_model(model)

        # memory add user message
        self.memory.add(cid, "user", text)

        messages = [
            {"role": "system", "content": state.get("system_prompt", "")},
            *self.memory.get(cid, limit=10),
        ]

        # ─────────────────────────────
        # FIRST LM CALL
        # ─────────────────────────────
        result = await self.client.chat(model, messages)

        message = result["choices"][0]["message"]

        content = message.get("content", "")
        tool_calls = message.get("tool_calls", [])

        # ─────────────────────────────
        # TOOL EXECUTION (WITH FEEDBACK LOOP)
        # ─────────────────────────────
        if tool_calls:

            # mark tool running (prevents idle unload)
            state["tool_running"] = True

            try:
                # execute tools
                results = await self.tools.execute_tool_calls(tool_calls)

            finally:
                state["tool_running"] = False
                state["last_used"] = time.time()

            # build tool feedback messages
            tool_messages = []

            for r in results:
                tool_messages.append({
                    "role": "tool",
                    "content": {
                        "tool": r.get("name"),
                        "success": r.get("success"),
                        "result": r.get("result"),
                        "error": r.get("error"),
                    }
                })

            # ─────────────────────────────
            # SECOND LM CALL (FEEDBACK LOOP)
            # ─────────────────────────────
            messages = [
                {"role": "system", "content": state.get("system_prompt", "")},
                *self.memory.get(cid, limit=10),
                *tool_messages,
            ]

            result = await self.client.chat(model, messages)

            final_message = result["choices"][0]["message"]["content"]

            response_text = final_message

        else:
            response_text = content

        # store assistant response
        self.memory.add(cid, "assistant", response_text)

        # ─────────────────────────────
        # RETURN TO HOME ASSISTANT
        # ─────────────────────────────
        response = IntentResponse(language="en")
        response.async_set_speech(response_text)

        return response