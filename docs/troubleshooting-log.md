# Troubleshooting Log

This file records concrete errors encountered during setup and deployment, with the likely cause and the fix that resolved them.

## Docker and local runtime

### Nginx startup error: `"worker_processes" directive is not allowed here`

Error:

```text
/docker-entrypoint.sh: Configuration complete; ready for start up
2026/03/19 16:00:56 [emerg] 1#1: "worker_processes" directive is not allowed here in /etc/nginx/conf.d/default.conf:1
nginx: [emerg] "worker_processes" directive is not allowed here in /etc/nginx/conf.d/default.conf:1
```

Cause:

- a full top-level `nginx.conf` was rendered into `/etc/nginx/conf.d/default.conf`
- `conf.d/default.conf` only accepts `server`-level config, not top-level directives like `worker_processes`

Solution:

- render the template into `/etc/nginx/nginx.conf` instead
- start Nginx with a custom `CMD` after `envsubst`

Relevant file:

- `backend/nginx/Dockerfile`

### Compose startup failure: `dependency app failed to start: container rag_app is unhealthy`

Error:

```text
Container rag_app Error dependency app failed to start
dependency failed to start: container rag_app is unhealthy
```

Cause:

- the app container was given `APP_PORT=9010`
- the app healthcheck and Nginx upstream were still targeting `8000`

Solution:

- set container `APP_PORT` to `8000` inside `backend/docker-compose.yml`
- keep host exposure on Nginx via `HOST_PROXY_PORT`

Relevant file:

- `backend/docker-compose.yml`

### Local Docker ignored edited `backend/.env`

Symptom:

- local config changes in `backend/.env` did not take effect
- the container still behaved as if `.env.example` values were active

Cause:

- `backend/docker-compose.yml` loaded `.env.example` as the app `env_file`
- editing `backend/.env` therefore had no effect on the container

Solution:

- change the Compose app service to load `.env`
- keep `.env.example` only as the template to copy from

Relevant file:

- `backend/docker-compose.yml`

### Docker tag failure: `No such image: rag-backend:latest`

Error:

```text
Error response from daemon: No such image: rag-backend:latest
```

Cause:

- the local image had not been built yet under that tag

Solution:

1. Build the image first:

```powershell
docker build -f backend/Dockerfile -t rag-backend:latest backend
```

2. Verify it exists:

```powershell
docker images | findstr rag-
```

3. Then tag and push it to ECR.

Relevant file:

- `deploy/ecs/README.md`

### Docker push failure: `no basic auth credentials`

Error:

```text
no basic auth credentials
```

Cause:

- Docker was not logged in to the ECR registry
- `aws login` does not authenticate Docker for `docker push`

Solution:

Authenticate Docker to ECR first:

```powershell
aws ecr get-login-password --region ap-southeast-1 | docker login --username AWS --password-stdin 961341555117.dkr.ecr.ap-southeast-1.amazonaws.com
```

Then push the image again.

Relevant file:

- `deploy/ecs/README.md`

## ECS and Fargate deployment

### ECS service launch failure: unable to assume `ecsTaskRole`

Error:

```text
(service backend-rag-multipurpose) failed to launch a task with
(error ECS was unable to assume the role
'arn:aws:iam::...:role/ecsTaskRole' ...)
```

Cause:

- `ecsTaskRole` did not exist, or
- its trust relationship did not allow `ecs-tasks.amazonaws.com`, or
- the deploying identity did not have permission to pass the role

Solution:

- create `ecsTaskRole`
- set its trust policy to allow `ecs-tasks.amazonaws.com`
- if deploying with a non-root IAM identity, also allow `iam:PassRole`

Trust policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

Relevant file:

- `deploy/ecs/README.md`

### Fargate task startup failure: `AccessDeniedException` for `ssm:GetParameters`

Error:

```text
ResourceInitializationError: unable to pull secrets or registry auth:
unable to retrieve secrets from ssm ...
AccessDeniedException:
... is not authorized to perform: ssm:GetParameters ...
```

Cause:

- `ecsTaskExecutionRole` did not have permission to read SSM parameters

Solution:

- add `ssm:GetParameters` permission to `ecsTaskExecutionRole`
- if `SecureString` uses a customer-managed KMS key, also add `kms:Decrypt`

Example policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ssm:GetParameters"
      ],
      "Resource": [
        "arn:aws:ssm:ap-southeast-1:961341555117:parameter/backend-rag/OPENAI_API_KEY",
        "arn:aws:ssm:ap-southeast-1:961341555117:parameter/backend-rag/AUTH_JWT_SECRET",
        "arn:aws:ssm:ap-southeast-1:961341555117:parameter/backend-rag/AUTH_BOOTSTRAP_ADMIN_USERNAME",
        "arn:aws:ssm:ap-southeast-1:961341555117:parameter/backend-rag/AUTH_BOOTSTRAP_ADMIN_PASSWORD"
      ]
    }
  ]
}
```

Relevant file:

- `deploy/ecs/README.md`

### PostgreSQL init failure: `column cannot have more than 2000 dimensions for ivfflat index`

Error:

```text
ERROR: column cannot have more than 2000 dimensions for ivfflat index
STATEMENT: CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding
ON document_chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

Cause:

- the schema used `VECTOR(4096)`
- `ivfflat` in pgvector does not support more than `2000` dimensions
- the deployment path was switched to a `1536`-dimension canonical embedding model, so the schema and runtime config were inconsistent

Solution:

- change the schema to `VECTOR(1536)`
- align the default embedding configuration to a `1536`-dimension canonical embedding model
- rebuild and push the Postgres image again
- redeploy the ECS service

Relevant files:

- `backend/app/db/schema.sql`
- `backend/app/core/config.py`
- `backend/.env.example`

## Usage

When a new setup or deployment issue appears, add:

1. the exact error message
2. the likely cause
3. the fix
4. the related file or AWS resource
