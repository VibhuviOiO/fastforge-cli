"""Post-generation hook for infrastructure template — removes unused service files."""

import os
import shutil

PROJECT_DIR = os.path.realpath(os.path.curdir)


def remove_path(rel_path: str) -> None:
    abs_path = os.path.join(PROJECT_DIR, rel_path)
    if os.path.isdir(abs_path):
        shutil.rmtree(abs_path)
    elif os.path.isfile(abs_path):
        os.remove(abs_path)


# ── Log Agent ────────────────────────────────────────────────────────────────
log_agent = "{{ cookiecutter.log_agent }}"
log_aggregator = "{{ cookiecutter.log_aggregator }}"

if log_agent == "none":
    remove_path("docker-compose.vector-agent.yml")
    remove_path("docker-compose.fluentbit.yml")
elif log_agent == "vector":
    remove_path("docker-compose.fluentbit.yml")
    remove_path("fluentbit")
elif log_agent == "fluentbit":
    remove_path("docker-compose.vector-agent.yml")
    remove_path("vector/vector-agent.toml")

# ── Log Aggregator ───────────────────────────────────────────────────────────
if log_aggregator == "none":
    remove_path("docker-compose.vector-aggregator.yml")
    remove_path("docker-compose.logstash.yml")
    remove_path("docker-compose.elasticsearch.yml")
elif log_aggregator == "vector":
    remove_path("docker-compose.logstash.yml")
    remove_path("logstash")
elif log_aggregator == "logstash":
    remove_path("docker-compose.vector-aggregator.yml")
    remove_path("vector/vector-aggregator.toml")

# Clean up empty vector dir if neither uses it
if log_agent != "vector" and log_aggregator != "vector":
    remove_path("vector")

# Remove FluentBit if not used as agent
if log_agent != "fluentbit":
    remove_path("fluentbit")

# Remove Logstash if not used as aggregator
if log_aggregator != "logstash":
    remove_path("logstash")

# No log pipeline means no ES/Kibana needed
if log_agent == "none" and log_aggregator == "none":
    remove_path("docker-compose.elasticsearch.yml")

# ── Kafka ────────────────────────────────────────────────────────────────────
# Kafka needed for streaming OR as log transport
needs_kafka = "{{ cookiecutter.streaming }}" != "none" or log_agent != "none"
if not needs_kafka:
    remove_path("docker-compose.kafka.yml")

# ── Database ─────────────────────────────────────────────────────────────────
if "{{ cookiecutter.database }}" != "postgres":
    remove_path("docker-compose.postgres.yml")
if "{{ cookiecutter.database }}" != "mongodb":
    remove_path("docker-compose.mongodb.yml")

# ── Vault ────────────────────────────────────────────────────────────────────
if "{{ cookiecutter.secrets }}" != "vault":
    remove_path("docker-compose.vault.yml")
    remove_path("vault")

print("\n✅ Infrastructure stack generated: {{ cookiecutter.project_slug }}-infrastructure/")
print("   cd {{ cookiecutter.project_slug }}-infrastructure && docker compose up -d")
