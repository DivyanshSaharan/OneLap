import pytest
from fastapi.testclient import TestClient
from onelap.config import Settings
from onelap.main import create_app

ACCESS_TOKEN = "test-deployment-access-token-with-32-chars"


def test_bundled_frontend_is_served_without_exposing_private_api(tmp_path):
    (tmp_path / "index.html").write_text("<main>OneLap bundle</main>", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log('app')", encoding="utf-8")
    app = create_app(
        Settings(
            access_token=ACCESS_TOKEN,
            serve_frontend=True,
            frontend_directory=tmp_path,
        )
    )

    with TestClient(app) as client:
        page = client.get("/")
        asset = client.get("/assets/app.js")
        status = client.get("/api/model/status")
        health = client.get("/health")

    assert page.status_code == 200
    assert "OneLap bundle" in page.text
    assert page.headers["cache-control"] == "no-store"
    assert asset.status_code == 200
    assert asset.text == "console.log('app')"
    assert status.status_code == 401
    assert health.status_code == 200


def test_bundled_frontend_fails_startup_when_build_is_missing(tmp_path):
    missing = tmp_path / "missing-build"

    with pytest.raises(RuntimeError, match="OneLap frontend build is missing"):
        create_app(
            Settings(
                access_token=ACCESS_TOKEN,
                serve_frontend=True,
                frontend_directory=missing,
            )
        )


def test_bundled_frontend_requires_a_server_access_token(tmp_path):
    (tmp_path / "index.html").write_text("OneLap bundle", encoding="utf-8")

    with pytest.raises(RuntimeError, match="OneLap deployments require ONELAP_ACCESS_TOKEN"):
        create_app(Settings(serve_frontend=True, frontend_directory=tmp_path))


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("index.html", "text/html; charset=utf-8"),
        ("sw.js", "text/javascript; charset=utf-8"),
        ("assets/app.js", "text/javascript; charset=utf-8"),
        ("assets/app.css", "text/css; charset=utf-8"),
        ("icon.svg", "image/svg+xml"),
        ("manifest.webmanifest", "application/manifest+json"),
    ],
)
def test_public_mime_types_ignore_incorrect_os_registry(tmp_path, monkeypatch, name, expected):
    monkeypatch.setattr("starlette.responses.guess_type", lambda _path: ("text/plain", None))
    (tmp_path / "assets").mkdir()
    (tmp_path / name).write_text("public fixture", encoding="utf-8")
    app = create_app(
        Settings(
            access_token=ACCESS_TOKEN,
            serve_frontend=True,
            frontend_directory=tmp_path,
        )
    )
    with TestClient(app) as client:
        response = client.get("/" + name)
    assert response.status_code == 200
    assert response.headers["content-type"] == expected
    assert response.headers["x-content-type-options"] == "nosniff"
