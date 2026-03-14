import json
from typing import AsyncIterator

import httpx

from app.core.config import Settings
from app.models.schemas import ChatCompletionResult, ChatMessage, ProviderHealth
from app.providers.base import ProviderAdapter


class OpenAIProvider(ProviderAdapter):
    provider_name = "openai"
    capabilities = ["chat", "embeddings"]

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def healthcheck(self) -> ProviderHealth:
        enabled = self._settings.openai_enabled
        configured = bool(self._settings.openai_api_key)

        if not enabled:
            return ProviderHealth(
                ok=True,
                detail="disabled",
                enabled=False,
                provider=self.provider_name,
                capabilities=self.capabilities,
                configuration_present=configured,
            )

        if not configured:
            return ProviderHealth(
                ok=False,
                detail="missing OPENAI_API_KEY",
                enabled=True,
                provider=self.provider_name,
                capabilities=self.capabilities,
                configuration_present=False,
            )

        return ProviderHealth(
            ok=True,
            detail="configuration_present",
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
        if not self._settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI chat")

        headers = {
            "Authorization": f"Bearer {self._settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [message.model_dump() for message in messages],
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        text = data["choices"][0]["message"]["content"]
        return ChatCompletionResult(text=text, provider=self.provider_name, model=model)

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
    ) -> AsyncIterator[str]:
        if not self._settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI chat")

        headers = {
            "Authorization": f"Bearer {self._settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [message.model_dump() for message in messages],
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue

                    data = line[6:].strip()
                    if data == "[DONE]":
                        break

                    parsed = json.loads(data)
                    delta = parsed["choices"][0]["delta"].get("content", "")
                    if delta:
                        yield delta
