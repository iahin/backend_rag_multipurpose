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

Embedding providers are implemented through named profiles. That means:

- generation providers are fully switchable per request
- embedding provider/model/dimension are selected together through `embedding_profile`
- each embedding dimension is stored in its own Qdrant collection
- new dimensions are created automatically on first use

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
- `DEFAULT_EMBEDDING_PROFILE`
- `EMBEDDING_PROFILES`

Current repository defaults:

- `DEFAULT_LLM_PROVIDER=ollama`
- `DEFAULT_LLM_MODEL=llama3.2`
- `DEFAULT_EMBEDDING_PROFILE=ollama_1536`
- `EMBEDDING_PROFILES={"ollama_1536":{"provider":"ollama","model":"rjmalagon/gte-qwen2-1.5b-instruct-embed-f16","dimension":1536},"openai_small_1536":{"provider":"openai","model":"text-embedding-3-small","dimension":1536}}`
- `SIMILARITY_THRESHOLD=0.35`

Embedding profile registry:

- `DEFAULT_EMBEDDING_PROFILE` selects the active profile
- `EMBEDDING_PROFILES` defines the named provider/model/dimension map

## OpenAI

Generation route implementation:

- `POST https://api.openai.com/v1/chat/completions`

Embedding route implementation:

- `POST https://api.openai.com/v1/embeddings`

OpenAI is implemented and can be selected with a profile, but it is not the default path in the current `.env.example`.

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

## Error conditions

Examples:

- missing `OPENAI_API_KEY` returns a clear error
- missing `GEMINI_API_KEY` returns a clear error
- unreachable Ollama returns a clear error
- unsupported provider names return HTTP `400`
