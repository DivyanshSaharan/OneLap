import pytest
from fastapi.testclient import TestClient
from onelap.config import Settings
from onelap.journal_config import PERSONAL_OWNER, JournalSettings
from onelap.main import create_app


def local_client(app, **options):
    return TestClient(app, base_url="http://127.0.0.1:8770", client=("127.0.0.1", 50000), **options)


def test_token_free_local_status_keeps_cloud_and_model_disabled(tmp_path, request_data):
    with local_client(create_app(Settings(data_dir=tmp_path))) as client:
        status = client.get("/api/model/status")
        assert status.status_code == 200
        assert status.json()["disabled_reason"] == "hosted_requests_disabled"
        assert status.headers["cache-control"] == "no-store"
        assert client.get("/api/journal/status").json()["disabled_reason"] == "journal_disabled"
        assert client.post("/api/missions", json=request_data).status_code == 503
    assert list(tmp_path.iterdir()) == []


def test_local_mode_can_generate_only_through_approved_provider_double(
    provider_factory, request_data
):
    provider, runtime, _ = provider_factory(changes={"access_token": ""})
    with local_client(create_app(provider.settings, provider)) as client:
        assert client.post("/api/missions", json=request_data).status_code == 201
    assert len(runtime.samples) == 1


@pytest.mark.parametrize(
    "headers",
    [
        {"Host": "attacker.example:8770"},
        {"Host": "127.0.0.1.attacker.example:8770"},
        {"Host": "localhost:9999"},
        {"Host": "localhost:8770/path"},
        {"Host": "user@localhost:8770"},
        {"Origin": "https://attacker.example"},
        {"Origin": "null"},
        {"Origin": "http://localhost:9999"},
        {"Origin": "http://localhost:4174/path"},
        {"Sec-Fetch-Site": "cross-site"},
        {"X-Forwarded-For": "127.0.0.1"},
        {"X-Forwarded-Host": "localhost:4174"},
        {"X-Forwarded-Proto": "http"},
        {"Forwarded": "for=127.0.0.1"},
    ],
)
def test_local_mode_rejects_public_cross_site_and_proxy_requests(tmp_path, headers):
    with local_client(create_app(Settings(data_dir=tmp_path))) as client:
        for method, path in [("get", "/api/model/status"), ("post", "/api/missions")]:
            response = getattr(client, method)(path, headers=headers)
            assert response.status_code == 403
            assert response.json() == {"error": "local_access_only"}
            assert response.headers["cache-control"] == "no-store"
    assert list(tmp_path.iterdir()) == []


def test_non_loopback_peer_is_blocked_even_with_local_host_and_origin(tmp_path):
    with TestClient(
        create_app(Settings(data_dir=tmp_path)),
        base_url="http://127.0.0.1:8770",
        client=("192.0.2.1", 50000),
    ) as client:
        assert (
            client.get("/api/model/status", headers={"Origin": "http://localhost:4174"}).status_code
            == 403
        )


@pytest.mark.parametrize("host", ["localhost:4174", "127.0.0.1:5174", "[::1]:4174"])
def test_local_frontend_proxy_hosts_and_origins_are_allowed(tmp_path, host):
    with local_client(create_app(Settings(data_dir=tmp_path))) as client:
        assert (
            client.get(
                "/api/model/status", headers={"Host": host, "Origin": f"http://{host}"}
            ).status_code
            == 200
        )


def test_configured_token_does_not_fall_back_to_local_mode(tmp_path):
    token = "a" * 32
    with local_client(create_app(Settings(access_token=token, data_dir=tmp_path))) as client:
        assert client.get("/api/model/status").status_code == 401
        assert (
            client.get(
                "/api/model/status", headers={"Authorization": f"Bearer {token}"}
            ).status_code
            == 200
        )


def test_personal_owner_is_stable_and_needs_no_environment_setup(monkeypatch):
    monkeypatch.delenv("ONELAP_OWNER_ID", raising=False)
    assert JournalSettings.from_environment().owner_id == PERSONAL_OWNER
    monkeypatch.setenv("ONELAP_OWNER_ID", "")
    assert JournalSettings.from_environment().owner_id == PERSONAL_OWNER
    monkeypatch.setenv("ONELAP_OWNER_ID", "11111111-1111-4111-8111-111111111111")
    assert JournalSettings.from_environment().owner_id != PERSONAL_OWNER
