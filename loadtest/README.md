# Load Testing

This repository includes small `k6` scripts for exercising the local Docker stack through `nginx`.

Target base URL by default:

- `http://localhost:9010`

## Prerequisites

1. Start the stack:

```bash
docker compose -f backend/docker-compose.yml up --build -d
```

2. Either install `k6` on the host or use the included Docker Compose override.

3. For chat tests, create a JWT first:

```bash
curl -X POST http://localhost:9010/auth/token ^
  -H "Content-Type: application/json" ^
  -d "{\"username\":\"admin\",\"password\":\"change-me-immediately\"}"
```

## Scripts

- `health.js` for proxy and app liveness
- `auth-token.js` for token issuance throughput
- `chat.js` for authenticated chat requests

## Run examples

Host-installed `k6`:

Health:

```bash
k6 run loadtest/health.js
```

Auth:

```bash
k6 run loadtest/auth-token.js
```

Chat:

```bash
k6 run -e JWT_TOKEN=YOUR_TOKEN loadtest/chat.js
```

Dockerized `k6`:

Health:

```bash
docker compose -f backend/docker-compose.yml -f backend/docker-compose.loadtest.yml run --rm k6 run /scripts/health.js
```

Auth:

```bash
docker compose -f backend/docker-compose.yml -f backend/docker-compose.loadtest.yml run --rm k6 run /scripts/auth-token.js
```

Chat:

```bash
docker compose -f backend/docker-compose.yml -f backend/docker-compose.loadtest.yml run --rm -e JWT_TOKEN=YOUR_TOKEN k6 run /scripts/chat.js
```

## Optional env vars

- `BASE_URL` default: `http://localhost:9010`
- `JWT_TOKEN` required for `chat.js`
- `CHAT_PROVIDER` default: `ollama`
- `CHAT_MODEL` default: `llama3.2`

## Notes

- Run tests through `nginx`, not against the app container directly.
- The Dockerized `k6` service uses the same Compose network and hits `http://nginx`.
- If you point chat at OpenAI or Gemini, load tests will create API cost.
- Start with low concurrency because local Docker runs `nginx`, app, PostgreSQL, and Redis on one machine.
