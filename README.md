# 🔨 FastForge

**Production-grade FastAPI project generator for Python backends.**

[![PyPI](https://img.shields.io/pypi/v/fastforge)](https://pypi.org/project/fastforge/)
[![Python](https://img.shields.io/pypi/pyversions/fastforge)](https://pypi.org/project/fastforge/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

FastForge generates a **ready-to-run, production-grade FastAPI project** with SOLID architecture, structured logging, Docker containerization, and async CRUD — all in under 30 seconds.

## Quick Start

```bash
pip install fastforge
fastforge
```

That's it. Answer a few prompts and you get a running application.

## What You Get (Basic Mode)

| Feature | Implementation |
|---|---|
| **SOLID Architecture** | Repository pattern + Service layer + Dependency Injection |
| **Async CRUD API** | FastAPI with full Create/Read/Update/Delete |
| **Structured Logging** | structlog with JSON output, request IDs, duration tracking |
| **Docker** | Multi-stage Dockerfile, docker-compose, health checks |
| **Security** | Security headers middleware, CORS, non-root container |
| **Testing** | pytest + pytest-asyncio, 80%+ coverage out of the box |
| **Code Quality** | ruff linting, pre-commit hooks |

## CLI Flow

```
$ fastforge

  ___         _   ___
 | __| _ _ __| |_| __|__ _ _ __ _ ___
 | _/ _` (_-<  _| _/ _ \ '_/ _` / -_)
 |_|\__,_/__/\__|_|\___/_| \__, \___|
                            |___/
 Production-grade FastAPI Generator

┌─ Choose your path ───────────────────────────────────┐
│ Basic mode  → SOLID app, JSON logging, Docker, async │
│ Advanced    → + Database, Cache, Streaming, Secrets  │
└──────────────────────────────────────────────────────┘

? Project name: order-service
? Model name: order
? Log output: Stdout
? Include debug compose? No
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
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── .pre-commit-config.yaml
```

## Run Immediately

```bash
cd your-service

# Option A: Docker
docker compose up --build

# Option B: Local
pip install -e ".[dev]"
uvicorn app.main:app --reload
pytest
```

## Extend Your Project

```bash
fastforge-infra           # Infrastructure (Kafka, Elasticsearch, Vault, DB)
fastforge-cicd            # CI/CD pipeline
fastforge-secops          # Security tools
fastforge-helm            # Helm chart
fastforge-k8s             # Kubernetes manifests
fastforge-observability   # Tracing + Metrics
```

## Requirements

- Python 3.10+
- pip

## License

MIT
