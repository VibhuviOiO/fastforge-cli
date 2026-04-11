"""Secret management — {{ cookiecutter.secrets }} provider."""

import asyncio
{%- if cookiecutter.logging == "structlog" %}

from app.logging_config import get_logger

logger = get_logger(__name__)
{%- else %}

from logging import getLogger

logger = getLogger(__name__)
{%- endif %}

from app.config import settings
{%- if cookiecutter.secrets == "vault" %}


def _load_vault_secrets() -> dict:
    """Load secrets from HashiCorp Vault (sync — runs in thread pool)."""
    import hvac

    client = hvac.Client(url=settings.vault_url, token=settings.vault_token)
    if not client.is_authenticated():
        logger.warning("vault_auth_failed", url=settings.vault_url)
        return {}

    response = client.secrets.kv.v2.read_secret_version(
        path=settings.vault_secret_path,
        mount_point=settings.vault_mount_point,
    )
    secrets = response["data"]["data"]
    logger.info("vault_secrets_loaded", path=settings.vault_secret_path, count=len(secrets))
    return secrets


async def load_secrets() -> dict:
    """Load secrets from Vault (async wrapper)."""
    return await asyncio.to_thread(_load_vault_secrets)
{%- elif cookiecutter.secrets == "aws_sm" %}


def _load_aws_secrets() -> dict:
    """Load secrets from AWS Secrets Manager (sync — runs in thread pool)."""
    import json

    import boto3

    client = boto3.client("secretsmanager", region_name=settings.aws_region)
    response = client.get_secret_value(SecretId=settings.aws_secret_name)
    secrets = json.loads(response["SecretString"])
    logger.info("aws_secrets_loaded", secret_name=settings.aws_secret_name, count=len(secrets))
    return secrets


async def load_secrets() -> dict:
    """Load secrets from AWS Secrets Manager (async wrapper)."""
    return await asyncio.to_thread(_load_aws_secrets)
{%- elif cookiecutter.secrets == "azure_kv" %}


def _load_azure_secrets() -> dict:
    """Load secrets from Azure Key Vault (sync — runs in thread pool)."""
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient

    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=settings.azure_vault_url, credential=credential)
    secrets = {}
    for prop in client.list_properties_of_secrets():
        secret = client.get_secret(prop.name)
        secrets[prop.name] = secret.value
    logger.info("azure_secrets_loaded", vault=settings.azure_vault_url, count=len(secrets))
    return secrets


async def load_secrets() -> dict:
    """Load secrets from Azure Key Vault (async wrapper)."""
    return await asyncio.to_thread(_load_azure_secrets)
{%- elif cookiecutter.secrets == "gcp_sm" %}


def _load_gcp_secrets() -> dict:
    """Load secrets from GCP Secret Manager (sync — runs in thread pool)."""
    import json

    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{settings.gcp_project_id}/secrets/{settings.gcp_secret_name}/versions/latest"
    response = client.access_secret_version(name=name)
    secrets = json.loads(response.payload.data.decode())
    logger.info("gcp_secrets_loaded", project=settings.gcp_project_id, count=len(secrets))
    return secrets


async def load_secrets() -> dict:
    """Load secrets from GCP Secret Manager (async wrapper)."""
    return await asyncio.to_thread(_load_gcp_secrets)
{%- endif %}
