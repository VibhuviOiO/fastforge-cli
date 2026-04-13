"""Add observability (OpenTelemetry tracing + Prometheus metrics) to a FastForge project.

Creates: app/telemetry/__init__.py, tracing.py, metrics.py
Modifies: app/main.py, app/config.py, pyproject.toml, .fastforge.json
"""

import os
import re
import subprocess

from fastforge.project_config import load_config, save_config

TELEMETRY_INIT = '"""Telemetry package — tracing and metrics."""\n'

TRACING_PY = '''\
"""OpenTelemetry distributed tracing setup."""

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.config import settings


def setup_tracing(app) -> None:
    """Initialize OpenTelemetry tracing if enabled.

    Configures:
    - OTLP exporter (sends traces to Jaeger/Tempo/any OTLP-compatible backend)
    - FastAPI auto-instrumentation (traces all HTTP requests)
    - Logging instrumentation (injects trace_id/span_id into log records)
    """
    if not settings.otel_enabled:
        return

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": settings.app_version,
            "deployment.environment": settings.app_env,
        }
    )

    provider = TracerProvider(resource=resource)
    otlp_exporter = OTLPSpanExporter(
        endpoint=settings.otel_exporter_otlp_endpoint, insecure=True
    )
    provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)
    LoggingInstrumentor().instrument(set_logging_format=True)
'''

METRICS_PY = '''\
"""Prometheus metrics collection."""

from prometheus_client import Counter, Histogram, generate_latest
from starlette.requests import Request
from starlette.responses import Response

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)


def record_request_metrics(
    method: str, endpoint: str, status_code: int, duration: float
) -> None:
    """Record Prometheus metrics for a request."""
    REQUEST_COUNT.labels(
        method=method, endpoint=endpoint, status_code=str(status_code)
    ).inc()
    REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(duration)


async def metrics_endpoint(_request: Request) -> Response:
    """Prometheus metrics scrape endpoint."""
    return Response(
        content=generate_latest(), media_type="text/plain; charset=utf-8"
    )
'''

OTEL_DEPS = [
    '"opentelemetry-api>=1.20.0"',
    '"opentelemetry-sdk>=1.20.0"',
    '"opentelemetry-exporter-otlp-proto-grpc>=1.20.0"',
    '"opentelemetry-instrumentation-fastapi>=0.41b0"',
    '"opentelemetry-instrumentation-logging>=0.41b0"',
    '"prometheus-client>=0.20.0"',
]

# ═══════════════════════════════════════════════════════════════════════════════
# Infrastructure compose templates per observability stack
# ═══════════════════════════════════════════════════════════════════════════════

COMPOSE_JAEGER = """\
# Jaeger — distributed tracing
# Usage: docker compose -f infra/docker-compose.yml -f infra/docker-compose.jaeger.yml up -d
# UI: http://localhost:16686

services:
  jaeger:
    image: jaegertracing/all-in-one:1.58
    container_name: {slug}-jaeger
    environment:
      COLLECTOR_OTLP_ENABLED: "true"
    ports:
      - "16686:16686"   # Jaeger UI
      - "4317:4317"     # OTLP gRPC
      - "4318:4318"     # OTLP HTTP
    healthcheck:
      test: ["CMD-SHELL", "wget --spider -q http://localhost:16686/ || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5
"""

COMPOSE_ELK = """\
# ELK Stack — Elasticsearch + Kibana + APM Server
# Usage: docker compose -f infra/docker-compose.yml -f infra/docker-compose.elk.yml up -d
# Kibana: http://localhost:5601  |  APM: http://localhost:8200

services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.15.0
    container_name: {slug}-elasticsearch
    environment:
      - discovery.type=single-node
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    ports:
      - "9200:9200"
    volumes:
      - esdata:/var/lib/elasticsearch/data
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:9200/_cluster/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 5

  kibana:
    image: docker.elastic.co/kibana/kibana:8.15.0
    container_name: {slug}-kibana
    environment:
      ELASTICSEARCH_HOSTS: http://elasticsearch:9200
    ports:
      - "5601:5601"
    depends_on:
      elasticsearch:
        condition: service_healthy

  apm-server:
    image: docker.elastic.co/apm/apm-server:8.15.0
    container_name: {slug}-apm
    command: >
      apm-server -e
        -E apm-server.host=0.0.0.0:8200
        -E output.elasticsearch.hosts=["http://elasticsearch:9200"]
        -E apm-server.rum.enabled=true
    ports:
      - "8200:8200"
    depends_on:
      elasticsearch:
        condition: service_healthy

volumes:
  esdata:
    name: {slug}-esdata
"""

COMPOSE_GRAFANA = """\
# Grafana + Prometheus + Loki + Tempo
# Usage: docker compose -f infra/docker-compose.yml -f infra/docker-compose.grafana.yml up -d
# Grafana: http://localhost:3000 (admin/admin)  |  Prometheus: http://localhost:9090

services:
  prometheus:
    image: prom/prometheus:v2.53.0
    container_name: {slug}-prometheus
    volumes:
      - ./grafana/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    ports:
      - "9090:9090"
    healthcheck:
      test: ["CMD-SHELL", "wget --spider -q http://localhost:9090/-/healthy || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 5

  loki:
    image: grafana/loki:3.1.0
    container_name: {slug}-loki
    ports:
      - "3100:3100"
    command: -config.file=/etc/loki/local-config.yaml

  tempo:
    image: grafana/tempo:2.5.0
    container_name: {slug}-tempo
    command: ["-config.file=/etc/tempo/tempo.yml"]
    volumes:
      - ./grafana/tempo.yml:/etc/tempo/tempo.yml:ro
    ports:
      - "4317:4317"     # OTLP gRPC
      - "4318:4318"     # OTLP HTTP
      - "3200:3200"     # Tempo API

  grafana:
    image: grafana/grafana:11.1.0
    container_name: {slug}-grafana
    environment:
      GF_SECURITY_ADMIN_USER: admin
      GF_SECURITY_ADMIN_PASSWORD: admin
      GF_AUTH_ANONYMOUS_ENABLED: "true"
    volumes:
      - ./grafana/datasources.yml:/etc/grafana/provisioning/datasources/datasources.yml:ro
    ports:
      - "3000:3000"
    depends_on:
      - prometheus
      - loki
      - tempo
"""

# Grafana config files
PROMETHEUS_YML = """\
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: "{slug}"
    metrics_path: /metrics
    static_configs:
      - targets: ["host.docker.internal:{port}"]
        labels:
          service: "{slug}"
"""

TEMPO_YML = """\
server:
  http_listen_port: 3200

distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: 0.0.0.0:4317
        http:
          endpoint: 0.0.0.0:4318

storage:
  trace:
    backend: local
    local:
      path: /tmp/tempo/blocks
"""

GRAFANA_DATASOURCES = """\
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true

  - name: Loki
    type: loki
    access: proxy
    url: http://loki:3100

  - name: Tempo
    type: tempo
    access: proxy
    url: http://tempo:3200
    jsonData:
      tracesToLogsV2:
        datasourceUid: loki
      tracesToMetrics:
        datasourceUid: prometheus
"""


def add_observability(project_dir: str, stack: str = "jaeger") -> dict:
    """Add observability to the project. Returns summary of changes."""
    config = load_config(project_dir)

    # Idempotency
    if config.get("observability") == "enabled":
        return {"status": "already_configured", "created": [], "modified": []}

    created: list[str] = []
    modified: list[str] = []

    # 1. Create app/telemetry/ package
    telemetry_dir = os.path.join(project_dir, "app", "telemetry")
    os.makedirs(telemetry_dir, exist_ok=True)

    for filename, content in [
        ("__init__.py", TELEMETRY_INIT),
        ("tracing.py", TRACING_PY),
        ("metrics.py", METRICS_PY),
    ]:
        path = os.path.join(telemetry_dir, filename)
        if not os.path.exists(path):
            with open(path, "w") as f:
                f.write(content)
            created.append(f"app/telemetry/{filename}")

    # 2. Add otel settings to config.py
    config_path = os.path.join(project_dir, "app", "config.py")
    if os.path.isfile(config_path):
        with open(config_path) as f:
            content = f.read()

        if "otel_enabled" not in content:
            otel_block = (
                "\n    # OpenTelemetry\n"
                "    otel_enabled: bool = False\n"
                '    otel_exporter_otlp_endpoint: str = "http://localhost:4317"\n'
                '    otel_service_name: str = "{}"\n\n'
            ).format(config.get("project_slug", "app"))

            for anchor in ["    model_config", "    @property"]:
                if anchor in content:
                    content = content.replace(anchor, otel_block + anchor, 1)
                    break

            with open(config_path, "w") as f:
                f.write(content)
            modified.append("app/config.py")

    # 3. Add imports + setup to main.py
    main_path = os.path.join(project_dir, "app", "main.py")
    if os.path.isfile(main_path):
        with open(main_path) as f:
            main_content = f.read()

        changed = False

        # Add imports after the last "from app." import line
        imports_to_add = []
        if "from app.telemetry.tracing import setup_tracing" not in main_content:
            imports_to_add.append("from app.telemetry.tracing import setup_tracing")
        if "from app.telemetry.metrics import metrics_endpoint" not in main_content:
            imports_to_add.append("from app.telemetry.metrics import metrics_endpoint")
        if "from starlette.routing import Route" not in main_content:
            imports_to_add.append("from starlette.routing import Route")

        if imports_to_add:
            lines = main_content.split("\n")
            last_app_import = -1
            for i, line in enumerate(lines):
                if line.startswith("from app."):
                    last_app_import = i
            if last_app_import >= 0:
                for offset, imp in enumerate(imports_to_add):
                    lines.insert(last_app_import + 1 + offset, imp)
                main_content = "\n".join(lines)
                changed = True

        # Add setup_tracing(app) and metrics route after last include_router
        if "setup_tracing(app)" not in main_content:
            lines = main_content.split("\n")
            last_include = -1
            for i, line in enumerate(lines):
                if "include_router" in line:
                    last_include = i

            if last_include >= 0:
                indent = "    " if lines[last_include].startswith("    ") else ""
                insertions = [
                    "",
                    f"{indent}# Prometheus metrics endpoint",
                    f'{indent}app.routes.append(Route("/metrics", metrics_endpoint))',
                    f"{indent}# OpenTelemetry tracing",
                    f"{indent}setup_tracing(app)",
                ]
                for idx, line in enumerate(insertions):
                    lines.insert(last_include + 1 + idx, line)
                main_content = "\n".join(lines)
                changed = True

        if changed:
            with open(main_path, "w") as f:
                f.write(main_content)
            modified.append("app/main.py")

    # 4. Add .env.staging vars
    env_path = os.path.join(project_dir, ".env.staging")
    if os.path.isfile(env_path):
        with open(env_path) as f:
            env_content = f.read()

        if "OTEL_ENABLED" not in env_content:
            with open(env_path, "a") as f:
                f.write(
                    "\n# OpenTelemetry\n"
                    "OTEL_ENABLED=false\n"
                    "OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317\n"
                    f"OTEL_SERVICE_NAME={config.get('project_slug', 'app')}\n"
                )
            modified.append(".env.staging")

    # 5. Add dependencies to pyproject.toml
    pyproject_path = os.path.join(project_dir, "pyproject.toml")
    if os.path.isfile(pyproject_path):
        with open(pyproject_path) as f:
            pyproject_content = f.read()

        new_deps = [d for d in OTEL_DEPS if d.split('"')[1].split('>')[0].split('[')[0] not in pyproject_content.lower()]

        if new_deps:
            match = re.search(r"(dependencies\s*=\s*\[)(.*?)(^\])", pyproject_content, re.DOTALL | re.MULTILINE)
            if match:
                existing = match.group(2).rstrip()
                if existing and not existing.rstrip().endswith(","):
                    existing = existing.rstrip() + ","
                new_section = existing + "\n" + "\n".join(f"    {d}," for d in new_deps) + "\n"
                pyproject_content = (
                    pyproject_content[:match.start(2)]
                    + new_section
                    + pyproject_content[match.start(3):]
                )
                with open(pyproject_path, "w") as f:
                    f.write(pyproject_content)
                modified.append("pyproject.toml")

    # 6. Generate infra compose + config for the selected stack
    slug = config.get("project_slug", "app")
    port = config.get("port", 8000)
    infra_dir = os.path.join(project_dir, "infra")
    os.makedirs(infra_dir, exist_ok=True)

    if stack == "jaeger":
        compose_path = os.path.join(infra_dir, "docker-compose.jaeger.yml")
        if not os.path.exists(compose_path):
            with open(compose_path, "w") as f:
                f.write(COMPOSE_JAEGER.format(slug=slug))
            created.append("infra/docker-compose.jaeger.yml")

    elif stack == "elk":
        compose_path = os.path.join(infra_dir, "docker-compose.elk.yml")
        if not os.path.exists(compose_path):
            with open(compose_path, "w") as f:
                f.write(COMPOSE_ELK.format(slug=slug))
            created.append("infra/docker-compose.elk.yml")

    elif stack == "grafana":
        compose_path = os.path.join(infra_dir, "docker-compose.grafana.yml")
        if not os.path.exists(compose_path):
            with open(compose_path, "w") as f:
                f.write(COMPOSE_GRAFANA.format(slug=slug))
            created.append("infra/docker-compose.grafana.yml")

        # Grafana config files
        grafana_dir = os.path.join(infra_dir, "grafana")
        os.makedirs(grafana_dir, exist_ok=True)

        for filename, content in [
            ("prometheus.yml", PROMETHEUS_YML.format(slug=slug, port=port)),
            ("tempo.yml", TEMPO_YML),
            ("datasources.yml", GRAFANA_DATASOURCES),
        ]:
            path = os.path.join(grafana_dir, filename)
            if not os.path.exists(path):
                with open(path, "w") as f:
                    f.write(content)
                created.append(f"infra/grafana/{filename}")

    # 6. Run ruff
    subprocess.run(["ruff", "check", "--fix", "--silent", "."], cwd=project_dir, capture_output=True)
    subprocess.run(["ruff", "format", "--silent", "."], cwd=project_dir, capture_output=True)

    # 8. Update .fastforge.json
    config["observability"] = "enabled"
    config["observability_stack"] = stack
    save_config(config, project_dir)
    modified.append(".fastforge.json")

    return {"status": "added", "created": created, "modified": modified}
