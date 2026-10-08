from fastapi.testclient import TestClient

from apps.api.app.main import create_app


def test_local_web_origins_can_call_api_but_unknown_origin_is_not_allowed() -> None:
    client = TestClient(create_app())

    local = client.options(
        "/auth/login",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"},
    )
    preview = client.options(
        "/auth/login",
        headers={"Origin": "http://127.0.0.1:3006", "Access-Control-Request-Method": "POST"},
    )
    unknown = client.options(
        "/auth/login",
        headers={"Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST"},
    )

    assert local.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert preview.headers["access-control-allow-origin"] == "http://127.0.0.1:3006"
    assert "access-control-allow-origin" not in unknown.headers
