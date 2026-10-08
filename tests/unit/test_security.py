import pytest

from apps.api.app.core.security import LoginRateLimiter, RedisLoginRateLimiter, build_login_rate_limiter, cors_allowed_origins


pytestmark = pytest.mark.unit


def test_cors_uses_development_origins_when_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)

    assert "http://localhost:3000" in cors_allowed_origins()


def test_cors_requires_explicit_origin_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)

    with pytest.raises(RuntimeError, match="required"):
        cors_allowed_origins()


def test_cors_rejects_wildcard_and_non_https_production_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")
    with pytest.raises(RuntimeError, match="explicit"):
        cors_allowed_origins()

    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://ai.example.com")
    with pytest.raises(RuntimeError, match="https"):
        cors_allowed_origins()


def test_cors_accepts_multiple_https_production_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "https://ai.example.com, https://teacher.example.com/")

    assert cors_allowed_origins() == ["https://ai.example.com", "https://teacher.example.com"]


def test_login_rate_limiter_blocks_until_its_window_expires() -> None:
    now = [0.0]
    limiter = LoginRateLimiter(2, 60, clock=lambda: now[0])

    assert limiter.allow("127.0.0.1") is True
    assert limiter.allow("127.0.0.1") is True
    assert limiter.allow("127.0.0.1") is False
    now[0] = 61.0
    assert limiter.allow("127.0.0.1") is True


def test_login_rate_limiter_is_only_enabled_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    assert build_login_rate_limiter() is None

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("LOGIN_RATE_LIMIT_MAX", "2")
    monkeypatch.setenv("LOGIN_RATE_LIMIT_WINDOW_SECONDS", "30")
    assert isinstance(build_login_rate_limiter(), LoginRateLimiter)


def test_redis_login_rate_limiter_uses_shared_counter_and_expiry() -> None:
    class Pipeline:
        def __init__(self, client) -> None:
            self.client = client
        def incr(self, key: str): self.client.key = key; return self
        def ttl(self, key: str): return self
        def execute(self): self.client.count += 1; return self.client.count, -1
    class Client:
        count = 0
        key = ""
        def pipeline(self, transaction: bool): return Pipeline(self)
        def expire(self, key: str, seconds: int): self.expiry = (key, seconds)
    client = Client()
    limiter = RedisLoginRateLimiter(client, 2, 60)

    assert limiter.allow("127.0.0.1") is True
    assert limiter.allow("127.0.0.1") is True
    assert limiter.allow("127.0.0.1") is False
    assert client.expiry == ("xiao-edu:login-rate:127.0.0.1", 60)
