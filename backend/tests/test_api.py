import json

import pytest
from conftest import ACCESS_TOKEN, plan_for
from fastapi.testclient import TestClient
from onelap.config import Settings
from onelap.main import MAX_BODY_BYTES, create_app

HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}"}


def test_health_works_without_credentials_or_provider(tmp_path):
    app = create_app(Settings(data_dir=tmp_path))
    with TestClient(app) as client:
        assert client.get("/health").json() == {"service": "onelap", "status": "ok"}
        assert client.get("/api/model/status").status_code == 503
        assert client.get("/docs").status_code == 404
        assert client.get("/openapi.json").status_code == 404
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("authorization", [None, "Bearer wrong", ACCESS_TOKEN, "Basic abc"])
def test_unauthorized_requests_do_not_reach_model(provider_factory, request_data, authorization):
    provider, runtime, creations = provider_factory()
    headers = {} if authorization is None else {"Authorization": authorization}
    with TestClient(create_app(provider.settings, provider)) as client:
        response = client.post("/api/missions", json=request_data, headers=headers)
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
    assert creations == runtime.samples == []


def test_generate_endpoint_uses_model_and_returns_identity(provider_factory, request_data):
    provider, runtime, _ = provider_factory()
    with TestClient(create_app(provider.settings, provider)) as client:
        response = client.post("/api/missions", json=request_data, headers=HEADERS)
        assert response.status_code == 201
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["mission"]["minutes"] == request_data["minutes"]
        assert response.json()["generation"]["target"] == "base"
        assert len(runtime.samples) == 1
        status = client.get("/api/model/status", headers=HEADERS).json()
        assert status["reserved_requests"] == 1


def test_default_disabled_endpoint_does_not_sample(provider_factory, request_data):
    provider, _, creations = provider_factory(changes={"hosted_enabled": False})
    with TestClient(create_app(provider.settings, provider)) as client:
        response = client.post("/api/missions", json=request_data, headers=HEADERS)
        assert response.status_code == 503
        assert response.json() == {"error": "hosted_requests_disabled"}
    assert creations == []


def test_private_invalid_input_is_not_echoed(provider_factory, request_data):
    provider, runtime, _ = provider_factory()
    request_data["location"] = "PRIVATE_ADDRESS_DO_NOT_ECHO"
    with TestClient(create_app(provider.settings, provider)) as client:
        response = client.post("/api/missions", json=request_data, headers=HEADERS)
        assert response.status_code == 422
        assert "PRIVATE_ADDRESS_DO_NOT_ECHO" not in response.text
    assert runtime.samples == []


@pytest.mark.parametrize(
    "content",
    [
        b"a" * (MAX_BODY_BYTES + 1),
        b'{"minutes":10,"minutes":20}',
        b"malformed PRIVATE_TEXT",
        b"\xff",
    ],
)
def test_invalid_or_oversized_body_no_sample(provider_factory, content):
    provider, runtime, creations = provider_factory()
    with TestClient(create_app(provider.settings, provider)) as client:
        response = client.post("/api/missions", content=content, headers=HEADERS)
        assert response.status_code in (413, 422)
        assert "PRIVATE_TEXT" not in response.text
    assert creations == runtime.samples == []


def test_policy_rejection_is_visible_not_a_fake_success(
    provider_factory, mission_request, request_data
):
    data = plan_for(mission_request)
    data["instruction"] = "Take a photo."
    provider, runtime, _ = provider_factory(text=json.dumps(data))
    with TestClient(create_app(provider.settings, provider)) as client:
        response = client.post("/api/missions", json=request_data, headers=HEADERS)
        assert response.status_code == 502
        assert response.json() == {"error": "mission_policy_rejected"}
        assert "mission" not in response.json()
    assert len(runtime.samples) == 1


def test_no_retry_after_failed_model_request(provider_factory, request_data):
    provider, runtime, _ = provider_factory()
    runtime.failure = RuntimeError("PRIVATE KEY")
    with TestClient(create_app(provider.settings, provider)) as client:
        response = client.post("/api/missions", json=request_data, headers=HEADERS)
        assert response.status_code == 503
        assert "PRIVATE" not in response.text
        assert "key" not in response.text.lower()
    assert len(runtime.samples) == 1


def test_rate_limit_prevents_seventh_generation(provider_factory, request_data):
    provider, runtime, _ = provider_factory()
    with TestClient(create_app(provider.settings, provider)) as client:
        for _ in range(6):
            assert (
                client.post("/api/missions", json=request_data, headers=HEADERS).status_code == 201
            )
        response = client.post("/api/missions", json=request_data, headers=HEADERS)
        assert response.status_code == 429
        assert response.json()["error"] == "request_rate_limited"
    assert len(runtime.samples) == 6


def test_status_and_invalid_provider_settings_are_private(settings, provider_factory):
    provider, _, _ = provider_factory()
    with TestClient(create_app(provider.settings, provider)) as client:
        assert client.get("/api/model/status").status_code == 401
        response = client.get("/api/model/status", headers=HEADERS)
        assert settings.api_key not in response.text
        assert settings.access_token not in response.text
    with pytest.raises(ValueError, match="settings must match"):
        create_app(Settings(), provider)


def test_unauthorized_malformed_body_is_not_parsed(provider_factory):
    provider, _, creations = provider_factory()
    with TestClient(create_app(provider.settings, provider)) as client:
        response = client.post("/api/missions", content=b"PRIVATE malformed data")
        assert response.status_code == 401
        assert "PRIVATE" not in response.text
    assert creations == []


def test_extreme_content_length_rejected(provider_factory):
    provider, _, creations = provider_factory()
    with TestClient(create_app(provider.settings, provider)) as client:
        response = client.post(
            "/api/missions",
            content=b"{}",
            headers={**HEADERS, "Content-Length": "9" * 5000},
        )
        assert response.status_code == 413
    assert creations == []


def test_deep_json_is_rejected_without_provider_access(provider_factory):
    provider, _, creations = provider_factory()
    with TestClient(create_app(provider.settings, provider)) as client:
        response = client.post(
            "/api/missions",
            content="[" * 2000 + "]" * 2000,
            headers=HEADERS,
        )
        assert response.status_code == 422
    assert creations == []
