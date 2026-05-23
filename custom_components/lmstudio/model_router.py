from __future__ import annotations
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from .client import LMStudioClient

_LOGGER = logging.getLogger(__name__)


class ModelRouter:
    """Handles model selection and routing based on user input."""

    def __init__(self, entry_data: dict[str, Any]) -> None:
        self._entry_data = entry_data
        self._default_model = entry_data.get("model", "LM Studio")

    def pick_model(self, string: str, entry_data: dict[str, Any]) -> str | None:
        """Pick a model based on the's request or configuration."""
        if "use model" in string.lower():
            import re
            match = re.search(r"use model\s+(.+)", string, re.IGNORECASE)
            if match:
                return match.group(1).strip()
            return self._default_model

        if "list models" in string.lower():
            return "LIST_MODELS"

        return self._default_model



        return self._default_model
