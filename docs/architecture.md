# Architecture

## Overview

The project is a backend-only RAG chatbot service with these runtime dependencies:

- FastAPI application layer
- PostgreSQL as the primary data store
- pgvector for embedding storage and similarity search
- Redis for rate limiting, caching, and optional session state
- Provider adapters for OpenAI, Gemini, and Ollama

## High-level flow

1. Documents are ingested through `POST /ingest/text` or `POST /ingest/files`.
2. Inputs are normalized into a shared internal document model.
3. Text is chunked.
4. Chunks are embedded using the canonical configured embedding provider/model.
5. Documents and chunks are stored in PostgreSQL.
6. A chat request embeds the user query with the same canonical embedding pair.
7. pgvector retrieves top matching chunks above the configured similarity threshold.
8. A grounded prompt is built from retrieved context.
9. The selected generation provider produces either a full answer or a streaming answer.

## Code layout

```text
backend/app/
├── api/         # FastAPI routes
├── core/        # config, logging, rate limiting
├── db/          # connection managers, schema, repositories
├── models/      # Pydantic schemas
├── parsers/     # file parsing and normalization
├── providers/   # provider abstraction and implementations
└── services/    # chunking, embeddings, retrieval, prompting, chat, ingest
```

## Separation of concerns

- Route handlers stay thin and delegate to services.
- Provider-specific logic is isolated under `backend/app/providers/`.
- PostgreSQL access is isolated under `backend/app/db/repositories/`.
- File-type-specific parsing stays under `backend/app/parsers/`.
- RAG orchestration lives in `backend/app/services/`.

## Data model

Primary tables:

- `documents`
- `document_chunks`

Important fields:

- `documents.title`
- `documents.url`
- `documents.source_type`
- `documents.metadata`
- `documents.original_filename`
- `documents.mime_type`
- `document_chunks.content`
- `document_chunks.metadata`
- `document_chunks.embedding`

## Current architectural limitations

- One canonical embedding provider/model is enforced for indexed data.
- Request payloads expose `embedding_provider` and `embedding_model`, but they must match the canonical configured pair in this MVP.
- Provider streaming is implemented, but integration tests against live providers are not included.

Current repository default canonical embedding pair:

- provider: `ollama`
- model: `qwen3-embedding`
- dimension: `4096`
