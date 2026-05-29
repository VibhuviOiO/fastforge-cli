# 🔨 FastForge

**Production-grade FastAPI project generator for Python backends.**

[![PyPI](https://img.shields.io/pypi/v/fastforge-cli)](https://pypi.org/project/fastforge-cli/)
[![Python](https://img.shields.io/pypi/pyversions/fastforge-cli)](https://pypi.org/project/fastforge-cli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

FastForge generates a **ready-to-run, production-grade FastAPI project** with SOLID architecture, structured logging, Docker containerization, and async CRUD — all in under 30 seconds.

## Use Cases

FastForge is for teams and developers who need to ship production Python APIs fast:

| Use Case | What FastForge Generates |
|---|---|
| **Microservice backend** | REST API with async CRUD, health checks, structured logging, Docker — ready to deploy |
| **Event-driven service** | Kafka/RabbitMQ/NATS producer + consumer, structured events, async processing |
| **Data API layer** | PostgreSQL/MySQL/MongoDB with async ORM, repository pattern, Pydantic schemas |
| **Internal tooling API** | Fast scaffolding with security headers middleware, CORS, structured error handling |
| **Hackathon / MVP** | Working API with Docker in 30 seconds — skip the boilerplate, start building |
| **Team standardization** | Enforce consistent architecture, logging, testing, and deployment patterns across projects |

### Example: Build an Order Service

```bash
$ pip install fastforge-cli
$ fastforge new

? Project name: order-service
? Model name: order
? Log output: Stdout + File
? Log agent: Vector
? Log target: Elasticsearch
? Include debug compose? Yes
? Generate project? Yes

✔ Project created: ./order-service

$ cd order-service
$ docker compose -f infra/docker-compose.yml up --build
# API running at http://localhost:8000/docs
```

## Standards & Architecture

Every generated project follows these standards:

### SOLID Principles

| Principle | Implementation |
|---|---|
| **Single Responsibility** | Each layer has one job: routes handle HTTP, services hold business logic, repositories manage data |
| **Open/Closed** | Add new models by creating new files — no modification to existing code needed |
| **Liskov Substitution** | Repository interfaces allow swapping implementations (in-memory → PostgreSQL) |
| **Interface Segregation** | Small, focused interfaces — `Repository` protocol with only the methods each consumer needs |
| **Dependency Inversion** | FastAPI's `Depends()` wires everything; services depend on abstractions, not implementations |

### 12-Factor App Compliance

| Factor | Implementation |
|---|---|
| **Config** | `pydantic-settings` — all config via environment variables |
| **Dependencies** | `pyproject.toml` with pinned versions, no system-level deps |
| **Backing services** | Database, cache, streaming attached via URL config — swap by changing env vars |
| **Port binding** | Self-contained HTTP server via uvicorn |
| **Concurrency** | Async I/O with `asyncio` — scales via process managers (gunicorn, uvicorn workers) |
| **Logs** | Structured JSON to stdout/file — treat logs as event streams |
| **Dev/prod parity** | Same Docker image for dev and prod, identical dependencies |
| **Disposability** | Graceful shutdown via lifespan events, health checks for orchestrators |

### Code Quality

- **Linting**: ruff (replaces flake8 + isort + black)
- **Testing**: pytest + pytest-asyncio, async test client
- **Type safety**: Pydantic models for all request/response schemas
- **Pre-commit hooks**: Automated ruff + pytest on every commit
- **Security**: Non-root Docker user, security headers middleware, CORS configuration

## Quick Start

```bash
pip install fastforge-cli
fastforge new
```

Answer a few prompts and you get a running application.

### Non-Interactive / Preset-Driven Generation

Skip the prompts entirely with a **built-in preset** (works straight from `pip install`, no repo clone needed):

```bash
# List all available presets
fastforge list-presets

# Generate from a built-in preset
fastforge new --preset simple-fastapi
fastforge new --preset postgres-api
fastforge new --preset observable-api
fastforge new --preset rag-observable

# Override the project name (preset stays the same)
fastforge new --preset postgres-api --name my-order-service
```

You can also load presets from a custom file (JSON or YAML):

```bash
fastforge new --from-file ./my-team-preset.fastforge.json
fastforge new --from-file ./my-team-preset.fastforge.yaml
```

The repo also ships example presets under [`examples/use-cases/`](examples/use-cases/) you can copy and tweak.

## What You Get (Basic Mode)

| Feature | Implementation |
|---|---|
| **SOLID Architecture** | Repository pattern + Service layer + Dependency Injection |
| **Async CRUD API** | FastAPI with full Create/Read/Update/Delete |
| **Structured Logging** | structlog with JSON output, request IDs, duration tracking |
| **Docker** | Slim Dockerfile, docker-compose, health checks |
| **Debug Docker** | `docker-compose.debug.yml` at project root — no venv needed, auto-reload, debugpy on port 5678 |
| **Security** | Security headers middleware, CORS, non-root container |
| **Testing** | pytest + pytest-asyncio, 80%+ coverage out of the box |
| **Code Quality** | ruff linting, pre-commit hooks |

## CLI Flow

```
$ fastforge new

  ╔═╗╔═╗╔═╗╔╦╗  ╔═╗╔═╗╦═╗╔═╗╔═╗
  ╠╣ ╠═╣╚═╗ ║   ╠╣ ║ ║╠╦╝║ ╦║╣
  ╚  ╩ ╩╚═╝ ╩   ╚  ╚═╝╩╚═╚═╝╚═╝
  Production-grade FastAPI Generator

┌─ Choose your path ───────────────────────────────────┐
│ Basic mode  → SOLID app, JSON logging, Docker, async │
│ Advanced    → + Database, Cache, Streaming, Secrets  │
└──────────────────────────────────────────────────────┘

? Project name: order-service
? Model name: order
? Log output: Stdout + File
? Log agent: Vector
? Log target: Elasticsearch
? Include debug compose? Yes
? Generate project? Yes

✔ Project created: ./order-service
```

### Basic Mode (default)

Just 4-5 questions → production-ready app with structured logging, Docker, and CRUD.

### Advanced Mode

Enable with "Enable advanced configuration?" → unlocks:

- **Database** — PostgreSQL, MySQL, SQLite (SQLAlchemy async), MongoDB (Motor)
- **Cache** — Redis, Memcached, In-memory (cachetools)
- **Streaming** — Kafka, RabbitMQ, Redis Pub/Sub, NATS (producer + consumer)
- **Secrets** — HashiCorp Vault, AWS Secrets Manager, Azure Key Vault, GCP Secret Manager
- **Logging** — Vector or Fluent Bit sidecar → Elasticsearch, OpenSearch, Kafka, Loki, or HTTP endpoint
- **Quality Gate** — SonarQube, SonarCloud, Qodana, CodeClimate

## Generated Project Structure

```
your-service/
├── app/
│   ├── main.py                    # App factory + lifespan
│   ├── config.py                  # pydantic-settings
│   ├── dependencies.py            # DI wiring
│   ├── api/
│   │   ├── routes/
│   │   │   ├── health.py          # Health + readiness
│   │   │   └── orders.py          # CRUD routes
│   │   └── models/
│   │       └── order.py           # Pydantic schemas
│   ├── services/
│   │   └── order_service.py       # Business logic
│   ├── repositories/
│   │   └── order_repository.py    # Data access (interface + impl)
│   └── middleware/
│       ├── security_headers.py
│       └── logging_middleware.py
├── tests/
│   └── test_api.py
├── docker-compose.debug.yml       # Dev: debugpy + auto-reload (no venv needed)
├── infra/
│   ├── docker-compose.yml         # Production stack
│   └── vector/ or fluentbit/      # Log agent config (if selected)
├── Dockerfile
├── pyproject.toml
└── .pre-commit-config.yaml
```

## Run Immediately

```bash
cd your-service

# Option A: Docker (recommended — no venv needed)
docker compose -f docker-compose.debug.yml up --build   # dev + auto-reload
docker compose -f infra/docker-compose.yml up --build   # production stack

# Option B: Local
pip install -e ".[dev]"
uvicorn app.main:app --reload
pytest
```

## Log Agent Targets

When you select a log agent (Vector or Fluent Bit), FastForge asks where to send logs:

| Target | Description |
|---|---|
| **Elasticsearch** | Full-text search and analytics — ELK stack |
| **OpenSearch** | AWS-managed alternative to Elasticsearch |
| **Kafka** | Log streaming to a Kafka topic for downstream consumers |
| **Loki** | Grafana's log aggregation system — lightweight, label-based |
| **HTTP** | Generic HTTP endpoint — works with any log ingestion API |

## Extend Your Project

```bash
# Add features
fastforge add model         # CRUD model (route, service, repo, tests)
fastforge add postgres      # PostgreSQL database support
fastforge add redis         # Redis cache support
fastforge add kafka         # Kafka streaming (producer + consumer)
fastforge add observability # OpenTelemetry tracing + Prometheus metrics
fastforge add auth jwt      # JWT authentication (login + protected routes)
fastforge add ai-telemetry  # OTel spans + token cost attribution for AI calls

# Deploy
fastforge deploy local      # Build and run with docker compose
fastforge deploy compose    # Production Docker Compose manifest
fastforge deploy swarm      # Docker Swarm stack
fastforge deploy k8s        # Kubernetes manifests
fastforge deploy helm       # Helm chart
fastforge deploy marathon   # Marathon app definition

# Security
fastforge secure setup      # Gitleaks + Trivy configs
fastforge secure scan       # Trivy image scan
fastforge secure sbom       # CycloneDX SBOM
fastforge secure license    # License compliance check
fastforge secure audit      # Dependency vulnerability audit

# CI/CD
fastforge ci github         # GitHub Actions pipeline
fastforge ci gitlab         # GitLab CI pipeline
fastforge ci bitbucket      # Bitbucket Pipelines
fastforge ci jenkins        # Jenkinsfile

# Operations
fastforge doctor            # Project health check (8 checks)
fastforge audit             # Capability drift + CVE + env contract
fastforge upgrade           # Re-apply generator deltas
fastforge plugins ls        # List discovered generator plugins
```

## Roadmap & Feature Plans

Honest, public roadmap. Status keys: **✅ Shipped** · **🟡 Partial** · **⛔ Planned**

### Core CLI

| Status | Feature | Notes |
|---|---|---|
| ✅ | `fastforge new` (interactive) | standalone / app / lib / workspace shapes |
| ✅ | `fastforge add postgres / kafka / redis / observability / ai-telemetry` | Idempotent, capability-tracked |
| ✅ | `fastforge add model <name>` | CRUD scaffold + repository + service + tests |
| ✅ | `fastforge add auth jwt` | JWT login/me routes, PyJWT + passlib |
| ✅ | `fastforge plugins ls / install` | Entry-point discovery via `fastforge.generators` |
| ✅ | `fastforge doctor` | 8 health checks; friendly when run outside a project |
| ✅ | `fastforge audit` | Capability drift + dependency CVE scan |
| 🟡 | `fastforge upgrade` | Command exists; needs version-delta migration corpus |
| ✅ | `fastforge new --from-file preset.fastforge.json` | Non-interactive scaffolding for reproducible use-case presets and CI smoke runs |
| ⛔ | `fastforge ship` | One-command deploy to Fly.io / Railway / Cloud Run free tier — closes the "60-second wow" loop with a real URL |

### AI Ecosystem

| Status | Feature | Notes |
|---|---|---|
| ✅ | AI gateway (litellm, bifrost) | Hot-swappable via `AI_GATEWAY_PROVIDER` |
| ✅ | Embeddings (openai, gemini, cohere, bedrock, huggingface, local) | 6 providers, one factory |
| ✅ | Vector stores (chromadb, pgvector, qdrant, opensearch, vertex_ai) | 5 providers, one factory |
| ✅ | App kinds (semantic_search, rag, agent) | Picked once at `fastforge new` |
| ✅ | `fastforge add ai-telemetry` | OTel spans + USD cost + tenant ID + W3C trace propagation |
| ⛔ | `fastforge add ai-eval` | Promptfoo + golden-set + CI integration for prompt regression tests |
| ⛔ | `fastforge add ai-cache` | Semantic + exact response caching to cut LLM bills |
| ⛔ | `fastforge add ai-guardrails` | PII redaction, prompt-injection detection, output validation |

### Plugin Ecosystem

| Status | Feature | Notes |
|---|---|---|
| ✅ | Entry-point group `fastforge.generators` | Discoverable, documented protocol |
| ✅ | `BaseGenerator` + `capability_schema()` | Plugin protocol stable across 0.x |
| ✅ | Plugin author docs | Overview, authoring, reference, publishing pages on vibhuvioio.com |
| ⛔ | `billing-stripe` (first external) | Stripe Checkout + webhooks + metered usage hook — pairs with `ai-telemetry` for AI chargeback |
| ⛔ | `auth-clerk` | Drop-in auth with `current_user` deps + webhook handlers |
| ⛔ | `storage-s3` | Presigned URLs + multipart + MinIO compose for local dev |
| ⛔ | `auth-keycloak` | Enterprise OIDC + role guards |
| ⛔ | `queue-celery` | Background jobs + Redis broker + Flower |
| ⛔ | `email-resend` | Templated transactional email |

### Promotion / Adoption

| Status | Feature | Notes |
|---|---|---|
| ✅ | Production-grade core | 202 unit tests + 3 E2E generated-project tests + 6 smoke scenarios; 70% coverage |
| ✅ | Public docs site | vibhuvioio.com/products/fastforge with 16 pages |
| ✅ | Version 0.1.0 published to PyPI | Single source of truth via `importlib.metadata` |
| 🟡 | README hero GIF | Tape script in `promo/`; recording pending |
| ⛔ | Comparison page vs cookiecutter-fastapi / full-stack-fastapi-template | High-leverage SEO |
| ⛔ | Reference app `fastforge-shop` | End-to-end demo with billing + auth + AI |
| ⛔ | First 5 case studies | Social proof for the ecosystem story |

### Out of scope (won't build)

To keep the project focused, these are explicitly **not** planned:

- Hosted gateway / managed runtime — FastForge generates code, you run it.
- Model evaluation harness — use `promptfoo` / `lm-eval-harness` alongside.
- Fine-tuning pipelines — vendor-specific, doesn't belong in a scaffolding tool.
- Web playground — high cost, medium impact; CLI install is fast enough.

### Suggest a feature

Open an issue on [GitHub](https://github.com/VibhuviOiO/fastforge-cli/issues) tagged `roadmap` or send a PR adding a row to this table. Plugins that don't fit core are welcome under your own namespace — see [Authoring a Plugin](https://vibhuvioio.com/products/fastforge/authoring-a-plugin).

## Requirements

- Python 3.10+
- pip

## License

MIT
