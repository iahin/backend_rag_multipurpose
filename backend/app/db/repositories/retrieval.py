from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.models.schemas import RetrievedChunk


class RetrievalRepository:
    def __init__(self, pool: AsyncConnectionPool) -> None:
        self._pool = pool

    async def search_similar_chunks(
        self,
        embedding: list[float],
        limit: int,
        similarity_threshold: float,
        embedding_provider: str,
        embedding_model: str,
    ) -> list[RetrievedChunk]:
        query = """
            SELECT
                dc.id AS chunk_id,
                dc.document_id,
                d.title,
                d.url,
                d.source_type,
                dc.content,
                dc.metadata,
                1 - (dc.embedding <=> %(embedding)s::vector) AS similarity_score
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE dc.embedding_provider = %(embedding_provider)s
              AND dc.embedding_model = %(embedding_model)s
              AND 1 - (dc.embedding <=> %(embedding)s::vector) >= %(similarity_threshold)s
            ORDER BY dc.embedding <=> %(embedding)s::vector ASC
            LIMIT %(limit)s
        """

        params = {
            "embedding": self._to_pgvector_literal(embedding),
            "limit": limit,
            "similarity_threshold": similarity_threshold,
            "embedding_provider": embedding_provider,
            "embedding_model": embedding_model,
        }

        async with self._pool.connection() as connection:
            async with connection.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, params)
                rows = await cursor.fetchall()

        return [RetrievedChunk.model_validate(row) for row in rows]

    async def search_keyword_chunks(
        self,
        query_text: str,
        limit: int,
        embedding_provider: str,
        embedding_model: str,
    ) -> list[RetrievedChunk]:
        query = """
            SELECT
                dc.id AS chunk_id,
                dc.document_id,
                d.title,
                d.url,
                d.source_type,
                dc.content,
                dc.metadata,
                ts_rank_cd(
                    setweight(to_tsvector('simple', COALESCE(d.title, '')), 'A') ||
                    setweight(to_tsvector('simple', COALESCE(dc.content, '')), 'B'),
                    websearch_to_tsquery('simple', %(query_text)s)
                ) AS similarity_score
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE dc.embedding_provider = %(embedding_provider)s
              AND dc.embedding_model = %(embedding_model)s
              AND (
                    COALESCE(d.title, '') ILIKE %(search_pattern)s
                 OR COALESCE(dc.content, '') ILIKE %(search_pattern)s
                 OR (
                        %(query_text)s <> ''
                    AND (
                        setweight(to_tsvector('simple', COALESCE(d.title, '')), 'A') ||
                        setweight(to_tsvector('simple', COALESCE(dc.content, '')), 'B')
                    ) @@ websearch_to_tsquery('simple', %(query_text)s)
                 )
              )
            ORDER BY similarity_score DESC, dc.created_at DESC
            LIMIT %(limit)s
        """

        params = {
            "query_text": self._normalize_query_text(query_text),
            "search_pattern": self._to_ilike_pattern(query_text),
            "limit": limit,
            "embedding_provider": embedding_provider,
            "embedding_model": embedding_model,
        }

        async with self._pool.connection() as connection:
            async with connection.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, params)
                rows = await cursor.fetchall()

        return [RetrievedChunk.model_validate(row) for row in rows]

    async def search_best_available_chunks(
        self,
        embedding: list[float],
        limit: int,
        embedding_provider: str,
        embedding_model: str,
    ) -> list[RetrievedChunk]:
        query = """
            SELECT
                dc.id AS chunk_id,
                dc.document_id,
                d.title,
                d.url,
                d.source_type,
                dc.content,
                dc.metadata,
                1 - (dc.embedding <=> %(embedding)s::vector) AS similarity_score
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE dc.embedding_provider = %(embedding_provider)s
              AND dc.embedding_model = %(embedding_model)s
            ORDER BY dc.embedding <=> %(embedding)s::vector ASC
            LIMIT %(limit)s
        """

        params = {
            "embedding": self._to_pgvector_literal(embedding),
            "limit": limit,
            "embedding_provider": embedding_provider,
            "embedding_model": embedding_model,
        }

        async with self._pool.connection() as connection:
            async with connection.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(query, params)
                rows = await cursor.fetchall()

        return [RetrievedChunk.model_validate(row) for row in rows]

    def _to_pgvector_literal(self, embedding: list[float]) -> str:
        return "[" + ",".join(str(value) for value in embedding) + "]"

    def _to_ilike_pattern(self, query_text: str) -> str:
        normalized = self._normalize_query_text(query_text)
        return f"%{normalized}%"

    def _normalize_query_text(self, query_text: str) -> str:
        return " ".join(query_text.strip().split())
