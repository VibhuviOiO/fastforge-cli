import os

import pytest
from httpx import ASGITransport, AsyncClient

# Disable file logging for tests (avoids /var/log/app permission issues locally)
os.environ.setdefault("LOG_FILE_ENABLED", "false")

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
