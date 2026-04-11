# {{ cookiecutter.project_slug }} — Infrastructure Stack

Docker Compose stack for supporting services (local development / staging).

## Quick Start

```bash
docker compose up -d
```

## Services

| Service | Port | Description |
|---------|------|-------------|
| App | 8000 | FastAPI application |
{%- if cookiecutter.log_agent == "vector" %}
| Vector Agent | — | Log collector (file → Kafka) |
{%- elif cookiecutter.log_agent == "fluentbit" %}
| Fluent Bit | — | Log collector (file → Kafka) |
{%- endif %}
{%- if cookiecutter.log_aggregator == "vector" %}
| Vector Aggregator | — | Log pipeline (Kafka → Elasticsearch) |
{%- elif cookiecutter.log_aggregator == "logstash" %}
| Logstash | — | Log pipeline (Kafka → Elasticsearch) |
{%- endif %}
{%- if cookiecutter.log_agent != "none" or cookiecutter.log_aggregator != "none" %}
| Elasticsearch | 9200 | Log storage |
| Kibana | 5601 | Log visualization |
{%- endif %}
{%- if cookiecutter.streaming != "none" or cookiecutter.log_agent != "none" %}
| Kafka | 9092 | Message broker |
{%- endif %}
{%- if cookiecutter.database == "postgres" %}
| PostgreSQL | 5432 | Database |
{%- endif %}
{%- if cookiecutter.database == "mongodb" %}
| MongoDB | 27017 | Database |
{%- endif %}
{%- if cookiecutter.secrets == "vault" %}
| Vault | 8200 | Secret management |
{%- endif %}
