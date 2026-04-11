import asyncio
import time

class ToolExecutor:
    def __init__(self, hass):
        self.hass = hass

    async def execute_tool_calls(self, tool_calls):
        state = self.hass.data["lmstudio"]

        # 🧠 mark tool running
        state["tool_running"] = True

        try:
            for call in tool_calls:
                name = call["function"]["name"]
                args = call["function"]["arguments"]

                # keep “alive” during long operations
                state["last_used"] = time.time()

                if name == "turn_on":
                    await self.hass.services.async_call(
                        "homeassistant",
                        "turn_on",
                        args
                    )

                elif name == "turn_off":
                    await self.hass.services.async_call(
                        "homeassistant",
                        "turn_off",
                        args
                    )

                elif name == "call_service":
                    await self.hass.services.async_call(
                        args["domain"],
                        args["service"],
                        args.get("data", {})
                    )

        finally:
            # 🧠 tool finished
            state["tool_running"] = False
            state["last_used"] = time.time()