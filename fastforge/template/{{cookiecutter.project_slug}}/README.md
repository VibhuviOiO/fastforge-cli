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
docker compose -f docker/docker-compose.yml up --build

# Start in detached mode (production)
docker compose -f docker/docker-compose.yml up --build -d

# View logs
docker compose -f docker/docker-compose.yml logs -f app

# Stop
docker compose -f docker/docker-compose.yml down

# Stop and remove volumes
docker compose -f docker/docker-compose.yml down -v
```
{%- if cookiecutter.docker_debug == "yes" %}

### Debug Mode (VS Code)

No virtual environment needed — Docker handles everything. Code changes auto-reload.

```bash
docker compose -f docker-compose.debug.yml up --build
```

Once running:
- **API docs** → [http://localhost:{{ cookiecutter.port }}/docs](http://localhost:{{ cookiecutter.port }}/docs)
- **Debugger** → Attach VS Code to port `5678` anytime (optional — app starts without waiting)
- **Auto-reload** → Edit files under `app/` and the server restarts automatically
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

{%- if cookiecutter.precommit == "yes" %}

### Code Quality

- **Linting**: ruff (replaces flake8 + isort + black)
- **Pre-commit hooks**: Automated ruff + pytest on every commit
- **Testing**: pytest + pytest-asyncio, async test client
- **Coverage**: `pytest --cov=app --cov-report=html`
{%- endif %}

## Environment

Configuration is managed via environment variables. See `.env.staging`.
{%- if cookiecutter.logging == "structlog" %}

## Log Integration
{%- if cookiecutter.log_agent != "none" %}

### Included: {{ cookiecutter.log_agent }} sidecar → {{ cookiecutter.log_target }}

A **{{ cookiecutter.log_agent }}** sidecar is included in `docker/docker-compose.yml`.
It reads structured JSON logs from `/var/log/app/*.log` and forwards them to **{{ cookiecutter.log_target }}**.

#### How it works

1. Your app writes JSON logs to **stdout** (visible in `docker logs`) AND to **/var/log/app/app.log**
2. The {{ cookiecutter.log_agent }} sidecar **reads the log file** and forwards entries to {{ cookiecutter.log_target }}
3. Both containers share a Docker volume (`app-logs`) for the log file

#### Getting started

```bash
# 1. Configure your {{ cookiecutter.log_target }} connection in .env.staging
{%- if cookiecutter.log_target == "kafka" %}
#    KAFKA_BOOTSTRAP_SERVERS=your-kafka:9092    (default: kafka:9092)
{%- elif cookiecutter.log_target == "elasticsearch" %}
#    ELASTICSEARCH_URL=http://your-elasticsearch:9200    (default: http://elasticsearch:9200)
{%- elif cookiecutter.log_target == "opensearch" %}
#    OPENSEARCH_URL=http://your-opensearch:9200    (default: http://opensearch:9200)
{%- elif cookiecutter.log_target == "loki" %}
#    LOKI_URL=http://your-loki:3100    (default: http://loki:3100)
{%- elif cookiecutter.log_target == "http" %}
#    LOG_HTTP_ENDPOINT=https://your-endpoint.example.com/logs
{%- endif %}

# 2. Start the app + {{ cookiecutter.log_agent }} sidecar
docker compose -f docker/docker-compose.yml up --build -d

# 3. Verify the app is running
curl http://localhost:{{ cookiecutter.port }}/health

# 4. Make some API calls to generate logs
curl http://localhost:{{ cookiecutter.port }}/api/v1/{{ cookiecutter.model_name_plural }}
curl -X POST http://localhost:{{ cookiecutter.port }}/api/v1/{{ cookiecutter.model_name_plural }} \
  -H "Content-Type: application/json" \
  -d '{"name": "test"}'

# 5. Check logs are being written to file
docker exec {{ cookiecutter.project_slug }}-dev cat /var/log/app/app.log

# 6. Check {{ cookiecutter.log_agent }} is forwarding
docker logs {{ cookiecutter.project_slug }}-{{ cookiecutter.log_agent }}
```

Config files:
{%- if cookiecutter.log_agent == "vector" %}
- `docker/vector/vector.toml` — Vector pipeline config
{%- endif %}
{%- if cookiecutter.log_agent == "fluentbit" %}
- `docker/fluentbit/fluent-bit.conf` — Fluent Bit pipeline config
- `docker/fluentbit/parsers.conf` — JSON log parser
{%- endif %}

### If your environment already has a log daemon

If you already have {{ cookiecutter.log_agent }} running as a DaemonSet (Kubernetes), systemd agent,
or per-node container (Marathon/Swarm), you don't need the sidecar.

**Option 1 — Shared volume mount (recommended for Marathon/Swarm):**

Mount the app's log volume into your existing agent and add this source:

{%- if cookiecutter.log_agent == "vector" %}
```toml
# Add to your existing vector.toml
[sources.{{ cookiecutter.project_slug }}_logs]
type = "file"
include = ["/var/log/{{ cookiecutter.project_slug }}/*.log"]
read_from = "beginning"
```
{%- endif %}
{%- if cookiecutter.log_agent == "fluentbit" %}
```ini
# Add to your existing fluent-bit.conf
[INPUT]
    Name         tail
    Path         /var/log/{{ cookiecutter.project_slug }}/*.log
    Tag          {{ cookiecutter.project_slug }}.*
    Parser       json
    Read_from_Head True
```
{%- endif %}

**Option 2 — Docker log driver (Kubernetes/Swarm with docker logging):**

If your agent collects from docker stdout (default in Kubernetes), switch the
app to stdout-only logging:

```env
# .env.staging
LOG_FILE_ENABLED=false
```

Then remove the {{ cookiecutter.log_agent }} sidecar from `docker/docker-compose.yml`.
{%- else %}

### Logs go to stdout (container output)

This project writes structured JSON logs to **stdout**. View them with:

```bash
# View live logs
docker logs -f {{ cookiecutter.project_slug }}-dev

# Or when using debug compose
docker logs -f {{ cookiecutter.project_slug }}-debug
```

To forward these logs to a centralized system, you have three options:

**Option A — Use an existing Vector daemon:**

```toml
# Add to your existing vector.toml
[sources.{{ cookiecutter.project_slug }}_docker]
type = "docker_logs"
docker_host = "unix:///var/run/docker.sock"
include_containers = ["{{ cookiecutter.project_slug }}-*"]

[transforms.{{ cookiecutter.project_slug }}_parse]
type = "remap"
inputs = ["{{ cookiecutter.project_slug }}_docker"]
source = '''
parsed, err = parse_json(.message)
if err == null { . = merge(., parsed); del(.message) }
.service = "{{ cookiecutter.project_slug }}"
'''

[sinks.{{ cookiecutter.project_slug }}_kafka]
type = "kafka"
inputs = ["{{ cookiecutter.project_slug }}_parse"]
bootstrap_servers = "kafka:9092"
topic = "{{ cookiecutter.project_slug }}-logs"
encoding.codec = "json"
```

**Option B — Use an existing Fluent Bit daemon:**

```ini
# Add to your existing fluent-bit.conf
[INPUT]
    Name          docker
    Tag           {{ cookiecutter.project_slug }}.*
    Docker_Include {{ cookiecutter.project_slug }}-*

[OUTPUT]
    Name          kafka
    Match         {{ cookiecutter.project_slug }}.*
    Brokers       kafka:9092
    Topics        {{ cookiecutter.project_slug }}-logs
    Format        json
```

**Option C — Enable file logging and add a sidecar:**

```env
# .env.staging
LOG_FILE_ENABLED=true
```

Then re-run `fastforge` in advanced mode to generate Vector or Fluent Bit
sidecar config, or add manually to `docker/docker-compose.yml`.
{%- endif %}
{%- endif %}

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

*Generated with [FastForge](https://pypi.org/project/fastforge-cli/)*
