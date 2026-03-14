from uuid import UUID, uuid4

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from app.models.schemas import ChunkRecord, ChunkUpsert


class ChunkRepository:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def bulk_create(
        self,
        document_id: UUID,
        chunks: list[ChunkUpsert],
        embedding_provider: str,
        embedding_model: str,
    ) -> list[ChunkRecord]:
        if not chunks:
            return []

        query = """
            INSERT INTO document_chunks (
                id,
                document_id,
                chunk_index,
                content,
                metadata,
                embedding_provider,
                embedding_model,
                embedding
            )
            VALUES (
                %(id)s,
                %(document_id)s,
                %(chunk_index)s,
                %(content)s,
                %(metadata)s,
                %(embedding_provider)s,
                %(embedding_model)s,
                %(embedding)s::vector
            )
            RETURNING
                id,
                document_id,
                chunk_index,
                content,
                metadata,
                embedding_provider,
                embedding_model,
                created_at
        """

        payload = [
            {
                "id": uuid4(),
                "document_id": document_id,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "metadata": Jsonb(chunk.metadata),
                "embedding_provider": embedding_provider,
                "embedding_model": embedding_model,
                "embedding": self._to_pgvector_literal(chunk.embedding),
            }
            for chunk in chunks
        ]

        inserted: list[dict] = []

        async with self._pool.connection() as connection:
            async with connection.cursor(row_factory=dict_row) as cursor:
                for item in payload:
                    await cursor.execute(query, item)
                    row = await cursor.fetchone()
                    if row is not None:
                        inserted.append(row)
            await connection.commit()

        return [ChunkRecord.model_validate(row) for row in inserted]

    def _to_pgvector_literal(self, embedding: list[float]) -> str:
        return "[" + ",".join(str(value) for value in embedding) + "]"

    async def list_for_document(self, document_id: UUID) -> list[ChunkRecord]:
        query = """
            SELECT
                id,
                document_id,
                chunk_index,
                content,
                metadata,
                embedding_provider,
                embedding_model,
                created_at
            FROM document_chunks
            WHERE document_id = %(document_id)s
            ORDER BY chunk_index ASC
        """

        async with self._pool.connection() as connection:
            async with connection.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, {"document_id": document_id})
                rows = await cursor.fetchall()

        return [ChunkRecord.model_validate(row) for row in rows]
