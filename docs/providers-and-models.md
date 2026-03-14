# Providers and Models

## Generation providers

Implemented generation providers:

- OpenAI
- Gemini
- Ollama

These are switchable per request on:

- `POST /chat`
- `POST /chat/stream`

Relevant request fields:

- `provider`
- `model`

## Embedding providers

Implemented embedding providers:

- OpenAI
- Gemini
- Ollama

Relevant request fields:

- `embedding_provider`
- `embedding_model`

## Important constraint

Although embedding providers are implemented, the current index is single-column pgvector with fixed dimension. That means:

- generation providers are fully switchable per request
- embedding providers are not freely switchable for retrieval against the same index
- request-level embedding overrides must match the canonical configured pair

## Provider config env vars

- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `OLLAMA_BASE_URL`
- `OPENAI_ENABLED`
- `GEMINI_ENABLED`
- `OLLAMA_ENABLED`

## Defaults

- `DEFAULT_LLM_PROVIDER`
- `DEFAULT_LLM_MODEL`
- `DEFAULT_EMBEDDING_PROVIDER`
- `DEFAULT_EMBEDDING_MODEL`
- `CANONICAL_EMBEDDING_DIMENSION`

Current repository defaults:

- `DEFAULT_LLM_PROVIDER=ollama`
- `DEFAULT_LLM_MODEL=llama3.2`
- `DEFAULT_EMBEDDING_PROVIDER=ollama`
- `DEFAULT_EMBEDDING_MODEL=qwen3-embedding`
- `CANONICAL_EMBEDDING_DIMENSION=4096`
- `SIMILARITY_THRESHOLD=0.35`

## OpenAI

Generation route implementation:

- `POST https://api.openai.com/v1/chat/completions`

Embedding route implementation:

- `POST https://api.openai.com/v1/embeddings`

OpenAI is implemented but not the default path in the current `.env.example`.

## Gemini

Generation route implementation:

- `:generateContent`
- `:streamGenerateContent`

Embedding route implementation:

- `:embedContent`

Note:

- Gemini embeddings are implemented in code
- the current MVP still enforces the canonical embedding pair for indexed retrieval

## Ollama

Generation route implementation:

- `POST /api/chat`

Embedding route implementation:

- `POST /api/embeddings`

Health check route:

- `GET /api/tags`

Default runtime mode:

- Ollama runs outside Docker on the host machine
- the app container reaches it through `http://host.docker.internal:11434`

Optional runtime mode:

- Ollama can be added with `backend/docker-compose.ollama.yml`
- in that mode the app uses `http://ollama:11434`

Current default embedding model:

- `qwen3-embedding`

Current default embedding dimension:

- `4096`

## Error conditions

Examples:

- missing `OPENAI_API_KEY` returns a clear error
- missing `GEMINI_API_KEY` returns a clear error
- unreachable Ollama returns a clear error
- unsupported provider names return HTTP `400`
