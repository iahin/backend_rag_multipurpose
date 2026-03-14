import json
from typing import AsyncIterator

import httpx

from app.core.config import Settings
from app.models.schemas import ChatCompletionResult, ChatMessage, ProviderHealth
from app.providers.base import ProviderAdapter


class GeminiProvider(ProviderAdapter):
    provider_name = "gemini"
    capabilities = ["chat", "embeddings_interface_ready"]

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def healthcheck(self) -> ProviderHealth:
        enabled = self._settings.gemini_enabled
        configured = bool(self._settings.gemini_api_key)

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
                detail="missing GEMINI_API_KEY",
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
        if not self._settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required for Gemini chat")

        contents = self._build_contents(messages)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                params={"key": self._settings.gemini_api_key},
                json={"contents": contents},
            )
            response.raise_for_status()
            data = response.json()

        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return ChatCompletionResult(text=text, provider=self.provider_name, model=model)

    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
    ) -> AsyncIterator[str]:
        if not self._settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required for Gemini chat")

        contents = self._build_contents(messages)

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent",
                params={"key": self._settings.gemini_api_key, "alt": "sse"},
                json={"contents": contents},
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue

                    payload = json.loads(line[6:].strip())
                    candidates = payload.get("candidates", [])
                    if not candidates:
                        continue

                    parts = candidates[0].get("content", {}).get("parts", [])
                    for part in parts:
                        text = part.get("text", "")
                        if text:
                            yield text

    def _build_contents(self, messages: list[ChatMessage]) -> list[dict]:
        contents: list[dict] = []
        for message in messages:
            role = "model" if message.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": message.content}]})
        return contents
