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
$ fastforge

? Project name: order-service
? Model name: order
? Log output: Stdout + File
? Log agent: Vector
? Log target: Elasticsearch
? Include debug compose? Yes
? Generate project? Yes

✔ Project created: ./order-service

$ cd order-service
$ docker compose -f docker-compose.debug.yml up --build
# API running at http://localhost:8000/docs — no venv needed
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
fastforge
```

That's it. Answer a few prompts and you get a running application.

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
$ fastforge

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
├── docker/
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
docker compose -f docker/docker-compose.yml up --build   # production stack

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
fastforge add observability # OpenTelemetry tracing + Prometheus metrics

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
fastforge infra             # Standalone infrastructure stack
fastforge doctor            # Project health check (8 checks)
```

## Requirements

- Python 3.10+
- pip

## License

MIT
