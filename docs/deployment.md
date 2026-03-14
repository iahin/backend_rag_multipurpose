# Deployment

## Local container stack

The repository includes:

- `backend/docker-compose.yml` for the FastAPI app, PostgreSQL, and Redis
- `backend/Dockerfile` for the FastAPI service image

## Start the full stack

```bash
copy backend\.env.example backend\.env
docker compose -f backend/docker-compose.yml up --build -d
```

If host port `9010` is unavailable, override it before starting:

```bash
set HOST_APP_PORT=8010
docker compose -f backend/docker-compose.yml up --build -d
```

The Compose app service reads defaults from:

- `backend/.env.example`

For non-Compose local runs, you can still create:

- `backend/.env`

This starts:

- FastAPI app on `http://localhost:9010` by default
- PostgreSQL with pgvector image `pgvector/pgvector:pg16`
- Redis `redis:7.4-alpine`

Ollama is not containerized in the default stack.

Default behavior:

- run Ollama on the host machine
- the app container connects to `http://host.docker.internal:11434`

## Optional Ollama-in-Docker mode

If you want Ollama containerized too, use the override file:

```bash
copy backend\.env.example backend\.env
docker compose -f backend/docker-compose.yml -f backend/docker-compose.ollama.yml up --build -d
```

This adds:

- an `ollama` service
- an app override so `OLLAMA_BASE_URL` becomes `http://ollama:11434`

Pull models in that mode with:

```bash
docker exec -it rag_ollama ollama pull llama3.2
docker exec -it rag_ollama ollama pull qwen3-embedding
```

## Stop the full stack

```bash
docker compose -f backend/docker-compose.yml down
```

To remove named volumes too:

```bash
docker compose -f backend/docker-compose.yml down -v
```

## Application container build

```bash
docker build -f backend/Dockerfile -t rag-backend backend
```

## Application container run

```bash
docker run --rm -p 9010:8000 --env-file backend/.env rag-backend
```

If you run the app container outside Compose, make sure `POSTGRES_DSN`, `REDIS_URL`, and `OLLAMA_BASE_URL` point to reachable hosts. The Compose stack overrides those values to use service DNS names for Postgres and Redis, and host access for Ollama:

- `postgres`
- `redis`
- `host.docker.internal`

## Required env vars for deployment

- `POSTGRES_DSN`
- `REDIS_URL`
- `DEFAULT_LLM_PROVIDER`
- `DEFAULT_LLM_MODEL`
- `DEFAULT_EMBEDDING_PROVIDER`
- `DEFAULT_EMBEDDING_MODEL`
- `CANONICAL_EMBEDDING_DIMENSION`

Current repository default embedding settings:

- `DEFAULT_EMBEDDING_PROVIDER=ollama`
- `DEFAULT_EMBEDDING_MODEL=qwen3-embedding`
- `CANONICAL_EMBEDDING_DIMENSION=4096`
- `SIMILARITY_THRESHOLD=0.35`

Depending on provider usage:

- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `OLLAMA_BASE_URL`

## Database initialization

Schema file:

- `backend/app/db/schema.sql`

The Docker Compose setup mounts this file into PostgreSQL init scripts.

## Production notes

Implemented:

- async FastAPI app
- Redis-backed rate limiting
- health endpoint
- provider abstraction

Not yet implemented:

- migrations framework
- background workers
- auth
- TLS termination
- structured observability stack
- secrets manager integration
- multi-replica coordination

## Compose service notes

### app

- builds from `backend/Dockerfile`
- listens on container port `8000`
- exposed on host port `9010` by default
- depends on PostgreSQL and Redis health checks
- uses Compose-internal DNS names for dependency URLs

### postgres

- initializes schema from `backend/app/db/schema.sql`

### redis

- persists AOF data to a named volume

## Ollama setup

Default mode:

1. Install Ollama on the host machine
2. Start Ollama locally
3. Pull the models referenced by your config

Example:

```bash
ollama pull llama3.2
ollama pull qwen3-embedding
```

Containerized alternative:

```bash
docker exec -it rag_ollama ollama pull llama3.2
docker exec -it rag_ollama ollama pull qwen3-embedding
```
