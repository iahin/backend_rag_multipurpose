from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.db.qdrant import QdrantManager
from app.models.schemas import ChunkRecord, ChunkUpsert


class ChunkRepository:
    def __init__(self, qdrant: QdrantManager) -> None:
        self._qdrant = qdrant

    async def bulk_create(
        self,
        document_id: UUID,
        chunks: list[ChunkUpsert],
        embedding_provider: str,
        embedding_model: str,
        embedding_profile: str,
        embedding_dimension: int,
    ) -> list[ChunkRecord]:
        if not chunks:
            return []

        collection_name = await self._qdrant.ensure_collection(embedding_dimension)
        created_at = datetime.now(timezone.utc)
        from qdrant_client.http import models

        points: list[models.PointStruct] = []
        records: list[ChunkRecord] = []
        for chunk in chunks:
            point_id = str(uuid4())
            title = str(chunk.metadata.get("title", ""))
            url = chunk.metadata.get("url")
            source_type = str(chunk.metadata.get("source_type", "text"))
            payload = {
                "document_id": str(document_id),
                "chunk_index": chunk.chunk_index,
                "title": title,
                "url": url,
                "source_type": source_type,
                "content": chunk.content,
                "metadata": chunk.metadata,
                "embedding_provider": embedding_provider,
                "embedding_model": embedding_model,
                "embedding_profile": embedding_profile,
                "created_at": created_at.isoformat(),
            }
            points.append(
                models.PointStruct(
                    id=point_id,
                    vector=chunk.embedding,
                    payload=payload,
                )
            )
            records.append(
                ChunkRecord(
                    id=UUID(point_id),
                    document_id=document_id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    metadata=chunk.metadata,
                    embedding_provider=embedding_provider,
                    embedding_model=embedding_model,
                    embedding_profile=embedding_profile,
                    created_at=created_at,
                )
            )

        await self._qdrant.client.upsert(
            collection_name=collection_name,
            points=points,
        )
        return records

    async def list_for_document(self, document_id: UUID, embedding_dimension: int) -> list[ChunkRecord]:
        collection_name = await self._qdrant.ensure_collection(embedding_dimension)
        from qdrant_client.http import models

        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(value=str(document_id)),
                )
            ]
        )

        points, _ = await self._qdrant.client.scroll(
            collection_name=collection_name,
            scroll_filter=query_filter,
            with_payload=True,
            with_vectors=False,
            limit=1000,
        )

        records: list[ChunkRecord] = []
        for point in points:
            payload = point.payload or {}
            records.append(
                ChunkRecord(
                    id=UUID(str(point.id)),
                    document_id=UUID(str(payload["document_id"])),
                    chunk_index=int(payload["chunk_index"]),
                    content=str(payload["content"]),
                    metadata=dict(payload.get("metadata", {})),
                    embedding_provider=str(payload["embedding_provider"]),
                    embedding_model=str(payload["embedding_model"]),
                    embedding_profile=str(payload.get("embedding_profile")) if payload.get("embedding_profile") is not None else None,
                    created_at=datetime.fromisoformat(str(payload["created_at"])),
                )
            )

        records.sort(key=lambda item: (item.chunk_index, item.created_at, str(item.id)))
        return records

    async def delete_for_document(self, document_id: UUID, embedding_dimension: int) -> int:
        collection_name = await self._qdrant.ensure_collection(embedding_dimension)
        from qdrant_client.http import models

        query_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="document_id",
                    match=models.MatchValue(value=str(document_id)),
                )
            ]
        )

        await self._qdrant.client.delete(
            collection_name=collection_name,
            points_selector=query_filter,
        )

        return 1
