import json
from typing import AsyncIterator

import httpx

from app.core.config import Settings
from app.models.schemas import ChatCompletionResult, ChatMessage, ProviderHealth
from app.providers.base import ProviderAdapter


class OllamaProvider(ProviderAdapter):
    provider_name = "ollama"
    capabilities = ["chat", "embeddings"]

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def healthcheck(self) -> ProviderHealth:
        enabled = self._settings.ollama_enabled

        if not enabled:
            return ProviderHealth(
                ok=True,
                detail="disabled",
                enabled=False,
                provider=self.provider_name,
                capabilities=self.capabilities,
                configuration_present=True,
            )

        try:
            async with httpx.AsyncClient(
                base_url=self._settings.ollama_base_url,
                timeout=self._settings.ollama_health_timeout_seconds,
            ) as client:
                response = await client.get("/api/tags")

            if response.status_code >= 400:
                return ProviderHealth(
                    ok=False,
                    detail=f"ollama_http_{response.status_code}",
                    enabled=True,
                    provider=self.provider_name,
                    capabilities=self.capabilities,
                    configuration_present=True,
                )

            return ProviderHealth(
                ok=True,
                detail="reachable",
                enabled=True,
                provider=self.provider_name,
                capabilities=self.capabilities,
                configuration_present=True,
            )
        except httpx.HTTPError as exc:
            return ProviderHealth(
                ok=False,
                detail=f"ollama_unreachable: {exc}",
                enabled=True,
                provider=self.provider_name,
                capabilities=self.capabilities,
                configuration_present=True,
            )

    async def complete_chat(
        self,
        messages: list[ChatMessage],
        model: str,
    ) -> ChatCompletionResult:
        async with httpx.AsyncClient(
            base_url=self._settings.ollama_base_url,
            timeout=60.0,
        ) as client:
            response = await client.post(
                "/api/chat",
                json={
                    "model": model,
                    "stream": False,
                    "messages": [message.model_dump() for message in messages],
                },
            )
            response.raise_for_status()
            data = response.json()

        text = data["message"]["content"]
        return ChatCompletionResult(text=text, provider=self.provider_name, model=model)

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
    ) -> AsyncIterator[str]:
        async with httpx.AsyncClient(
            base_url=self._settings.ollama_base_url,
            timeout=60.0,
        ) as client:
            async with client.stream(
                "POST",
                "/api/chat",
                json={
                    "model": model,
                    "stream": True,
                    "messages": [message.model_dump() for message in messages],
                },
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line:
                        continue
                    payload = json.loads(line)
                    delta = payload.get("message", {}).get("content", "")
                    if delta:
                        yield delta
