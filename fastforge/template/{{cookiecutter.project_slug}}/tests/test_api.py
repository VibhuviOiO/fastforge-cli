from httpx import AsyncClient


class TestHealthEndpoints:
    async def test_livez(self, client: AsyncClient):
        response = await client.get("/livez")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "alive"
        assert "version" in data
        assert "environment" in data

    async def test_readyz(self, client: AsyncClient):
        response = await client.get("/readyz")
        # 200 when all configured deps are healthy; 503 otherwise. Either is
        # a valid signal that the probe is functioning.
        assert response.status_code in (200, 503)
        body = response.json()
        if response.status_code == 503:
            # FastAPI default: {"detail": payload}.
            # Structlog template handler: {"error": {"message": payload}}.
            body = body.get("detail") or body.get("error", {}).get("message") or {}
        assert "checks" in body
        assert "status" in body


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
        body = response.json()
        assert "{{ cookiecutter.model_name_plural }}" in body
        assert "total" in body
        assert "limit" in body
        assert "offset" in body
        assert body["limit"] == 50
        assert body["offset"] == 0

    async def test_list_pagination_params(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/{{ cookiecutter.model_name_plural }}/", params={"limit": 10, "offset": 5}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["limit"] == 10
        assert body["offset"] == 5

    async def test_list_pagination_rejects_excessive_limit(self, client: AsyncClient):
        response = await client.get(
            "/api/v1/{{ cookiecutter.model_name_plural }}/", params={"limit": 1000}
        )
        assert response.status_code == 422

    async def test_get_{{ cookiecutter.model_name }}_not_found(self, client: AsyncClient):
        response = await client.get("/api/v1/{{ cookiecutter.model_name_plural }}/nonexistent")
        assert response.status_code == 404

    async def test_create_{{ cookiecutter.model_name }}_validation_error(self, client: AsyncClient):
        response = await client.post("/api/v1/{{ cookiecutter.model_name_plural }}/", json={})
        assert response.status_code == 422
{%- if cookiecutter.logging == "structlog" %}


class TestRequestLogging:
    async def test_request_id_header(self, client: AsyncClient):
        response = await client.get("/livez")
        assert "X-Request-ID" in response.headers

    async def test_custom_request_id(self, client: AsyncClient):
        response = await client.get("/livez", headers={"X-Request-ID": "test-123"})
        assert response.headers["X-Request-ID"] == "test-123"
{%- endif %}
