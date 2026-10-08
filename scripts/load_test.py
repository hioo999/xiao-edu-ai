from __future__ import annotations

import argparse
import concurrent.futures
import statistics
import time

import httpx


def run_load_test(base_url: str, requests: int, concurrency: int) -> dict[str, float | int]:
    def request_health() -> float:
        started = time.perf_counter()
        with httpx.Client(timeout=10, trust_env=False) as client:
            response = client.get(f"{base_url.rstrip('/')}/health")
            response.raise_for_status()
        return (time.perf_counter() - started) * 1000

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        latencies = list(executor.map(lambda _: request_health(), range(requests)))
    return {"requests": requests, "concurrency": concurrency, "p50_ms": round(statistics.median(latencies), 2), "p95_ms": round(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)], 2)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a non-generative health endpoint load test.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--requests", type=int, default=100)
    parser.add_argument("--concurrency", type=int, default=10)
    arguments = parser.parse_args()
    if arguments.requests < 1 or arguments.concurrency < 1:
        raise SystemExit("requests and concurrency must be positive")
    print(run_load_test(arguments.base_url, arguments.requests, arguments.concurrency))
