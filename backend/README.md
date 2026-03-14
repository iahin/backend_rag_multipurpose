# Backend Folder

Repository-level documentation now lives at:

- `README.md`
- `docs/architecture.md`
- `docs/api.md`
- `docs/ingestion.md`
- `docs/rag-pipeline.md`
- `docs/providers-and-models.md`
- `docs/redis-and-caching.md`
- `docs/deployment.md`
- `docs/runbook.md`

Use the root `README.md` as the primary entry point.

The Docker-first startup path is:

```bash
copy backend\.env.example backend\.env
docker compose -f backend/docker-compose.yml up --build -d
```

Default Docker-exposed API port is `9010`.

If host port `9010` is blocked, set:

```bash
set HOST_APP_PORT=8010
```

In the default setup, Ollama is not containerized. Run Ollama on the host machine.

Optional override for containerized Ollama:

```bash
copy backend\.env.example backend\.env
docker compose -f backend/docker-compose.yml -f backend/docker-compose.ollama.yml up --build -d
```
