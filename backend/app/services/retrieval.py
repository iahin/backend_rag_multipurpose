from psycopg_pool import AsyncConnectionPool

from app.core.config import Settings
from app.db.redis import RedisManager
from app.db.repositories.retrieval import RetrievalRepository
from app.models.schemas import EmbeddingSelection, RetrievedChunk
from app.services.cache_service import CacheService


class RetrievalService:
    def __init__(
        self,
        settings: Settings,
        postgres_pool: AsyncConnectionPool,
        redis_manager: RedisManager,
    ) -> None:
        self._settings = settings
        self._repository = RetrievalRepository(postgres_pool)
        self._cache = CacheService(
            redis_manager.client,
            ttl_seconds=settings.retrieval_cache_ttl_seconds,
        )

    async def retrieve(
        self,
        query_text: str,
        query_embedding: list[float],
        selection: EmbeddingSelection,
        top_k: int,
    ) -> list[RetrievedChunk]:
        cache_key = self._cache.make_key(
            "retrieval",
            {
                "embedding_provider": selection.provider,
                "embedding_model": selection.model,
                "top_k": top_k,
                "query_text": query_text,
                "query_embedding": query_embedding,
                "similarity_threshold": self._settings.similarity_threshold,
            },
        )
        cached = await self._cache.get_json(cache_key)
        if isinstance(cached, list):
            return [RetrievedChunk.model_validate(item) for item in cached]

        results = await self._repository.search_similar_chunks(
            embedding=query_embedding,
            limit=top_k,
            similarity_threshold=self._settings.similarity_threshold,
            embedding_provider=selection.provider,
            embedding_model=selection.model,
        )
        if not results and query_text.strip():
            results = await self._repository.search_keyword_chunks(
                query_text=query_text,
                limit=top_k,
                embedding_provider=selection.provider,
                embedding_model=selection.model,
            )
        if not results:
            results = await self._repository.search_best_available_chunks(
                embedding=query_embedding,
                limit=top_k,
                embedding_provider=selection.provider,
                embedding_model=selection.model,
            )
        await self._cache.set_json(cache_key, [item.model_dump(mode="json") for item in results])
        return results
