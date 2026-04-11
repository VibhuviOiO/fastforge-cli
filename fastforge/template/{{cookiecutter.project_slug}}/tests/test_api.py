from httpx import AsyncClient


class TestHealthEndpoints:
    async def test_health_check(self, client: AsyncClient):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "environment" in data

    async def test_readiness_check(self, client: AsyncClient):
        response = await client.get("/ready")
        assert response.status_code == 200
        assert response.json()["status"] == "ready"


class Test{{ cookiecutter.model_name_class }}API:
    async def test_create_{{ cookiecutter.model_name }}(self, client: AsyncClient):
        payload = {"name": "Test {{ cookiecutter.model_name_class }}", "description": "A test"}
        response = await client.post("/api/v1/{{ cookiecutter.model_name_plural }}/", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test {{ cookiecutter.model_name_class }}"
        assert "id" in data

    async def test_list_{{ cookiecutter.model_name_plural }}(self, client: AsyncClient):
        response = await client.get("/api/v1/{{ cookiecutter.model_name_plural }}/")
        assert response.status_code == 200
        assert "{{ cookiecutter.model_name_plural }}" in response.json()

    async def test_get_{{ cookiecutter.model_name }}_not_found(self, client: AsyncClient):
        response = await client.get("/api/v1/{{ cookiecutter.model_name_plural }}/nonexistent")
        assert response.status_code == 404

    async def test_create_{{ cookiecutter.model_name }}_validation_error(self, client: AsyncClient):
        response = await client.post("/api/v1/{{ cookiecutter.model_name_plural }}/", json={})
        assert response.status_code == 422
{%- if cookiecutter.logging == "structlog" %}


class TestRequestLogging:
    async def test_request_id_header(self, client: AsyncClient):
        response = await client.get("/health")
        assert "X-Request-ID" in response.headers

    async def test_custom_request_id(self, client: AsyncClient):
        response = await client.get("/health", headers={"X-Request-ID": "test-123"})
        assert response.headers["X-Request-ID"] == "test-123"
{%- endif %}
