class ModelRouter:

    def pick_model(self, text: str, state: dict) -> str:
        default = state["model"]
        smart_model = state.get("smart_model") or default
        fast_model = state.get("fast_model") or default

        if state.get("thinking"):
            return smart_model

        if len(text) < 40:
            return fast_model

        if any(w in text.lower() for w in ["why", "how", "explain", "analyze"]):
            return smart_model

        return default
