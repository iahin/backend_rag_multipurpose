# RAG Pipeline

## Pipeline steps

1. Accept user query on `/chat` or `/chat/stream`
2. Rate-limit the request in Redis
3. Resolve generation provider/model from the request or config defaults
4. Resolve canonical embedding provider/model from the request or config defaults
5. Embed the query with the canonical embedding provider
6. Retrieve top matching chunks from pgvector
7. Filter vector results using `SIMILARITY_THRESHOLD`
8. If vector retrieval returns nothing, run a lexical fallback against stored titles and chunk content
9. If lexical retrieval still returns nothing, use the best available semantic matches without applying the threshold
10. If no chunks exist for the active embedding pair, return the safe fallback
11. Build a grounded prompt from retrieved chunks
12. Generate the answer using the selected generation provider
13. Return citations and metadata
14. Optionally store session messages in Redis

## Retrieval query

The implementation uses cosine similarity in PostgreSQL with pgvector:

```sql
1 - (dc.embedding <=> %(embedding)s::vector)
```

Results are filtered by:

- `embedding_provider`
- `embedding_model`
- `similarity_threshold`
- `top_k`

## Grounding behavior

The system prompt explicitly instructs the model to:

- answer only from the provided context
- not invent services, pricing, experience, or facts
- say it does not know when context is insufficient

## Fallback behavior

If vector retrieval returns no chunks above the threshold, the system tries a second-stage lexical lookup over `documents.title` and `document_chunks.content`. If that still returns nothing, it falls back to the best available semantic matches for the active embedding pair. Only if no chunks exist at all for that embedding pair does the system return:

```text
I couldn't find that in the knowledge base.
```

This is returned for:

- `POST /chat`
- `POST /chat/stream`

## Citations

Citations are built from retrieved chunks and include:

- `document_id`
- `chunk_id`
- `title`
- `url`
- `source_type`
- `snippet`
- `metadata`

## Current limitations

- No reranking stage
- No multi-index support for different embedding dimensions
- No document deletion endpoint
- Broad questions over tiny corpora may still retrieve weak matches because the final fallback prefers grounded recall over an empty answer

Current default indexed embedding setup:

- provider: `ollama`
- model: `qwen3-embedding`
- dimension: `4096`
- similarity threshold: `0.35`
