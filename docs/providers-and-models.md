# Providers and Models

## Generation providers

Implemented generation providers:

- OpenAI
- Gemini
- Ollama
- NVIDIA NIM via the `nim` provider alias

These are switchable per request on:

- `POST /chat`
- `POST /chat/stream`

Relevant request fields:

- `provider`
- `model`

Default generation selection can also be profile-based through:

- `DEFAULT_LLM_PROFILE`
- `GENERATION_PROFILES`

## Embedding providers

Implemented embedding providers:

- OpenAI
- Gemini
- Ollama
- NVIDIA NIM via the `nim` provider alias

Relevant request fields:

- `embedding_provider`
- `embedding_model`

## Important constraint

Embedding providers are implemented through named profiles. That means:

- generation providers are fully switchable per request
- embedding provider/model/dimension are selected together through `embedding_profile`
- each embedding dimension is stored in its own Qdrant collection
- new dimensions are created automatically on first use

## Provider config env vars

- `OPENAI_API_KEY`
- `NIM_API_KEY`
- `GEMINI_API_KEY`
- `OLLAMA_BASE_URL`
- `RERANK_ENABLED`
- `RERANK_MODEL`
- `CHAT_THINKING_ENABLED`

## Defaults

- `DEFAULT_LLM_PROFILE`
- `GENERATION_PROFILES`
- `DEFAULT_EMBEDDING_PROFILE`
- `EMBEDDING_PROFILES`

Current repository defaults:

- `DEFAULT_LLM_PROFILE=ollama_llama32`
- `GENERATION_PROFILES={"nim_3super120":{"provider":"nim","model":"nvidia/nemotron-3-super-120b-a12b"},"openai_gpt41_mini":{"provider":"openai","model":"gpt-4.1-mini"},"ollama_llama32":{"provider":"ollama","model":"llama3.2"}}`
- `DEFAULT_EMBEDDING_PROFILE=ollama_1536`
- `EMBEDDING_PROFILES={"ollama_1536":{"provider":"ollama","model":"rjmalagon/gte-qwen2-1.5b-instruct-embed-f16","dimension":1536},"openai_small_1536":{"provider":"openai","model":"text-embedding-3-small","dimension":1536}}`
- `SIMILARITY_THRESHOLD` uses the code default
- `RERANK_ENABLED=false`

Generation profile registry:

- `DEFAULT_LLM_PROFILE` selects the default generation profile when set
- `GENERATION_PROFILES` defines named provider/model pairs for chat defaults

Embedding profile registry:

- `DEFAULT_EMBEDDING_PROFILE` selects the active profile
- `EMBEDDING_PROFILES` defines the named provider/model/dimension map

## OpenAI

Generation route implementation:

- `POST https://api.openai.com/v1/chat/completions`

Embedding route implementation:

- `POST https://api.openai.com/v1/embeddings`

OpenAI is implemented and can be selected with a profile, but it is not the default path in the current `.env.example`.

OpenAI uses the fixed public API endpoint internally, so there is no `OPENAI_BASE_URL` setting to manage.

NIM is implemented as a dedicated alias so the config stays explicit:

- generation uses `DEFAULT_LLM_PROFILE=nim_3super120`
- generation and embeddings use the built-in NVIDIA base URL unless you override it in env
- embeddings use a profile with `provider="nim"`
- NIM thinking follows `CHAT_THINKING_ENABLED` and falls back automatically if the model rejects reasoning mode

Relevant NIM model IDs:

- `nvidia/llama-3.3-nemotron-super-49b-v1.5`
- `nvidia/llama-nemotron-embed-1b-v2`
- `nvidia/llama-nemotron-rerank-1b-v2`

The embed model uses a `2048`-dimensional vector space, so its Qdrant profile should declare `dimension=2048`.

## Gemini

Generation route implementation:

- `:generateContent`
- `:streamGenerateContent`

Embedding route implementation:

- `:embedContent`

Note:

- Gemini embeddings are implemented in code
- the current MVP stores each embedding dimension in its own Qdrant collection

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

Current default Ollama embedding model:

- `rjmalagon/gte-qwen2-1.5b-instruct-embed-f16`

Current default Ollama embedding dimension:

- `1536`

## Reranking

Reranking is optional and disabled by default.

When enabled, retrieval will over-fetch candidates and send them through the configured reranker before the prompt is built.

Implementation route:

- `POST /v1/ranking`

Default NVIDIA rerank model:

- `nvidia/llama-nemotron-rerank-1b-v2`

## Error conditions

Examples:

- missing `OPENAI_API_KEY` returns a clear error
- missing `GEMINI_API_KEY` returns a clear error
- missing `NIM_API_KEY` returns a clear error when the configured NIM endpoint requires one
- unreachable Ollama returns a clear error
- missing `NIM_API_KEY` returns a clear error when the configured rerank endpoint requires one
- unsupported provider names return HTTP `400`
