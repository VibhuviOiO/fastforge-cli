FROM python:{{cookiecutter.python_version}}-slim AS base

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY app/ app/
{%- if cookiecutter.log_connector == "file" %}

RUN mkdir -p /var/log/app
{%- endif %}

RUN adduser --disabled-password --gecos "" appuser
{%- if cookiecutter.log_connector == "file" %} \
    && chown -R appuser:appuser /var/log/app
{%- endif %}

USER appuser

EXPOSE {{cookiecutter.port}}

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:{{cookiecutter.port}}/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "{{cookiecutter.port}}", "--log-level", "info"]
