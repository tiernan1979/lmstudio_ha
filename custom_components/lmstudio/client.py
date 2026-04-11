import aiohttp


class LMStudioClient:

    def __init__(self, config):
        self.url = config["url"]
        self.api_key = config.get("api_key")

    def headers(self):
        return (
            {"Authorization": f"Bearer {self.api_key}"}
            if self.api_key else {}
        )

    # ─────────────────────────────
    # NON-STREAM CHAT
    # ─────────────────────────────
    async def chat(self, model, messages):

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.url}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                },
                headers=self.headers(),
            ) as resp:
                return await resp.json()

    # ─────────────────────────────
    # STREAM CHAT (NEW)
    # ─────────────────────────────
    async def chat_stream(self, model, messages, callback):

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.url}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": True,
                },
                headers=self.headers(),
            ) as resp:

                buffer = ""

                async for line in resp.content:

                    if not line:
                        continue

                    try:
                        decoded = line.decode("utf-8").strip()

                        if not decoded.startswith("data:"):
                            continue

                        data = decoded.replace("data:", "").strip()

                        if data == "[DONE]":
                            break

                        import json
                        chunk = json.loads(data)

                        delta = (
                            chunk.get("choices", [{}])[0]
                            .get("delta", {})
                            .get("content", "")
                        )

                        if delta:
                            buffer += delta
                            await callback(delta)

                    except Exception:
                        continue

                return buffer