# Redis and Caching

## Redis usage in the implementation

Redis is used for:

- chat rate limiting
- retrieval result caching
- embedding caching
- optional session history storage

Redis is not used as the vector store.

## Rate limiting

Implemented in:

- `backend/app/core/rate_limit.py`

Applied in:

- `backend/app/services/chat_service.py`

Config:

- `CHAT_RATE_LIMIT_REQUESTS`
- `CHAT_RATE_LIMIT_WINDOW_SECONDS`

Behavior:

- a Redis counter key is created per time bucket
- requests beyond the limit return HTTP `429`

## Embedding cache

Implemented in:

- `backend/app/services/cache_service.py`
- `backend/app/services/embeddings.py`

Config:

- `EMBEDDING_CACHE_TTL_SECONDS`

Cache key includes:

- provider
- model
- input texts

## Retrieval cache

Implemented in:

- `backend/app/services/retrieval.py`

Config:

- `RETRIEVAL_CACHE_TTL_SECONDS`

Cache key includes:

- canonical embedding provider
- canonical embedding model
- query embedding
- `top_k`
- `SIMILARITY_THRESHOLD`

## Session storage

Implemented in:

- `backend/app/services/session_service.py`

Config:

- `SESSION_STORAGE_ENABLED`
- `SESSION_TTL_SECONDS`
- `MAX_SESSION_MESSAGES`

Behavior:

- disabled by default
- when enabled, user and assistant messages are stored in Redis by `session_id`
- stored history is trimmed to the most recent configured message count

## Operational notes

- Redis must be reachable for chat rate limiting to work
- cache misses do not break functionality
- Redis data is non-authoritative and safe to clear
