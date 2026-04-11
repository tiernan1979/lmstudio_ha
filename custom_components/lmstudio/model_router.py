class ModelRouter:
    def pick_model(self, text, state):

        # 🧠 THINKING MODE OVERRIDE
        if state.get("thinking"):
            return state.get("smart_model") or state["selected_model"]

        # fast path
        if len(text) < 40:
            return state.get("fast_model") or state["selected_model"]

        text_lower = text.lower()

        if any(w in text_lower for w in ["why", "how", "explain", "analyze"]):
            return state.get("smart_model") or state["selected_model"]

        return state["selected_model"]