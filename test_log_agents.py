"""Test fastforge app generation and fastforge-infra generation."""
import os
import tempfile
from cookiecutter.main import cookiecutter

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "fastforge", "template")
INFRA_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "fastforge", "infra_template")


def gen_app(extra, output_dir):
    base = {
        "project_name": "test-project",
        "project_slug": "test-project",
        "package_name": "test_project",
        "description": "test",
        "author_name": "Test",
        "author_email": "test@test.com",
        "python_version": "3.11",
        "port": "8000",
        "logging": "none",
        "log_format": "console",
        "log_connector": "stdout",
        "tracing": "none",
        "tracing_backend": "none",
        "metrics": "none",
        "streaming": "none",
        "database": "none",
        "secrets": "none",
        "vault_auth": "token",
        "devsecops": "none",
        "devsecops_bandit": "no",
        "devsecops_gitleaks": "no",
        "devsecops_trivy": "no",
        "devsecops_hadolint": "no",
        "devsecops_pip_audit": "no",
        "devsecops_detect_secrets": "no",
        "precommit": "no",
        "ci": "none",
        "ci_security_scan": "no",
        "docker": "no",
        "docker_debug": "no",
        "deploy_compose": "no",
        "deploy_kubernetes": "no",
        "deploy_k8s_manifests": "no",
        "deploy_k8s_helm": "no",
        "deploy_swarm": "no",
        "deploy_marathon": "no",
    }
    base.update(extra)
    return cookiecutter(TEMPLATE_DIR, no_input=True, extra_context=base, output_dir=output_dir)


def gen_infra(extra, output_dir):
    base = {
        "project_slug": "test-project",
        "log_agent": "none",
        "log_aggregator": "none",
        "streaming": "none",
        "database": "none",
        "secrets": "none",
    }
    base.update(extra)
    return cookiecutter(INFRA_TEMPLATE_DIR, no_input=True, extra_context=base, output_dir=output_dir)


# ── App Tests ────────────────────────────────────────────────────────────────

def test_minimal_app():
    """Minimal app — no infra dir, has security headers."""
    with tempfile.TemporaryDirectory() as td:
        p = gen_app({}, td)
        assert not os.path.exists(os.path.join(p, "infrastructure")), "infrastructure/ should NOT exist"
        assert os.path.exists(os.path.join(p, "app", "main.py"))
        assert os.path.exists(os.path.join(p, "app", "middleware", "security_headers.py"))
        assert os.path.exists(os.path.join(p, "app", "config.py"))

        with open(os.path.join(p, "app", "main.py")) as f:
            content = f.read()
        assert "CORSMiddleware" in content, "CORS not in main.py"
        assert "SecurityHeadersMiddleware" in content, "Security headers not in main.py"

        with open(os.path.join(p, "app", "config.py")) as f:
            content = f.read()
        assert "cors_origins" in content, "cors_origins not in config.py"

        print("  PASS: Minimal app")


def test_structured_logging_app():
    """App with structured logging — has exception handlers."""
    with tempfile.TemporaryDirectory() as td:
        p = gen_app({"logging": "structlog", "log_format": "json", "log_connector": "stdout"}, td)
        assert os.path.exists(os.path.join(p, "app", "api", "exception_handlers.py"))
        assert os.path.exists(os.path.join(p, "app", "middleware", "logging_middleware.py"))
        assert not os.path.exists(os.path.join(p, "infrastructure"))

        with open(os.path.join(p, "app", "main.py")) as f:
            content = f.read()
        assert "register_exception_handlers" in content
        assert "CORSMiddleware" in content

        print("  PASS: Structured logging app")


def test_full_app():
    """Full-featured app — still no infra dir."""
    with tempfile.TemporaryDirectory() as td:
        p = gen_app({
            "logging": "structlog", "log_format": "json", "log_connector": "file",
            "tracing": "opentelemetry", "tracing_backend": "jaeger",
            "metrics": "prometheus",
            "streaming": "producer",
            "database": "postgres",
            "secrets": "vault", "vault_auth": "both",
            "docker": "yes", "docker_debug": "yes",
            "deploy_kubernetes": "yes", "deploy_k8s_manifests": "yes",
            "ci": "github_actions", "ci_security_scan": "yes",
        }, td)
        assert not os.path.exists(os.path.join(p, "infrastructure"))
        assert os.path.exists(os.path.join(p, "app", "vault.py"))
        assert os.path.exists(os.path.join(p, "app", "streaming"))
        assert os.path.exists(os.path.join(p, "app", "db"))
        assert os.path.exists(os.path.join(p, "deploy", "kubernetes"))
        assert os.path.exists(os.path.join(p, "Dockerfile"))
        assert os.path.exists(os.path.join(p, "app", "middleware", "security_headers.py"))
        assert os.path.exists(os.path.join(p, "app", "api", "exception_handlers.py"))
        print("  PASS: Full app (all features, no infra)")


# ── Infra Tests ──────────────────────────────────────────────────────────────

def test_infra_vector_vector():
    """Infra: Vector agent + Vector aggregator."""
    with tempfile.TemporaryDirectory() as td:
        p = gen_infra({"log_agent": "vector", "log_aggregator": "vector"}, td)
        assert os.path.exists(os.path.join(p, "docker-compose.yml"))
        assert os.path.exists(os.path.join(p, "docker-compose.vector-agent.yml"))
        assert os.path.exists(os.path.join(p, "docker-compose.vector-aggregator.yml"))
        assert os.path.exists(os.path.join(p, "docker-compose.elasticsearch.yml"))
        assert os.path.exists(os.path.join(p, "docker-compose.kafka.yml"))
        assert os.path.exists(os.path.join(p, "vector", "vector-agent.toml"))
        assert os.path.exists(os.path.join(p, "vector", "vector-aggregator.toml"))
        assert not os.path.exists(os.path.join(p, "docker-compose.fluentbit.yml"))
        assert not os.path.exists(os.path.join(p, "docker-compose.logstash.yml"))
        assert not os.path.exists(os.path.join(p, "fluentbit"))
        assert not os.path.exists(os.path.join(p, "logstash"))
        print("  PASS: Infra Vector + Vector")


def test_infra_fluentbit_logstash():
    """Infra: FluentBit agent + Logstash aggregator."""
    with tempfile.TemporaryDirectory() as td:
        p = gen_infra({"log_agent": "fluentbit", "log_aggregator": "logstash"}, td)
        assert os.path.exists(os.path.join(p, "docker-compose.fluentbit.yml"))
        assert os.path.exists(os.path.join(p, "docker-compose.logstash.yml"))
        assert os.path.exists(os.path.join(p, "docker-compose.elasticsearch.yml"))
        assert os.path.exists(os.path.join(p, "fluentbit", "fluent-bit.conf"))
        assert os.path.exists(os.path.join(p, "logstash", "pipeline", "logstash.conf"))
        assert not os.path.exists(os.path.join(p, "docker-compose.vector-agent.yml"))
        assert not os.path.exists(os.path.join(p, "docker-compose.vector-aggregator.yml"))
        assert not os.path.exists(os.path.join(p, "vector"))
        print("  PASS: Infra FluentBit + Logstash")


def test_infra_vector_logstash():
    """Infra: Vector agent + Logstash aggregator."""
    with tempfile.TemporaryDirectory() as td:
        p = gen_infra({"log_agent": "vector", "log_aggregator": "logstash"}, td)
        assert os.path.exists(os.path.join(p, "docker-compose.vector-agent.yml"))
        assert os.path.exists(os.path.join(p, "docker-compose.logstash.yml"))
        assert os.path.exists(os.path.join(p, "vector", "vector-agent.toml"))
        assert not os.path.exists(os.path.join(p, "vector", "vector-aggregator.toml"))
        assert not os.path.exists(os.path.join(p, "docker-compose.fluentbit.yml"))
        assert not os.path.exists(os.path.join(p, "docker-compose.vector-aggregator.yml"))
        print("  PASS: Infra Vector + Logstash")


def test_infra_fluentbit_vector():
    """Infra: FluentBit agent + Vector aggregator."""
    with tempfile.TemporaryDirectory() as td:
        p = gen_infra({"log_agent": "fluentbit", "log_aggregator": "vector"}, td)
        assert os.path.exists(os.path.join(p, "docker-compose.fluentbit.yml"))
        assert os.path.exists(os.path.join(p, "docker-compose.vector-aggregator.yml"))
        assert os.path.exists(os.path.join(p, "vector", "vector-aggregator.toml"))
        assert not os.path.exists(os.path.join(p, "vector", "vector-agent.toml"))
        assert not os.path.exists(os.path.join(p, "docker-compose.vector-agent.yml"))
        print("  PASS: Infra FluentBit + Vector")


def test_infra_no_log_pipeline():
    """Infra: No log pipeline — just Kafka + DB + Vault."""
    with tempfile.TemporaryDirectory() as td:
        p = gen_infra({
            "streaming": "enabled",
            "database": "postgres",
            "secrets": "vault",
        }, td)
        assert os.path.exists(os.path.join(p, "docker-compose.kafka.yml"))
        assert os.path.exists(os.path.join(p, "docker-compose.postgres.yml"))
        assert os.path.exists(os.path.join(p, "docker-compose.vault.yml"))
        assert os.path.exists(os.path.join(p, "vault", "config.hcl"))
        assert not os.path.exists(os.path.join(p, "docker-compose.vector-agent.yml"))
        assert not os.path.exists(os.path.join(p, "docker-compose.fluentbit.yml"))
        assert not os.path.exists(os.path.join(p, "docker-compose.elasticsearch.yml"))
        assert not os.path.exists(os.path.join(p, "vector"))
        assert not os.path.exists(os.path.join(p, "fluentbit"))
        print("  PASS: Infra no log pipeline (Kafka + Postgres + Vault)")


def test_infra_mongodb():
    """Infra: MongoDB only."""
    with tempfile.TemporaryDirectory() as td:
        p = gen_infra({"database": "mongodb"}, td)
        assert os.path.exists(os.path.join(p, "docker-compose.mongodb.yml"))
        assert not os.path.exists(os.path.join(p, "docker-compose.postgres.yml"))
        assert not os.path.exists(os.path.join(p, "docker-compose.kafka.yml"))
        print("  PASS: Infra MongoDB only")


if __name__ == "__main__":
    print("=== App Generation Tests ===")
    test_minimal_app()
    test_structured_logging_app()
    test_full_app()

    print("\n=== Infrastructure Generation Tests ===")
    test_infra_vector_vector()
    test_infra_fluentbit_logstash()
    test_infra_vector_logstash()
    test_infra_fluentbit_vector()
    test_infra_no_log_pipeline()
    test_infra_mongodb()

    print("\n✅ All 9 tests passed!")
