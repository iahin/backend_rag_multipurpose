from psycopg_pool import AsyncConnectionPool

from app.db.qdrant import QdrantManager
from app.db.redis import RedisManager
from app.db.repositories.documents import DocumentRepository
from app.models.schemas import ResetResponse


class ResetService:
    def __init__(
        self,
        postgres_pool: AsyncConnectionPool,
        qdrant_manager: QdrantManager,
        redis_manager: RedisManager,
    ) -> None:
        self._document_repository = DocumentRepository(postgres_pool)
        self._qdrant = qdrant_manager
        self._redis_manager = redis_manager

    async def reset_all(self) -> ResetResponse:
        deletion_counts = await self._document_repository.delete_all()
        qdrant_deleted = await self._qdrant.delete_all_collections()
        redis_keys_deleted = await self._redis_manager.delete_by_prefixes(
            ["retrieval:", "embeddings:", "session:", "rate_limit:"]
        )

        return ResetResponse(
            status="ok",
            documents_deleted=deletion_counts["documents_deleted"],
            chunks_deleted=qdrant_deleted,
            redis_keys_deleted=redis_keys_deleted,
        )
