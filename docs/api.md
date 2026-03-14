# API

Base URL during local development:

```text
http://localhost:9010
```

When using the provided Docker Compose stack, this base URL is exposed by the `app` container on the host.

If `HOST_APP_PORT` is set to a different value, replace `9010` in the examples with that host port.

## GET /health

Checks:

- API availability
- PostgreSQL connectivity
- Redis connectivity
- Ollama reachability
- OpenAI config presence
- Gemini config presence

### Example

```bash
curl http://localhost:9010/health
```

### Response shape

```json
{
  "status": "ok",
  "app": "backend-rag-multipurpose",
  "postgres": {
    "ok": true,
    "detail": "connected"
  },
  "redis": {
    "ok": true,
    "detail": "connected"
  },
  "providers": {
    "openai": {
      "ok": true,
      "detail": "configuration_present",
      "enabled": true,
      "provider": "openai",
      "capabilities": ["chat", "embeddings"],
      "configuration_present": true
    }
  },
  "assumptions": {
    "default_generation_provider": "openai",
    "default_generation_model": "gpt-4.1-mini",
    "default_embedding_provider": "openai",
    "default_embedding_model": "text-embedding-3-small"
  }
}
```

## POST /ingest/text

Accepts one or more raw text items in JSON.

### Request

```json
{
  "items": [
    {
      "title": "Company Overview",
      "content": "# Services\nWe offer AI chatbot implementation.",
      "source_type": "markdown",
      "url": "https://example.com/overview",
      "metadata": {
        "team": "sales"
      }
    }
  ],
  "embedding_provider": "openai",
  "embedding_model": "text-embedding-3-small"
}
```

### Example

```bash
curl -X POST http://localhost:9010/ingest/text ^
  -H "Content-Type: application/json" ^
  -d "{\"items\":[{\"title\":\"Company Overview\",\"content\":\"# Services\nWe offer AI chatbot implementation.\",\"source_type\":\"markdown\"}]}"
```

### Response shape

```json
{
  "documents_inserted": 1,
  "chunks_inserted": 1,
  "embedding_provider": "openai",
  "embedding_model": "text-embedding-3-small",
  "results": [
    {
      "filename": "Company Overview",
      "detected_type": "markdown",
      "success": true,
      "chunks_created": 1,
      "error": null,
      "document_id": "..."
    }
  ]
}
```

## POST /ingest/files

Accepts multipart form uploads.

### Multipart fields

- `files`: one or many files
- `source_type`: optional override
- `tags`: optional JSON array string, JSON string, or comma-separated string
- `metadata`: optional JSON object string or plain string
- `embedding_provider`: optional canonical embedding provider
- `embedding_model`: optional canonical embedding model

Notes for Swagger UI:

- leave optional multipart text inputs empty if you are not using them
- the backend ignores the Swagger placeholder value `string` for optional multipart text fields

### Example

```bash
curl -X POST http://localhost:9010/ingest/files ^
  -F "files=@C:\path\to\overview.md" ^
  -F "files=@C:\path\to\services.csv" ^
  -F "tags=[\"portfolio\",\"demo\"]" ^
  -F "metadata={\"team\":\"solutions\"}"
```

Also valid:

```bash
curl -X POST http://localhost:9010/ingest/files ^
  -F "files=@C:\path\to\overview.md" ^
  -F "tags=portfolio,demo"
```

Also valid:

```bash
curl -X POST http://localhost:9010/ingest/files ^
  -F "files=@C:\path\to\overview.md" ^
  -F "metadata=uploaded-from-swagger"
```

### Response shape

```json
{
  "total_files": 2,
  "succeeded": 2,
  "failed": 0,
  "total_chunks_inserted": 5,
  "embedding_provider": "openai",
  "embedding_model": "text-embedding-3-small",
  "results": [
    {
      "filename": "overview.md",
      "detected_type": "md",
      "success": true,
      "chunks_created": 2,
      "error": null,
      "document_id": "..."
    }
  ]
}
```

## POST /chat

Returns a full JSON response.

### Request

```json
{
  "message": "What services do we offer?",
  "session_id": "demo-session",
  "chat_history": [],
  "top_k": 5,
  "provider": "openai",
  "model": "gpt-4.1-mini",
  "embedding_provider": "openai",
  "embedding_model": "text-embedding-3-small"
}
```

### Example

```bash
curl -X POST http://localhost:9010/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"What services do we offer?\",\"provider\":\"openai\",\"model\":\"gpt-4.1-mini\"}"
```

### Response shape

```json
{
  "answer": "We offer AI chatbot implementation.",
  "citations": [
    {
      "document_id": "...",
      "chunk_id": "...",
      "title": "Company Overview",
      "url": null,
      "source_type": "markdown",
      "snippet": "We offer AI chatbot implementation.",
      "metadata": {
        "chunk_index": 0
      }
    }
  ],
  "provider": "openai",
  "model": "gpt-4.1-mini",
  "embedding_provider": "openai",
  "embedding_model": "text-embedding-3-small",
  "used_fallback": false
}
```

## POST /chat/stream

Returns Server-Sent Events.

### Example

```bash
curl -N -X POST http://localhost:9010/chat/stream ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"Summarize our offerings.\",\"provider\":\"ollama\",\"model\":\"llama3.1\"}"
```

### Event sequence

- `metadata`
- `chunk`
- `chunk`
- `done`

### `metadata` event payload

```json
{
  "provider": "ollama",
  "model": "llama3.1",
  "embedding_provider": "openai",
  "embedding_model": "text-embedding-3-small",
  "used_fallback": false
}
```

### `chunk` event payload

```json
{
  "delta": "partial text"
}
```

### `done` event payload

```json
{
  "answer": "final answer",
  "citations": [],
  "used_fallback": false
}
```

## Error behavior

- Invalid provider values return HTTP `400`
- Missing provider credentials return HTTP `400`
- Provider reachability failures return HTTP `503`
- Chat rate limit failures return HTTP `429`
