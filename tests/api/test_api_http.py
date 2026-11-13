"""API tests: CORS, API key, 504 mapping and reference endpoints.

1. Health stays public.
2. The configured frontend origin gets CORS headers on preflight.
3. When API_KEY is set, write routes reject missing/wrong keys and accept the right one.
4. httpx upstream failures become 504, not 500.
5. Reference endpoints return usable crop/objective/season data.
"""

import httpx
from fastapi.testclient import TestClient

from cropseq.api.main import create_app
from cropseq.config import config


def _client() -> TestClient:
    return TestClient(create_app())


def test_health_is_public() -> None:
    response = _client().get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_allows_the_dev_origin(monkeypatch) -> None:
    monkeypatch.setattr(config, "cors_origins", "http://localhost:3000")
    client = TestClient(create_app())
    response = client.options(
        "/api/v1/recommendations/optimize",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-api-key",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_rejects_unknown_origin(monkeypatch) -> None:
    monkeypatch.setattr(config, "cors_origins", "http://localhost:3000")
    client = TestClient(create_app())
    response = client.options(
        "/api/v1/recommendations/optimize",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in response.headers


def test_api_key_blocks_missing_header(monkeypatch) -> None:
    monkeypatch.setattr(config, "api_key", "secret")
    response = _client().post("/api/v1/intake/message", json={"messages": []})
    assert response.status_code == 401
    assert "API key" in response.json()["detail"]


def test_api_key_blocks_wrong_header(monkeypatch) -> None:
    monkeypatch.setattr(config, "api_key", "secret")
    response = _client().post(
        "/api/v1/intake/message",
        json={"messages": []},
        headers={"X-API-Key": "wrong"},
    )
    assert response.status_code == 401


def test_api_key_accepts_correct_header(monkeypatch) -> None:
    monkeypatch.setattr(config, "api_key", "secret")
    response = _client().post(
        "/api/v1/intake/message",
        json={"messages": []},
        headers={"X-API-Key": "secret"},
    )
    assert response.status_code == 200
    assert "reply" in response.json()


def test_upstream_failure_maps_to_504() -> None:
    app = create_app()

    @app.get("/boom")
    def boom() -> None:
        raise httpx.ConnectError("upstream down")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/boom")
    assert response.status_code == 504
    assert "unavailable" in response.json()["detail"]


def test_objectives_endpoint() -> None:
    response = _client().get("/api/v1/objectives")
    assert response.status_code == 200
    keys = [item["key"] for item in response.json()]
    assert keys == config.objectives
    assert all(item["label"] and item["unit"] for item in response.json())


def test_seasons_endpoint() -> None:
    response = _client().get("/api/v1/seasons")
    assert response.status_code == 200
    assert [item["name"] for item in response.json()] == [
        season.name for season in config.seasons
    ]


def test_crops_endpoint_has_real_crops_and_fallow() -> None:
    response = _client().get("/api/v1/crops")
    assert response.status_code == 200
    items = response.json()
    assert any(item["crop_id"] == "999" for item in items)
    assert any(item["name"] == "Wheat" for item in items)
    assert all(item["crop_id"] and item["name"] for item in items)
