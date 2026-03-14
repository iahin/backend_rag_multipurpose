# Runbook

## Start the system

```bash
copy backend\.env.example backend\.env
docker compose -f backend/docker-compose.yml up --build -d
```

If `9010` is blocked on the host:

```bash
set HOST_APP_PORT=8010
docker compose -f backend/docker-compose.yml up --build -d
```

## Start the system with Ollama in Docker

```bash
copy backend\.env.example backend\.env
docker compose -f backend/docker-compose.yml -f backend/docker-compose.ollama.yml up --build -d
```

## Verify the stack

```bash
curl http://localhost:9010/health
```

If you changed `HOST_APP_PORT`, replace `9010` with that value in every curl command.

Check:

- app container is healthy
- PostgreSQL `ok`
- Redis `ok`
- provider configuration status
- Ollama `ok` if enabled and running on the host

## Inspect running containers

```bash
docker compose -f backend/docker-compose.yml ps
```

## Pull Ollama models on the host

If you use Ollama, pull the generation and embedding models on the host machine:

```bash
ollama pull llama3.2
ollama pull qwen3-embedding
```

If you use the Docker override instead:

```bash
docker exec -it rag_ollama ollama pull llama3.2
docker exec -it rag_ollama ollama pull qwen3-embedding
```

## Ingest sample content

```bash
curl -X POST http://localhost:9010/ingest/text ^
  -H "Content-Type: application/json" ^
  -d "{\"items\":[{\"title\":\"Overview\",\"content\":\"We offer AI chatbot implementation.\",\"source_type\":\"text\"}]}"
```

## Run a chat request

```bash
curl -X POST http://localhost:9010/chat ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"What do we offer?\",\"provider\":\"openai\",\"model\":\"gpt-4.1-mini\"}"
```

## Run a streaming chat request

```bash
curl -N -X POST http://localhost:9010/chat/stream ^
  -H "Content-Type: application/json" ^
  -d "{\"message\":\"What do we offer?\",\"provider\":\"ollama\",\"model\":\"llama3.2\"}"
```

## Run tests

If host-installed pytest plugins interfere with collection, disable plugin autoload:

```bash
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -m pytest backend/tests
```

## Common issues

### Health endpoint shows degraded

Check:

- `POSTGRES_DSN`
- `REDIS_URL`
- provider API keys
- Ollama service availability
- `docker compose -f backend/docker-compose.yml ps`
- verify Ollama is listening on `http://localhost:11434`

### Ingest rejects embedding override

Cause:

- embedding overrides must match the canonical configured embedding pair in this MVP

### Embedding dimension mismatch

Example:

- `expected 1536, got 4096`

Cause:

- the configured canonical embedding dimension does not match the actual embedding model output

Current default local Ollama setup expects:

- provider: `ollama`
- model: `qwen3-embedding`
- dimension: `4096`

If you changed the schema or old volumes still contain a `VECTOR(1536)` table definition, recreate the database volume and reinitialize the schema.

### Chat returns fallback unexpectedly

Check:

- documents were ingested successfully
- canonical embedding configuration matches the indexed corpus
- `SIMILARITY_THRESHOLD` is not too high
- the ingested chunk text or titles actually contain the terms you are asking about

Current retrieval order:

- pgvector cosine similarity search
- lexical fallback against stored titles and chunk content
- best available semantic matches without applying the threshold
- safe fallback response only if no chunks exist for the active embedding pair

Current default local Ollama threshold:

- `SIMILARITY_THRESHOLD=0.35`

### Chat returns HTTP 429

Cause:

- Redis rate limit exceeded for the current session or client IP

Adjust:

- `CHAT_RATE_LIMIT_REQUESTS`
- `CHAT_RATE_LIMIT_WINDOW_SECONDS`

### Streaming route does not emit tokens

Check:

- selected provider credentials are valid
- upstream provider supports the selected generation model
- Ollama model is actually pulled on the host machine

## Stop the system

```bash
docker compose -f backend/docker-compose.yml down
```
