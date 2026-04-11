from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "{{ cookiecutter.project_slug }}"
    app_env: str = "development"
    app_version: str = "0.1.0"
    app_host: str = "0.0.0.0"  # noqa: S104
    app_port: int = {{ cookiecutter.port }}
    app_workers: int = 1

    # CORS
    cors_origins: list[str] = ["*"]
{%- if cookiecutter.logging == "structlog" %}

    # Logging
    log_format: str = "{{ cookiecutter.log_format }}"
    log_level: str = "INFO"
    log_file_enabled: bool = {{ "True" if cookiecutter.log_connector == "file" else "False" }}
    log_file_path: str = "/var/log/app/app.log"
    log_file_max_bytes: int = 52428800  # 50MB
    log_file_backup_count: int = 5
{%- else %}
    log_level: str = "INFO"
{%- endif %}
{%- if cookiecutter.database == "postgres" %}

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/{{ cookiecutter.package_name }}"
{%- endif %}
{%- if cookiecutter.database == "mysql" %}

    # MySQL
    database_url: str = "mysql+aiomysql://root:root@localhost:3306/{{ cookiecutter.package_name }}"
{%- endif %}
{%- if cookiecutter.database == "sqlite" %}

    # SQLite
    database_url: str = "sqlite+aiosqlite:///./{{ cookiecutter.package_name }}.db"
{%- endif %}
{%- if cookiecutter.database == "mongodb" %}

    # MongoDB
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "{{ cookiecutter.package_name }}"
{%- endif %}
{%- if cookiecutter.cache == "redis" or cookiecutter.streaming == "redis_pubsub" %}

    # Redis
    redis_url: str = "redis://localhost:6379/0"
{%- endif %}
{%- if cookiecutter.cache == "memcached" %}

    # Memcached
    memcached_host: str = "localhost"
    memcached_port: int = 11211
{%- endif %}
{%- if cookiecutter.streaming == "kafka" %}

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic: str = "{{ cookiecutter.project_slug }}-events"
    kafka_group_id: str = "{{ cookiecutter.project_slug }}-group"
{%- endif %}
{%- if cookiecutter.streaming == "rabbitmq" %}

    # RabbitMQ
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    rabbitmq_topic: str = "{{ cookiecutter.project_slug }}-events"
{%- endif %}
{%- if cookiecutter.streaming == "nats" %}

    # NATS
    nats_url: str = "nats://localhost:4222"
    nats_topic: str = "{{ cookiecutter.project_slug }}-events"
{%- endif %}
{%- if cookiecutter.secrets == "vault" %}

    # HashiCorp Vault
    vault_url: str = "http://localhost:8200"
    vault_token: str = ""
    vault_mount_point: str = "secret"
    vault_secret_path: str = "{{ cookiecutter.project_slug }}"
{%- endif %}
{%- if cookiecutter.secrets == "aws_sm" %}

    # AWS Secrets Manager
    aws_region: str = "us-east-1"
    aws_secret_name: str = "{{ cookiecutter.project_slug }}"
{%- endif %}
{%- if cookiecutter.secrets == "azure_kv" %}

    # Azure Key Vault
    azure_vault_url: str = "https://your-vault.vault.azure.net"
{%- endif %}
{%- if cookiecutter.secrets == "gcp_sm" %}

    # GCP Secret Manager
    gcp_project_id: str = "your-project-id"
    gcp_secret_name: str = "{{ cookiecutter.project_slug }}"
{%- endif %}

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
