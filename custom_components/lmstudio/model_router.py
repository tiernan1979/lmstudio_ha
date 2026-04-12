class ModelRouter:

    def pick_model(self, text: str, state: dict) -> str:
        # "model" is the canonical key stored in hass.data
        default = state["model"]

        if state.get("thinking"):
            return state.get("smart_model", default)

        if len(text) < 40:
            return state.get("fast_model", default)

        if any(w in text.lower() for w in ["why", "how", "explain", "analyze"]):
            return state.get("smart_model", default)

        return default