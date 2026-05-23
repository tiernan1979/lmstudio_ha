"""Model selection and routing based on user input."""

from __future__ import annotations
import logging
import re
from typing import Any

_LOGGER = logging.getLogger(__name__)

LIST_MODELS = "LIST_MODELS"


class ModelRouter:
    """Handles model selection and routing based on user input."""

    def __init__(self, entry_data: dict[str, Any]) -> None:
        self._default_model = entry_data.get("model", "LM Studio")

    def pick_model(self, string: str) -> str | None:
        """Pick a model based on the user's request or configuration."""
        if "use model" in string.lower():
            match = re.search(r"use model\s+(.+)", string, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        if "list models" in string.lower():
            return LIST_MODELS

        return self._default_model
