# {{ cookiecutter.project_name }}

> {{ cookiecutter.description }}

**Author:** {{ cookiecutter.author_name }}
**Python:** {{ cookiecutter.python_version }}
**Port:** {{ cookiecutter.port }}

---

## Quick Start

```bash
# Install dependencies
pip install -e ".[dev]"

# Run development server
uvicorn app.main:app --reload --port {{ cookiecutter.port }}
```
{%- if cookiecutter.docker == "yes" %}

### With Docker

```bash
# Start all services
docker compose up --build

# Logs
docker compose logs -f app
```
{%- if cookiecutter.docker_debug == "yes" %}

### Debug Mode (VS Code)

```bash
docker compose -f docker-compose.debug.yml up
# Attach VS Code debugger to port 5678
```
{%- endif %}
{%- endif %}

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/api/v1/{{ cookiecutter.model_name_plural }}` | List {{ cookiecutter.model_name_plural }} |
| `POST` | `/api/v1/{{ cookiecutter.model_name_plural }}` | Create {{ cookiecutter.model_name }} |
| `GET` | `/api/v1/{{ cookiecutter.model_name_plural }}/{id}` | Get {{ cookiecutter.model_name }} |
| `PUT` | `/api/v1/{{ cookiecutter.model_name_plural }}/{id}` | Update {{ cookiecutter.model_name }} |
| `DELETE` | `/api/v1/{{ cookiecutter.model_name_plural }}/{id}` | Delete {{ cookiecutter.model_name }} |

## Architecture (SOLID)

```
app/
├── main.py                          # App factory, middleware
├── config.py                        # Settings (pydantic-settings)
├── dependencies.py                  # FastAPI DI wiring
├── api/
│   ├── exception_handlers.py        # Structured error responses
│   ├── routes/
│   │   ├── health.py                # Health + readiness
│   │   └── {{ cookiecutter.model_name_plural }}.py             # CRUD routes
│   └── models/
│       └── {{ cookiecutter.model_name }}.py              # Pydantic schemas
├── services/
│   └── {{ cookiecutter.model_name }}_service.py          # Business logic
├── repositories/
│   └── {{ cookiecutter.model_name }}_repository.py       # Data access
{%- if cookiecutter.database != "none" %}
├── db/models/
│   └── {{ cookiecutter.model_name }}.py                  # DB model
{%- endif %}
└── middleware/
    ├── security_headers.py          # Security headers
    └── logging_middleware.py         # Request logging
```

## Tests

```bash
pytest tests/ -v
pytest tests/ --cov=app --cov-report=html
```

---

## Features
{%- if cookiecutter.logging == "structlog" %}

### Structured Logging

- **Library:** structlog
- **Format:** {{ cookiecutter.log_format }}
{%- if cookiecutter.log_connector != "stdout" %}
- **Connector:** {{ cookiecutter.log_connector }}
{%- endif %}
- Request correlation IDs via `X-Request-ID` header
{%- endif %}
{%- if cookiecutter.database == "postgres" %}

### Database (PostgreSQL)

- **Driver:** asyncpg via SQLAlchemy async
- Configure via `DATABASE_URL`
{%- endif %}
{%- if cookiecutter.database == "mysql" %}

### Database (MySQL)

- **Driver:** aiomysql via SQLAlchemy async
- Configure via `DATABASE_URL`
{%- endif %}
{%- if cookiecutter.database == "sqlite" %}

### Database (SQLite)

- **Driver:** aiosqlite via SQLAlchemy async
- Configure via `DATABASE_URL`
{%- endif %}
{%- if cookiecutter.database == "mongodb" %}

### Database (MongoDB)

- **Driver:** Motor (async)
- Configure via `MONGODB_URL`, `MONGODB_DATABASE`
{%- endif %}
{%- if cookiecutter.cache == "redis" %}

### Cache (Redis)

- **Library:** redis-py (async)
- Configure via `REDIS_URL`
- Usage: `from app.cache import get_cache`
{%- endif %}
{%- if cookiecutter.cache == "memcached" %}

### Cache (Memcached)

- **Library:** aiomcache
- Configure via `MEMCACHED_HOST`, `MEMCACHED_PORT`
- Usage: `from app.cache import get_cache`
{%- endif %}
{%- if cookiecutter.cache == "in_memory" %}

### Cache (In-Memory)

- **Library:** cachetools (TTLCache)
- 1024 items max, 5 min TTL
- Usage: `from app.cache import get_cache`
{%- endif %}
{%- if cookiecutter.streaming == "kafka" %}

### Streaming (Kafka)

- **Library:** aiokafka
- Producer: `from app.streaming.producer import send_event`
- Consumer auto-starts in lifespan, dispatches to `app/streaming/handler.py`
- Configure via `KAFKA_BOOTSTRAP_SERVERS`, `KAFKA_GROUP_ID`
{%- endif %}
{%- if cookiecutter.streaming == "rabbitmq" %}

### Streaming (RabbitMQ)

- **Library:** aio-pika
- Producer: `from app.streaming.producer import send_event`
- Consumer auto-starts in lifespan, dispatches to `app/streaming/handler.py`
- Configure via `RABBITMQ_URL`
{%- endif %}
{%- if cookiecutter.streaming == "redis_pubsub" %}

### Streaming (Redis Pub/Sub)

- **Library:** redis-py (async)
- Producer: `from app.streaming.producer import send_event`
- Consumer auto-starts in lifespan, dispatches to `app/streaming/handler.py`
- Configure via `REDIS_URL`
{%- endif %}
{%- if cookiecutter.streaming == "nats" %}

### Streaming (NATS)

- **Library:** nats-py
- Producer: `from app.streaming.producer import send_event`
- Consumer auto-starts in lifespan, dispatches to `app/streaming/handler.py`
- Configure via `NATS_URL`
{%- endif %}
{%- if cookiecutter.secrets == "vault" %}

### Secrets (HashiCorp Vault)

- **Library:** hvac
- Secrets loaded at startup into `app.state.secrets`
- Configure via `VAULT_URL`, `VAULT_TOKEN`
{%- endif %}
{%- if cookiecutter.secrets == "aws_sm" %}

### Secrets (AWS Secrets Manager)

- **Library:** boto3
- Secrets loaded at startup into `app.state.secrets`
- Configure via `AWS_REGION`, `AWS_SECRET_NAME`
{%- endif %}
{%- if cookiecutter.secrets == "azure_kv" %}

### Secrets (Azure Key Vault)

- **Library:** azure-keyvault-secrets + azure-identity
- Secrets loaded at startup into `app.state.secrets`
- Configure via `AZURE_VAULT_URL`
{%- endif %}
{%- if cookiecutter.secrets == "gcp_sm" %}

### Secrets (GCP Secret Manager)

- **Library:** google-cloud-secret-manager
- Secrets loaded at startup into `app.state.secrets`
- Configure via `GCP_PROJECT_ID`, `GCP_SECRET_NAME`
{%- endif %}
{%- if cookiecutter.quality_gate != "none" %}

### Quality Gate

- **Tool:** {{ cookiecutter.quality_gate }}
{%- endif %}
{%- if cookiecutter.docker == "yes" %}

### Containerization

- Multi-stage Dockerfile (slim base)
- Non-root user
- Health check built-in
{%- endif %}

## Environment

Configuration is managed via environment variables. See `.env.staging`.

## Extend Your Project

```bash
fastforge-infra           # Infrastructure (Kafka, ES, Vault, DB)
fastforge-cicd            # CI/CD pipeline
fastforge-secops          # Security tools
fastforge-helm            # Helm chart
fastforge-k8s             # Kubernetes manifests
fastforge-swarm           # Docker Swarm stack
fastforge-observability   # Tracing + Metrics
```

---

*Generated with [FastForge](https://github.com/jinnabaalu/fastforge)*
