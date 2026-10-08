import pytest
from fastapi.testclient import TestClient

from apps.api.app.main import create_app


pytestmark = pytest.mark.integration


def test_api_responses_include_browser_security_headers() -> None:
    response = TestClient(create_app()).get("/health")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"
