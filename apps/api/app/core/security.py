from __future__ import annotations

import os
import time
from collections import deque


DEVELOPMENT_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3006",
    "http://127.0.0.1:3006",
)


def cors_allowed_origins() -> list[str]:
    """Return explicit browser origins and reject unsafe production defaults."""

    configured = [origin.strip().rstrip("/") for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if origin.strip()]
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    if not configured:
        if app_env == "production":
            raise RuntimeError("CORS_ALLOWED_ORIGINS is required in production")
        return list(DEVELOPMENT_ORIGINS)
    if any(origin == "*" or not origin.startswith("http") for origin in configured):
        raise RuntimeError("CORS_ALLOWED_ORIGINS must contain explicit http(s) origins")
    if app_env == "production" and any(not origin.startswith("https://") for origin in configured):
        raise RuntimeError("production CORS origins must use https")
    return configured


class LoginRateLimiter:
    """Small single-node login limiter; Redis is reserved for multi-node deployments."""

    def __init__(self, maximum_attempts: int, window_seconds: int, clock=time.monotonic) -> None:
        self._maximum_attempts = maximum_attempts
        self._window_seconds = window_seconds
        self._clock = clock
        self._attempts: dict[str, deque[float]] = {}

    def allow(self, key: str) -> bool:
        now = self._clock()
        attempts = self._attempts.setdefault(key, deque())
        while attempts and attempts[0] <= now - self._window_seconds:
            attempts.popleft()
        if len(attempts) >= self._maximum_attempts:
            return False
        attempts.append(now)
        return True


class RedisLoginRateLimiter:
    """Redis-backed login limiter shared by API replicas."""

    def __init__(self, client: object, maximum_attempts: int, window_seconds: int, prefix: str = "xiao-edu:login-rate") -> None:
        self._client = client
        self._maximum_attempts = maximum_attempts
        self._window_seconds = window_seconds
        self._prefix = prefix

    def allow(self, key: str) -> bool:
        counter_key = f"{self._prefix}:{key}"
        pipeline = self._client.pipeline(transaction=True)
        pipeline.incr(counter_key)
        pipeline.ttl(counter_key)
        attempts, ttl = pipeline.execute()
        if ttl < 0:
            self._client.expire(counter_key, self._window_seconds)
        return int(attempts) <= self._maximum_attempts


def build_login_rate_limiter() -> LoginRateLimiter | RedisLoginRateLimiter | None:
    if os.getenv("APP_ENV", "development").strip().lower() != "production":
        return None
    maximum_attempts = int(os.getenv("LOGIN_RATE_LIMIT_MAX", "10"))
    window_seconds = int(os.getenv("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "300"))
    if maximum_attempts < 1 or window_seconds < 1:
        raise RuntimeError("login rate limit settings must be positive integers")
    redis_url = os.getenv("REDIS_URL", "").strip()
    if redis_url:
        try:
            import redis
        except ImportError as exc:
            raise RuntimeError("Redis login limiting requires the redis package") from exc
        return RedisLoginRateLimiter(redis.Redis.from_url(redis_url, decode_responses=True), maximum_attempts, window_seconds)
    return LoginRateLimiter(maximum_attempts, window_seconds)
