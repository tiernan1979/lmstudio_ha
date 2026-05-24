from __future__ import annotations
import logging
from typing import Any

from homeassistant.components.ai_task import (
    AITaskEntity,
    AITaskEntityFeature,
    GenDataTask,
    GenDataTaskResult,
    GenImageTask,
    GenImageTaskResult,
)
from homeassistant.components.conversation import ChatLog

_LOGGER = logging.getLogger(__name__)


class LMStudioAITaskEntity(AITaskEntity):
    _attr_has_entity_name = True
    _attr_name = "AI Task"
    _attr_unique_id = "ai_task"
    _attr_supported_features = (
        AITaskEntityFeature.GENERATE_DATA
        | AITaskEntityFeature.GENERATE_IMAGE
        | AITaskEntityFeature.SUPPORT_ATTACHMENTS
    )

    def __init__(self, hass, client, model_manager, entry_id, entry_data):
        self.hass = hass
        self.client = client
        self.model_manager = model_manager
        self.entry_id = entry_id
        self._entry_data = entry_data

    async def _async_generate_data(
        self,
        task: GenDataTask,
        chat_log: ChatLog,
    ) -> GenDataTaskResult:
        from .model_router import ModelRouter

        router = ModelRouter(self._entry_data)
        model = router.pick_model(task.instructions)

        await self.model_manager.ensure_model(model)

        messages: list[dict[str, str]] = [
            {"role": "system", "content": "You are a Home Assistant expert. Generate the requested data accurately."},
            {"role": "user", "content": task.instructions},
        ]

        if task.structure is not None:
            messages.append({
                "role": "user",
                "content": f"Return your response as valid structured data following this schema.",
            })

        result = await self.client.chat(model, messages)
        content = result["choices"][0]["message"].get("content", "")

        return GenDataTaskResult(
            conversation_id=self.entry_id,
            data=content,
        )

    async def _async_generate_image(
        self,
        task: GenImageTask,
        chat_log: ChatLog,
    ) -> GenImageTaskResult:
        from .model_router import ModelRouter

        router = ModelRouter(self._entry_data)
        model = router.pick_model(task.instructions)

        await self.model_manager.ensure_model(model)

        image_data = await self.client.generate_image(
            model=model,
            prompt=task.instructions,
        )

        if not image_data:
            from homeassistant.exceptions import HomeAssistantError

            raise HomeAssistantError(
                "Image generation is not available on this LM Studio server. "
                "Ensure your LM Studio server supports /v1/images/generations "
                "or use a compatible backend."
            )

        return GenImageTaskResult(
            image_data=image_data,
            conversation_id=self.entry_id,
            mime_type="image/png",
            revised_prompt=task.instructions,
        )
