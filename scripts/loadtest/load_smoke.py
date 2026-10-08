"""Dependency-light concurrency smoke tool for the API surface."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import os

import httpx


async def fetch_many(client: httpx.AsyncClient, url: str, method: str, headers: dict[str, str] | None, body: dict[str, object] | None, count: int, concurrency: int) -> Counter[int]:
    semaphore = asyncio.Semaphore(concurrency)

    async def one_request() -> int:
        async with semaphore:
            response = await client.request(method, url, headers=headers, json=body)
            return response.status_code

    return Counter(await asyncio.gather(*(one_request() for _ in range(count))))


async def run_load(base_url: str, username: str, password: str, requests: int, concurrency: int, client: httpx.AsyncClient | None = None) -> dict[str, object]:
    async def execute(active_client: httpx.AsyncClient) -> dict[str, object]:
        health = await fetch_many(active_client, "/health", "GET", None, None, requests, concurrency)
        login = await fetch_many(active_client, "/auth/login", "POST", {"Content-Type": "application/json"}, {"username": username, "password": password}, requests, concurrency)
        return {"healthStatuses": dict(health), "loginStatuses": dict(login), "requests": requests, "concurrency": concurrency}
    if client is not None:
        return await execute(client)
    async with httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=30) as active_client:
        return await execute(active_client)


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Run a concurrency smoke check against the platform API.")
    parser.add_argument("--base-url", default=os.getenv("BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--username", default=os.getenv("LOAD_USERNAME", "admin"))
    parser.add_argument("--password", default=os.getenv("LOAD_PASSWORD", "admin123"))
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    arguments = parser.parse_args()
    if arguments.requests < 1 or arguments.concurrency < 1:
        raise SystemExit("requests and concurrency must be positive")
    print(await run_load(arguments.base_url, arguments.username, arguments.password, arguments.requests, arguments.concurrency))


if __name__ == "__main__":
    asyncio.run(_main())
