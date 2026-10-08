import asyncio

import httpx
import pytest

from scripts.loadtest.load_smoke import fetch_many, run_load


pytestmark = pytest.mark.unit


def test_fetch_many_counts_concurrent_responses() -> None:
    async def scenario() -> None:
        transport = httpx.MockTransport(lambda request: httpx.Response(200, request=request))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            counts = await fetch_many(client, "/health", "GET", None, None, 25, 5)
        assert counts[200] == 25

    asyncio.run(scenario())


def test_run_load_reports_health_and_login_statuses() -> None:
    async def scenario() -> None:
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200 if request.url.path == "/health" else 401, request=request)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="http://test") as client:
            result = await run_load("http://test", "admin", "admin123", 10, 4, client=client)
        assert result["healthStatuses"][200] == 10
        assert result["loginStatuses"][401] == 10

    asyncio.run(scenario())
