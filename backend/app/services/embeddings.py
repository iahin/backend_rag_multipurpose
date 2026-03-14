from abc import ABC, abstractmethod

import httpx

from app.core.config import Settings
from app.core.logging import get_logger
from app.models.schemas import EmbeddingSelection, ProviderName
from app.services.cache_service import CacheService

logger = get_logger(__name__)


class EmbeddingProvider(ABC):
    provider_name: str

    @abstractmethod
    async def embed(self, texts: list[str], model: str) -> list[list[float]]:
        raise NotImplementedError


class OpenAIEmbeddingProvider(EmbeddingProvider):
    provider_name = "openai"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def embed(self, texts: list[str], model: str) -> list[list[float]]:
        if not self._settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI embeddings")

        headers = {
            "Authorization": f"Bearer {self._settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {"input": texts, "model": model}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        return [item["embedding"] for item in data["data"]]


class GeminiEmbeddingProvider(EmbeddingProvider):
    provider_name = "gemini"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def embed(self, texts: list[str], model: str) -> list[list[float]]:
        if not self._settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required for Gemini embeddings")

        embeddings: list[list[float]] = []
        async with httpx.AsyncClient(timeout=30.0) as client:
            for text in texts:
                response = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent",
                    params={"key": self._settings.gemini_api_key},
                    json={"content": {"parts": [{"text": text}]}},
                )
                response.raise_for_status()
                data = response.json()
                embeddings.append(data["embedding"]["values"])
        return embeddings


class OllamaEmbeddingProvider(EmbeddingProvider):
    provider_name = "ollama"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def embed(self, texts: list[str], model: str) -> list[list[float]]:
        embeddings: list[list[float]] = []
        async with httpx.AsyncClient(
            base_url=self._settings.ollama_base_url,
            timeout=60.0,
        ) as client:
            for text in texts:
                response = await client.post(
                    "/api/embeddings",
                    json={"model": model, "prompt": text},
                )
                response.raise_for_status()
                data = response.json()
                embeddings.append(data["embedding"])
        return embeddings


class EmbeddingService:
    def __init__(self, settings: Settings, cache_service: CacheService | None = None) -> None:
        self._settings = settings
        self._cache = cache_service
        self._providers: dict[ProviderName, EmbeddingProvider] = {
            "openai": OpenAIEmbeddingProvider(settings),
            "gemini": GeminiEmbeddingProvider(settings),
            "ollama": OllamaEmbeddingProvider(settings),
        }

    def resolve_selection(
        self,
        provider: str | None,
        model: str | None,
    ) -> EmbeddingSelection:
        resolved_provider = provider or self._settings.default_embedding_provider
        resolved_model = model or self._settings.default_embedding_model

        if resolved_provider not in self._providers:
            raise ValueError(f"Unsupported embedding provider '{resolved_provider}'")

        if (
            resolved_provider != self._settings.default_embedding_provider
            or resolved_model != self._settings.default_embedding_model
        ):
            raise ValueError(
                "Indexed embeddings use the canonical configured provider/model only. "
                "Request-level embedding overrides must match the configured index pair."
            )

        return EmbeddingSelection(
            provider=resolved_provider,
            model=resolved_model,
            dimension=self._settings.canonical_embedding_dimension,
        )

    async def embed_texts(
        self,
        texts: list[str],
        provider: str | None = None,
        model: str | None = None,
    ) -> tuple[EmbeddingSelection, list[list[float]]]:
        selection = self.resolve_selection(provider, model)
        if not texts:
            return selection, []

        cache_key = None
        if self._cache is not None:
            cache_key = self._cache.make_key(
                "embeddings",
                {
                    "provider": selection.provider,
                    "model": selection.model,
                    "texts": texts,
                },
            )
            cached = await self._cache.get_json(cache_key)
            if isinstance(cached, list):
                return selection, cached

        embeddings = await self._providers[selection.provider].embed(texts, selection.model)

        for embedding in embeddings:
            if len(embedding) != selection.dimension:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {selection.dimension}, got {len(embedding)}"
                )

        if self._cache is not None and cache_key is not None:
            await self._cache.set_json(cache_key, embeddings)

        logger.info(
            "embeddings_generated provider=%s model=%s count=%s",
            selection.provider,
            selection.model,
            len(embeddings),
        )
        return selection, embeddings
