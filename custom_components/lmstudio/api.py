import aiohttp
import json


class LMStudioClient:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")

    async def chat_stream(self, model, messages):
        """
        Yields tokens incrementally
        """

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": True
                }
            ) as resp:

                async for line in resp.content:
                    line = line.decode("utf-8").strip()

                    if not line.startswith("data:"):
                        continue

                    data = line.replace("data: ", "")

                    if data == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"].get("content")
                        if delta:
                            yield delta
                    except:
                        continue

    async def chat(self, model, messages):
        # fallback non-stream
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False
                }
            ) as resp:
                return await resp.json()

    async def list_models(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/v1/models") as r:
                return await r.json()

    async def load_model(self, model):
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/api/v1/models/load",
                json={"model": model}
            ) as r:
                return await r.json()