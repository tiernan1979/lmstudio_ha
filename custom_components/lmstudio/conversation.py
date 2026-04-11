from homeassistant.components.conversation import AbstractConversationAgent
from homeassistant.helpers.intent import IntentResponse

import time


class LMStudioAgent(AbstractConversationAgent):

    @property
    def supported_languages(self):
        return ["en"]

    def __init__(self, hass, client, entry_id, model_manager):
        self.hass = hass
        self.client = client
        self.entry_id = entry_id
        self.model_manager = model_manager

    async def async_process(self, text, context, conversation_id=None):

        state = self.hass.data["lmstudio"][self.entry_id]

        state["last_used"] = time.time()

        model = state["model"]

        await self.model_manager.ensure_model(model)

        messages = [
            {"role": "system", "content": state["system_prompt"]},
            {"role": "user", "content": text},
        ]

        streaming_enabled = state.get("streaming", True)

        # ─────────────────────────────
        # STREAMING PATH
        # ─────────────────────────────
        if streaming_enabled:

            buffer = []

            async def on_delta(token):
                buffer.append(token)

            full = await self.client.chat_stream(
                model,
                messages,
                on_delta
            )

            content = full

        # ─────────────────────────────
        # NORMAL PATH
        # ─────────────────────────────
        else:
            result = await self.client.chat(model, messages)
            content = result["choices"][0]["message"]["content"]

        response = IntentResponse(language="en")
        response.async_set_speech(content)

        return response
    
    async def async_will_remove_from_hass(self):
        """When the agent is removed."""
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()