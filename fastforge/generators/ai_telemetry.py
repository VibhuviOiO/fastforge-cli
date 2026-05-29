"""fastforge add ai-telemetry — OTel spans + token/cost attribution around AI calls.

Generates:
- app/ai/telemetry/__init__.py
- app/ai/telemetry/spans.py        : tracer, ai_span() context manager, AITracingProxy
- app/ai/telemetry/pricing.py      : per-provider/model pricing table + cost_usd()
- app/ai/telemetry/propagation.py  : W3C traceparent injection for outbound HTTPX
- app/ai/telemetry/tenant.py       : ContextVar + middleware for per-tenant attribution
- infra/docker-compose.otel.yml    : OTel collector + Tempo + Prometheus
- infra/otel/otel-collector.yaml   : collector config (OTLP in, fan-out out)

Mutates:
- app/ai/gateway/registry.py        : wrap created client in AITracingProxy
- app/ai/embeddings/registry.py     : wrap created provider in AITracingProxy
- app/ai/vector_store/registry.py   : wrap created provider in AITracingProxy
- app/ai/config.py                  : add ai_telemetry_enabled / tenant header settings
- app/main.py                       : register TenantContextMiddleware
- pyproject.toml                    : pin OTel + opentelemetry-semantic-conventions-ai
- .fastforge.json                   : record capability
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from fastforge.generator_protocol import BaseGenerator

# ─────────────────────────────────────────────────────────────────────────────
# Emitted source files
# ─────────────────────────────────────────────────────────────────────────────

TELEMETRY_INIT = '"""AI telemetry — OTel spans + cost attribution around AI calls."""\n'


SPANS_PY = '''"""OTel spans + tracing proxy for AI provider calls.

Instruments gateway / embedding / vector_store calls with:
- OpenTelemetry GenAI semantic-convention attributes
- Token usage (when the underlying provider returns it)
- Computed USD cost via app.ai.telemetry.pricing
- Tenant id from app.ai.telemetry.tenant.current_tenant
"""

from __future__ import annotations

import functools
import inspect
from contextlib import contextmanager
from typing import Any, Iterable

import structlog
from opentelemetry import trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from app.ai.telemetry.pricing import cost_usd
from app.ai.telemetry.tenant import current_tenant

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer("app.ai")


# Per-category method name → (operation label, semconv attribute prefix)
_INSTRUMENTED: dict[str, dict[str, tuple[str, str]]] = {
    "gateway": {
        "generate": ("chat", "gen_ai"),
        "completion": ("chat", "gen_ai"),
        "chat": ("chat", "gen_ai"),
        "stream": ("chat.stream", "gen_ai"),
    },
    "embedding": {
        "embed": ("embedding", "gen_ai"),
        "embed_batch": ("embedding.batch", "gen_ai"),
    },
    "vector_store": {
        "query": ("vector.query", "db"),
        "search": ("vector.query", "db"),
        "upsert": ("vector.upsert", "db"),
        "add_documents": ("vector.upsert", "db"),
        "delete": ("vector.delete", "db"),
    },
}


@contextmanager
def ai_span(
    name: str,
    *,
    kind: str,
    provider: str,
    model: str | None = None,
    extra: dict[str, Any] | None = None,
):
    """Open an OTel span carrying GenAI semantic-convention attributes.

    Use directly when you write custom orchestration code:

        with ai_span("rewrite_query", kind="gateway", provider="openai", model="gpt-4o") as span:
            ...
            span.set_attribute("gen_ai.usage.input_tokens", n_in)
    """
    attrs: dict[str, Any] = {
        "ai.category": kind,
        "ai.provider": provider,
    }
    if model:
        attrs["gen_ai.request.model"] = model
        attrs["gen_ai.system"] = provider
    tenant = current_tenant()
    if tenant:
        attrs["ai.tenant_id"] = tenant
    if extra:
        attrs.update(extra)

    with tracer.start_as_current_span(
        f"ai.{kind}.{name}", kind=SpanKind.CLIENT, attributes=attrs
    ) as span:
        try:
            yield span
        except Exception as exc:
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            span.record_exception(exc)
            raise


class AITracingProxy:
    """Transparent proxy that emits an OTel span on instrumented method calls.

    Forwarding rule:
    - Any attribute that is NOT one of the instrumented method names passes
      through unchanged.
    - Instrumented async methods are wrapped to open a span, await the result,
      extract token usage + cost, and close the span.
    - Instrumented sync methods get the same treatment without await.
    """

    __slots__ = ("_target", "_kind", "_provider", "_model_attr")

    def __init__(self, target: Any, kind: str, provider: str, model_attr: str | None = None):
        object.__setattr__(self, "_target", target)
        object.__setattr__(self, "_kind", kind)
        object.__setattr__(self, "_provider", provider)
        object.__setattr__(self, "_model_attr", model_attr)

    def __getattr__(self, name: str) -> Any:  # pragma: no cover - trivial proxy
        attr = getattr(self._target, name)
        methods = _INSTRUMENTED.get(self._kind, {})
        if name in methods and callable(attr):
            op_label, _semconv = methods[name]
            return self._wrap(attr, op_label)
        return attr

    def __setattr__(self, name: str, value: Any) -> None:
        setattr(self._target, name, value)

    # ── internal ────────────────────────────────────────────────────────────

    def _model_for_call(self, args: tuple, kwargs: dict) -> str | None:
        # Highest priority: explicit "model" kwarg
        if "model" in kwargs and isinstance(kwargs["model"], str):
            return kwargs["model"]
        # Fallback: target attribute (e.g. self._target.model)
        if self._model_attr:
            return getattr(self._target, self._model_attr, None)
        # Common attribute names
        for guess in ("model", "model_name", "embedding_model", "chat_model"):
            value = getattr(self._target, guess, None)
            if isinstance(value, str):
                return value
        return None

    def _record_usage(self, span, result: Any, model: str | None) -> None:
        usage = _extract_usage(result)
        if not usage:
            return
        in_tok, out_tok, total_tok = usage
        if in_tok is not None:
            span.set_attribute("gen_ai.usage.input_tokens", in_tok)
        if out_tok is not None:
            span.set_attribute("gen_ai.usage.output_tokens", out_tok)
        if total_tok is not None:
            span.set_attribute("gen_ai.usage.total_tokens", total_tok)
        if model:
            usd = cost_usd(self._provider, model, in_tok or 0, out_tok or 0)
            if usd is not None:
                span.set_attribute("ai.cost_usd", round(usd, 8))

    def _wrap(self, fn, op_label: str):
        is_coro = inspect.iscoroutinefunction(fn)

        if is_coro:
            @functools.wraps(fn)
            async def aw(*args, **kwargs):
                model = self._model_for_call(args, kwargs)
                with ai_span(op_label, kind=self._kind, provider=self._provider, model=model) as span:
                    result = await fn(*args, **kwargs)
                    self._record_usage(span, result, model)
                    return result
            return aw

        @functools.wraps(fn)
        def sw(*args, **kwargs):
            model = self._model_for_call(args, kwargs)
            with ai_span(op_label, kind=self._kind, provider=self._provider, model=model) as span:
                result = fn(*args, **kwargs)
                self._record_usage(span, result, model)
                return result
        return sw


def _extract_usage(result: Any) -> tuple[int | None, int | None, int | None] | None:
    """Try every reasonable shape providers return; give up silently."""
    if result is None:
        return None
    # Object with .usage attr (OpenAI, Anthropic, etc.)
    usage = getattr(result, "usage", None)
    if usage is not None:
        return _pull(usage)
    # Dict with "usage" key
    if isinstance(result, dict) and "usage" in result:
        return _pull(result["usage"])
    # Some SDKs put it at top level
    return _pull(result) if _has_token_keys(result) else None


def _pull(obj: Any) -> tuple[int | None, int | None, int | None]:
    def g(*names: str) -> int | None:
        for n in names:
            if isinstance(obj, dict) and n in obj and isinstance(obj[n], int):
                return obj[n]
            v = getattr(obj, n, None)
            if isinstance(v, int):
                return v
        return None

    return (
        g("input_tokens", "prompt_tokens"),
        g("output_tokens", "completion_tokens"),
        g("total_tokens"),
    )


def _has_token_keys(obj: Any) -> bool:
    keys: Iterable[str]
    if isinstance(obj, dict):
        keys = obj.keys()
    else:
        keys = dir(obj)
    return any(k in keys for k in ("input_tokens", "prompt_tokens", "total_tokens"))
'''


PRICING_PY = '''"""USD cost calculator for common AI providers.

Prices are USD per 1 million tokens (input, output) as of generator template time.
Override per-model via PRICING_OVERRIDES env (JSON map) or by editing this file.

Sources: provider public pricing pages (subject to change). Treat as estimates
for cost attribution dashboards; not for billing.
"""

from __future__ import annotations

import json
import os
from typing import Any

# (input USD per 1M tokens, output USD per 1M tokens). For embeddings, output=0.
_PRICING: dict[str, dict[str, tuple[float, float]]] = {
    "openai": {
        "gpt-4o":              (2.50, 10.00),
        "gpt-4o-mini":         (0.15,  0.60),
        "gpt-4-turbo":         (10.00, 30.00),
        "text-embedding-3-small": (0.02, 0.0),
        "text-embedding-3-large": (0.13, 0.0),
        "text-embedding-ada-002": (0.10, 0.0),
    },
    "gemini": {
        "gemini-2.0-flash":      (0.10, 0.40),
        "gemini-2.0-flash-lite": (0.075, 0.30),
        "gemini-1.5-pro":        (1.25, 5.00),
        "gemini-1.5-flash":      (0.075, 0.30),
        "text-embedding-004":    (0.025, 0.0),
    },
    "bedrock": {
        "anthropic.claude-3-5-sonnet-20240620-v1:0": (3.00, 15.00),
        "anthropic.claude-3-haiku-20240307-v1:0":    (0.25,  1.25),
        "amazon.titan-embed-text-v2:0":              (0.02, 0.0),
    },
    "cohere": {
        "command-r":      (0.50, 1.50),
        "command-r-plus": (2.50, 10.00),
        "embed-english-v3.0":      (0.10, 0.0),
        "embed-multilingual-v3.0": (0.10, 0.0),
    },
    # Self-hosted / local: cost is operational, not per-token.
    "huggingface": {},
    "local":       {},
}


def _load_overrides() -> dict[str, dict[str, tuple[float, float]]]:
    raw = os.environ.get("AI_PRICING_OVERRIDES")
    if not raw:
        return {}
    try:
        data: Any = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    out: dict[str, dict[str, tuple[float, float]]] = {}
    for provider, models in (data or {}).items():
        out[provider] = {}
        for model, pair in (models or {}).items():
            if isinstance(pair, list) and len(pair) == 2:
                out[provider][model] = (float(pair[0]), float(pair[1]))
    return out


_OVERRIDES = _load_overrides()


def cost_usd(provider: str, model: str, input_tokens: int, output_tokens: int) -> float | None:
    """Compute USD cost for a call. Returns None if pricing for (provider, model) is unknown."""
    table = {**_PRICING.get(provider, {}), **_OVERRIDES.get(provider, {})}
    rates = table.get(model)
    if not rates:
        # Try a normalised model name (strip version suffixes)
        for known, known_rates in table.items():
            if model.startswith(known):
                rates = known_rates
                break
    if not rates:
        return None
    in_rate, out_rate = rates
    return (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000.0
'''


TENANT_PY = '''"""Per-tenant attribution — ContextVar + FastAPI middleware.

The current tenant is read from a request header (default ``X-Tenant-Id``)
and stored in a ContextVar so AI spans can attach it automatically.
"""

from __future__ import annotations

from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_current_tenant: ContextVar[str | None] = ContextVar("current_tenant", default=None)


def current_tenant() -> str | None:
    """Return the tenant id captured for the active request, if any."""
    return _current_tenant.get()


def set_tenant(value: str | None) -> None:
    """Set the tenant id manually (useful in background jobs / tests)."""
    _current_tenant.set(value)


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Read a tenant identifier from a header and bind it to the request context."""

    def __init__(self, app, header_name: str = "X-Tenant-Id") -> None:
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next) -> Response:
        tenant = request.headers.get(self.header_name)
        token = _current_tenant.set(tenant)
        try:
            return await call_next(request)
        finally:
            _current_tenant.reset(token)
'''


PROPAGATION_PY = '''"""W3C trace-context propagation for outbound HTTPX clients.

Use ``traced_httpx_client()`` instead of ``httpx.AsyncClient(...)`` when calling
the AI gateway, so the active span context propagates as a ``traceparent``
header and the gateway's spans link back to the originating request.
"""

from __future__ import annotations

from typing import Any

import httpx
from opentelemetry.propagate import inject


async def _inject_traceparent(request: httpx.Request) -> None:
    headers: dict[str, str] = {}
    inject(headers)
    for k, v in headers.items():
        request.headers.setdefault(k, v)


def traced_httpx_client(**kwargs: Any) -> httpx.AsyncClient:
    """Return an httpx.AsyncClient that injects traceparent on every request."""
    event_hooks = kwargs.pop("event_hooks", {})
    request_hooks = list(event_hooks.get("request", []))
    request_hooks.append(_inject_traceparent)
    event_hooks["request"] = request_hooks
    return httpx.AsyncClient(event_hooks=event_hooks, **kwargs)
'''


COLLECTOR_COMPOSE = """# OTel collector + Tempo + Prometheus — sidecar observability stack.
# Usage: docker compose -f infra/docker-compose.yml -f infra/docker-compose.otel.yml up -d
#
# Pipelines:
#   apps → otel-collector (OTLP gRPC :4317) → tempo (traces) + prometheus (metrics)
#
# Point your app at it:
#   OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
#   OTEL_SERVICE_NAME={slug}

services:
  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.110.0
    container_name: {slug}-otel-collector
    command: ["--config=/etc/otel/otel-collector.yaml"]
    volumes:
      - ./otel/otel-collector.yaml:/etc/otel/otel-collector.yaml:ro
    ports:
      - "4317:4317"   # OTLP gRPC
      - "4318:4318"   # OTLP HTTP
      - "8889:8889"   # Prometheus exporter scrape endpoint
    depends_on:
      - tempo
    networks: [default]

  tempo:
    image: grafana/tempo:2.6.0
    container_name: {slug}-tempo
    command: ["-config.file=/etc/tempo/tempo.yaml"]
    volumes:
      - ./otel/tempo.yaml:/etc/tempo/tempo.yaml:ro
    ports:
      - "3200:3200"   # Tempo HTTP / query
    networks: [default]

  prometheus:
    image: prom/prometheus:v3.0.1
    container_name: {slug}-prometheus
    command:
      - --config.file=/etc/prometheus/prometheus.yml
    volumes:
      - ./otel/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    ports:
      - "9090:9090"
    networks: [default]
"""


COLLECTOR_YAML = """receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 1s
    send_batch_size: 1024
  memory_limiter:
    check_interval: 1s
    limit_mib: 512

exporters:
  otlp/tempo:
    endpoint: tempo:4317
    tls:
      insecure: true
  prometheus:
    endpoint: 0.0.0.0:8889
  debug:
    verbosity: basic

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [otlp/tempo, debug]
    metrics:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [prometheus, debug]
"""


TEMPO_YAML = """server:
  http_listen_port: 3200

distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: 0.0.0.0:4317

ingester:
  trace_idle_period: 10s
  max_block_bytes: 1_048_576
  max_block_duration: 5m

compactor:
  compaction:
    block_retention: 24h

storage:
  trace:
    backend: local
    local:
      path: /var/tempo/blocks
    wal:
      path: /var/tempo/wal
"""


PROMETHEUS_YAML = """global:
  scrape_interval: 15s

scrape_configs:
  - job_name: otel-collector
    static_configs:
      - targets: ["otel-collector:8889"]
"""


# OTel + GenAI semconv dependencies pinned to known-good versions.
DEPS = [
    '"opentelemetry-api>=1.27.0"',
    '"opentelemetry-sdk>=1.27.0"',
    '"opentelemetry-exporter-otlp-proto-grpc>=1.27.0"',
    '"opentelemetry-instrumentation-fastapi>=0.48b0"',
    '"opentelemetry-instrumentation-httpx>=0.48b0"',
]


# ─────────────────────────────────────────────────────────────────────────────
# Generator
# ─────────────────────────────────────────────────────────────────────────────


class AITelemetryGenerator(BaseGenerator):
    name = "ai-telemetry"
    version = "1.0.0"
    description = "OTel spans, token usage, and USD cost attribution around AI calls"
    capability_key = "ai_telemetry"
    delegatable = False

    def emit_inline(self, project_dir: Path, args: dict[str, Any]) -> dict[str, Any]:
        ai_dir = project_dir / "app" / "ai"
        if not ai_dir.exists():
            raise FileNotFoundError(
                "app/ai/ not found — run `fastforge new` with AI capability first."
            )

        created: list[str] = []
        modified: list[str] = []

        # 1. Telemetry package files
        tel_dir = ai_dir / "telemetry"
        tel_dir.mkdir(parents=True, exist_ok=True)
        for fname, content in (
            ("__init__.py", TELEMETRY_INIT),
            ("spans.py", SPANS_PY),
            ("pricing.py", PRICING_PY),
            ("tenant.py", TENANT_PY),
            ("propagation.py", PROPAGATION_PY),
        ):
            target = tel_dir / fname
            if not target.exists():
                target.write_text(content)
                created.append(str(target.relative_to(project_dir)))

        # 2. Wrap registry factories
        for kind, rel in (
            ("gateway", "gateway/registry.py"),
            ("embedding", "embeddings/registry.py"),
            ("vector_store", "vector_store/registry.py"),
        ):
            reg_path = ai_dir / rel
            if reg_path.exists() and self._wrap_registry(reg_path, kind):
                modified.append(str(reg_path.relative_to(project_dir)))

        # 3. AI config additions
        config_path = ai_dir / "config.py"
        if config_path.exists() and self._patch_ai_config(config_path):
            modified.append(str(config_path.relative_to(project_dir)))

        # 4. Tenant middleware registration in app/main.py
        main_path = project_dir / "app" / "main.py"
        if main_path.exists() and self._wire_main(main_path):
            modified.append(str(main_path.relative_to(project_dir)))

        # 5. OTel collector compose + configs
        slug = self._project_slug(project_dir)
        infra_dir = project_dir / "infra"
        otel_dir = infra_dir / "otel"
        otel_dir.mkdir(parents=True, exist_ok=True)
        for rel, content in (
            ("docker-compose.otel.yml", COLLECTOR_COMPOSE.format(slug=slug)),
            ("otel/otel-collector.yaml", COLLECTOR_YAML),
            ("otel/tempo.yaml", TEMPO_YAML),
            ("otel/prometheus.yml", PROMETHEUS_YAML),
        ):
            target = infra_dir / rel
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
                created.append(str(target.relative_to(project_dir)))

        # 6. Pin OTel deps in pyproject.toml
        pyproject = project_dir / "pyproject.toml"
        if pyproject.exists() and self._add_deps(pyproject):
            modified.append("pyproject.toml")

        # 7. Record capability in .fastforge.json
        cfg_path = project_dir / ".fastforge.json"
        if cfg_path.exists() and self._record_capability(cfg_path):
            modified.append(".fastforge.json")

        return {
            "status": "ok" if (created or modified) else "already_configured",
            "created": created,
            "modified": modified,
        }

    def validate(self, project_dir: Path) -> list[str]:
        ai_dir = project_dir / "app" / "ai"
        if not ai_dir.exists():
            return ["app/ai/ missing — ai-telemetry requires the ai-app capability"]
        warnings: list[str] = []
        tel = ai_dir / "telemetry"
        for f in ("spans.py", "pricing.py", "tenant.py", "propagation.py"):
            if not (tel / f).exists():
                warnings.append(
                    f"app/ai/telemetry/{f} missing — re-run `fastforge add ai-telemetry`"
                )
        return warnings

    def capability_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ai_telemetry": {
                    "type": "object",
                    "properties": {
                        "version": {"type": "string"},
                        "tenant_header": {"type": "string", "default": "X-Tenant-Id"},
                    },
                    "required": ["version"],
                }
            },
        }

    # ── helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _project_slug(project_dir: Path) -> str:
        cfg = project_dir / ".fastforge.json"
        if cfg.exists():
            try:
                return json.loads(cfg.read_text()).get("project_slug", project_dir.name)
            except json.JSONDecodeError:
                pass
        return project_dir.name

    @staticmethod
    def _wrap_registry(path: Path, kind: str) -> bool:
        """Patch create_* factory to wrap returned instance in AITracingProxy."""
        text = path.read_text()
        if "AITracingProxy" in text:
            return False

        factory = {
            "gateway": "create_gateway_client",
            "embedding": "create_embedding_provider",
            "vector_store": "create_vector_store",
        }[kind]
        settings_attr = {
            "gateway": "gateway_provider",
            "embedding": "embedding_provider",
            "vector_store": "vector_store_provider",
        }[kind]

        if factory not in text:
            return False

        import_line = (
            "from app.ai.telemetry.spans import AITracingProxy  # fastforge ai-telemetry\n"
        )
        if import_line not in text:
            # Insert after any `from __future__` imports, else at file top.
            future_match = list(
                re.finditer(r"^from __future__ import .*\n", text, flags=re.MULTILINE)
            )
            if future_match:
                idx = future_match[-1].end()
                text = text[:idx] + import_line + text[idx:]
            else:
                text = import_line + text

        head, _, tail = text.partition(f"def {factory}")
        body_end = tail.find("\ndef ")
        if body_end == -1:
            body_end = len(tail)
        body = tail[:body_end]
        rest = tail[body_end:]

        def _wrap(expr: str) -> str:
            return f'AITracingProxy({expr}, kind="{kind}", provider=settings.{settings_attr})'

        # Pattern A: `return cls(<args>)` — wrap directly.
        new_body, n = re.subn(
            r"return\s+cls\((.*?)\)",
            lambda m: f"return {_wrap(f'cls({m.group(1)})')}",
            body,
            count=1,
        )

        # Pattern B: `<name> = cls(<args>)` followed by `return <name>`.
        # Wrap at the `return <name>` site so any in-between init code still runs.
        if n == 0:
            assign_match = re.search(
                r"^(\s+)(\w+)\s*=\s*cls\((.*?)\)\s*$",
                body,
                flags=re.MULTILINE,
            )
            if assign_match:
                varname = assign_match.group(2)
                # Replace the last `return <varname>` with the wrapped form.
                pattern = rf"return\s+{re.escape(varname)}\b"
                # Replace only the LAST occurrence inside this body.
                matches = list(re.finditer(pattern, body))
                if matches:
                    last = matches[-1]
                    new_body = (
                        body[: last.start()] + f"return {_wrap(varname)}" + body[last.end() :]
                    )
                    n = 1

        if n == 0:
            return False

        path.write_text(head + f"def {factory}" + new_body + rest)
        return True

    @staticmethod
    def _patch_ai_config(path: Path) -> bool:
        text = path.read_text()
        if "ai_telemetry_enabled" in text:
            return False
        addition = (
            "\n    # fastforge ai-telemetry\n"
            "    ai_telemetry_enabled: bool = True\n"
            '    ai_tenant_header: str = "X-Tenant-Id"\n'
        )
        # Append before the model_config / Config block if possible, else at file end.
        m = re.search(r"\n\s*(model_config\s*=|class\s+Config\b)", text)
        if m:
            insertion = m.start()
            text = text[:insertion] + addition + text[insertion:]
        else:
            text = text.rstrip() + "\n" + addition
        path.write_text(text)
        return True

    @staticmethod
    def _wire_main(path: Path) -> bool:
        text = path.read_text()
        if "TenantContextMiddleware" in text:
            return False
        # Add import after existing app.* imports
        import_line = "from app.ai.telemetry.tenant import TenantContextMiddleware  # fastforge ai-telemetry\n"
        if "from app.ai." in text:
            text = re.sub(
                r"(from app\.ai\.[^\n]+\n)(?!from app\.ai\.)",
                lambda m: m.group(1) + import_line,
                text,
                count=1,
            )
        else:
            # Fall back: place after the last `from app.` import
            text = re.sub(
                r"(from app\.[^\n]+\n)(?!from app\.)",
                lambda m: m.group(1) + import_line,
                text,
                count=1,
            )

        # Register middleware just after app = FastAPI(...) construction
        text = re.sub(
            r"(app\s*=\s*FastAPI\([^)]*\))",
            r"\1\n    app.add_middleware(TenantContextMiddleware)",
            text,
            count=1,
        )
        path.write_text(text)
        return True

    @staticmethod
    def _add_deps(path: Path) -> bool:
        text = path.read_text()
        changed = False
        for dep in DEPS:
            if dep.strip('"').split(">=")[0] in text:
                continue
            # Insert before the closing bracket of dependencies = [ ... ]
            text, n = re.subn(
                r"(dependencies\s*=\s*\[)(.*?)(\n\])",
                lambda m, _dep=dep: (
                    m.group(1) + m.group(2).rstrip(",\n ") + f",\n    {_dep}" + m.group(3)
                ),
                text,
                count=1,
                flags=re.DOTALL,
            )
            if n:
                changed = True
        if changed:
            path.write_text(text)
        return changed

    @staticmethod
    def _record_capability(path: Path) -> bool:
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError:
            return False
        if data.get("ai_telemetry", {}).get("version") == "1.0.0":
            return False
        data["ai_telemetry"] = {"version": "1.0.0", "tenant_header": "X-Tenant-Id"}
        path.write_text(json.dumps(data, indent=2))
        return True
