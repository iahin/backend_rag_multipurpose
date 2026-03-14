from abc import ABC, abstractmethod
from typing import AsyncIterator

from app.models.schemas import ChatMessage, ChatCompletionResult, ProviderHealth


class ProviderAdapter(ABC):
    provider_name: str
    capabilities: list[str]

    @abstractmethod
    async def healthcheck(self) -> ProviderHealth:
        raise NotImplementedError

    @abstractmethod
    async def complete_chat(
        self,
        messages: list[ChatMessage],
        model: str,
    ) -> ChatCompletionResult:
        raise NotImplementedError

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[ChatMessage],
        model: str,
    ) -> AsyncIterator[str]:
        raise NotImplementedError
