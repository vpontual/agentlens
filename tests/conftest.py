import pytest
import pytest_asyncio
import httpx
from main import app
from typing import AsyncGenerator

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest_asyncio.fixture
async def client() -> AsyncGenerator[httpx.AsyncClient, None]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
