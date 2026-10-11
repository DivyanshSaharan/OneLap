import base64
import json
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from time import time
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5

import pytest
from conftest import ACCESS_TOKEN
from fastapi.testclient import TestClient
from onelap.auth import CHALLENGE_COOKIE, COOKIE, verify_google
from onelap.auth_config import AuthSettings
from onelap.auth_repository import AtlasSessions, digest
from onelap.config import Settings
from onelap.main import create_app
from pymongo.errors import DuplicateKeyError
from test_journal import CONFIG, Collection
from test_journal import entry as entry

ORIGIN = "http://localhost:4174"
AUTH = AuthSettings(
    client_id="fictional.apps.googleusercontent.com",
    signing_key="fictional-server-only-signing-key-000000",
)


class SessionsCollection:
    def __init__(self):
        self.documents = {}
        self.indexes = []
        self.failure = False

    def create_index(self, key, **options):
        self.indexes.append((key, options))

    def insert_one(self, row):
        if self.failure:
            raise RuntimeError("PRIVATE URI")
        if row["_id"] in self.documents:
            raise DuplicateKeyError("duplicate")
        self.documents[row["_id"]] = deepcopy(row)

    def find_one(self, query):
        if self.failure:
            raise RuntimeError("PRIVATE URI")
        row = self.documents.get(query["_id"])
        if row and row["expires_at"] > query["expires_at"]["$gt"]:
            return deepcopy(row)
        return None

    def delete_one(self, query):
        if self.failure:
            raise RuntimeError("PRIVATE URI")
        self.documents.pop(query["_id"], None)


class Client:
    def __init__(self, collection):
        self.collection = collection
        self.closed = False

    def __getitem__(self, database):
        assert database == CONFIG.database
        return self

    def get_collection(self, name, **options):
        assert name in {"outings", "auth_sessions"}
        assert str(options["read_preference"]) == "Primary()"
        return self.collection

    def close(self):
        self.closed = True


@pytest.fixture
def environment(tmp_path):
    sessions_collection = SessionsCollection()
    journal_collection = Collection()

    def factory(collection):
        def build(_uri, **options):
            assert options["tls"] and options["w"] == "majority"
            assert not options["retryWrites"] and not options["retryReads"]
            assert not options["tlsAllowInvalidCertificates"]
            return Client(collection)

        return build

    def app(provider=None, auth=AUTH, verifier=None):
        from onelap.journal_repository import AtlasJournal

        return create_app(
            provider.settings
            if provider
            else Settings(data_dir=tmp_path, access_token=ACCESS_TOKEN),
            provider=provider,
            journal_settings=CONFIG,
            journal=AtlasJournal(CONFIG, client_factory=factory(journal_collection)),
            auth_settings=auth,
            sessions=AtlasSessions(CONFIG, client_factory=factory(sessions_collection)),
            google_verifier=verifier or (lambda credential, _audience: json.loads(credential)),
        )

    return SimpleNamespace(app=app, sessions=sessions_collection, journal=journal_collection)


def claims(challenge_nonce, subject="person-a", **updates):
    return {
        "iss": "https://accounts.google.com",
        "aud": AUTH.client_id,
        "exp": int(time()) + 3600,
        "iat": int(time()) - 1,
        "sub": subject,
        "nonce": challenge_nonce,
        **updates,
    }


def sign_in(client, subject="person-a", **updates):
    challenge = client.get("/api/auth/challenge").json()
    response = client.post(
        "/api/auth/google",
        headers={"Origin": ORIGIN},
        json={
            "credential": json.dumps(claims(challenge["nonce"], subject, **updates)),
            "csrf": challenge["csrf"],
        },
    )
    return response


def headers(session, owner=None):
    return {
        "Origin": ORIGIN,
        "X-OneLap-CSRF": session["csrf"],
        "X-OneLap-Journal-Owner": owner or session["owner_id"],
    }


def test_disabled_auth_does_not_read_atlas_or_replace_legacy_access(tmp_path):
    with TestClient(create_app(Settings(data_dir=tmp_path))) as client:
        assert client.get("/api/auth/session").json() == {
            "enabled": False,
            "client_id": None,
            "owner_id": None,
            "csrf": None,
        }
        assert (
            client.post(
                "/api/auth/google", json={"credential": "fictional", "csrf": "a" * 43}
            ).status_code
            == 503
        )
    assert list(tmp_path.iterdir()) == []


def test_sign_in_uses_sub_not_email_and_keeps_tokens_private(environment):
    with TestClient(environment.app(), base_url=ORIGIN) as client:
        assert client.get("/api/auth/session").json()["owner_id"] is None
        assert environment.sessions.documents == {}
        response = sign_in(client, email="first@example.invalid", name="PRIVATE_NAME")
        assert response.status_code == 200
        expected = str(uuid5(NAMESPACE_URL, "https://accounts.google.com/person-a"))
        assert response.json()["owner_id"] == expected
        token = client.cookies[COOKIE]
        row = environment.sessions.documents[digest(token)]
        assert row["owner"] == expected
        assert token not in str(environment.sessions.documents)
        assert "PRIVATE_NAME" not in response.text + str(environment.sessions.documents)
        assert "example.invalid" not in response.text + str(environment.sessions.documents)
        assert AUTH.signing_key not in response.text
        assert "HttpOnly" in response.headers["set-cookie"]
        assert "SameSite=strict" in response.headers["set-cookie"]
        assert response.headers["cache-control"] == "no-store"
        assert sign_in(client, email="changed@example.invalid").json()["owner_id"] == expected
        assert digest(token) not in environment.sessions.documents


@pytest.mark.parametrize(
    "updates",
    [
        {"aud": "other.apps.googleusercontent.com"},
        {"iss": "https://attacker.invalid"},
        {"exp": int(time()) - 3600},
        {"nonce": "wrong"},
        {"sub": ""},
        {"sub": []},
        {"exp": True},
        {"exp": float("nan")},
    ],
)
def test_bad_claims_never_create_session(environment, updates):
    with TestClient(environment.app(), base_url=ORIGIN) as client:
        response = sign_in(client, **updates)
        assert response.status_code == 401
        assert response.json() == {"error": "google_sign_in_failed"}
        assert environment.sessions.documents == {}


@pytest.mark.parametrize(
    "origin", [None, "null", "https://attacker.invalid", "http://localhost:5174"]
)
def test_login_requires_same_exact_allowed_origin(environment, origin):
    with TestClient(environment.app(), base_url=ORIGIN) as client:
        challenge = client.get("/api/auth/challenge").json()
        response = client.post(
            "/api/auth/google",
            headers={"Origin": origin} if origin else {},
            json={"credential": "fictional", "csrf": challenge["csrf"]},
        )
        assert response.status_code == 403
        assert environment.sessions.documents == {}


def test_host_and_cross_site_headers_are_checked(environment):
    with TestClient(environment.app(), base_url=ORIGIN) as client:
        assert client.get("/api/auth/session", headers={"Host": "evil.invalid"}).status_code == 403
        assert (
            client.get("/api/auth/session", headers={"Sec-Fetch-Site": "cross-site"}).status_code
            == 403
        )


def test_challenge_tamper_missing_csrf_and_replay_are_rejected(environment):
    with TestClient(environment.app(), base_url=ORIGIN) as client:
        challenge = client.get("/api/auth/challenge").json()
        original = client.cookies[CHALLENGE_COOKIE]
        body = {"credential": json.dumps(claims(challenge["nonce"])), "csrf": "a" * 43}
        assert (
            client.post("/api/auth/google", headers={"Origin": ORIGIN}, json=body).status_code
            == 401
        )
        body["csrf"] = challenge["csrf"]
        client.cookies.clear()
        client.cookies.set(CHALLENGE_COOKIE, original + "tampered")
        assert (
            client.post("/api/auth/google", headers={"Origin": ORIGIN}, json=body).status_code
            == 401
        )
        client.cookies.clear()
        client.cookies.set(CHALLENGE_COOKIE, original)
        assert (
            client.post("/api/auth/google", headers={"Origin": ORIGIN}, json=body).status_code
            == 200
        )
        client.cookies.clear()
        client.cookies.set(CHALLENGE_COOKIE, original)
        assert client.post("/api/auth/google", headers={"Origin": ORIGIN}, json=body).json() == {
            "error": "auth_challenge_used"
        }


def test_session_survives_server_restart_and_logout_revokes_replay(environment):
    with TestClient(environment.app(), base_url=ORIGIN) as client:
        session = sign_in(client).json()
        token = client.cookies[COOKIE]
    with TestClient(environment.app(), base_url=ORIGIN) as client:
        client.cookies.set(COOKIE, token)
        assert client.get("/api/auth/session").json() == session
        assert client.post("/api/auth/logout", headers=headers(session), json={}).status_code == 200
        client.cookies.set(COOKIE, token)
        assert client.get("/api/model/status").status_code == 401
        assert client.get("/api/auth/session").json()["owner_id"] is None


def test_expired_cookie_and_storage_outage_fail_closed(environment):
    with TestClient(environment.app(), base_url=ORIGIN) as client:
        sign_in(client)
        token = client.cookies[COOKIE]
        environment.sessions.failure = True
        response = client.get("/api/model/status")
        assert response.status_code == 503
        assert response.json() == {"error": "auth_storage_unavailable"}
        assert "PRIVATE" not in response.text
        environment.sessions.failure = False
        environment.sessions.documents[digest(token)]["expires_at"] = datetime.now(UTC) - timedelta(
            seconds=1
        )
        assert client.get("/api/model/status").status_code == 401


def test_legacy_bearer_cannot_bypass_google_and_no_model_is_sampled(
    environment, provider_factory, request_data
):
    provider, runtime, creations = provider_factory()
    with TestClient(environment.app(provider), base_url=ORIGIN) as client:
        response = client.post(
            "/api/missions",
            json=request_data,
            headers={"Origin": ORIGIN, "Authorization": f"Bearer {ACCESS_TOKEN}"},
        )
        assert response.status_code == 401
    assert runtime.samples == creations == []


def test_cookie_mutations_require_csrf_and_do_not_reach_model(
    environment, provider_factory, request_data
):
    provider, runtime, creations = provider_factory()
    with TestClient(environment.app(provider), base_url=ORIGIN) as client:
        session = sign_in(client).json()
        for bad in [{}, {"Origin": ORIGIN}, {"Origin": ORIGIN, "X-OneLap-CSRF": "wrong"}]:
            assert client.post("/api/missions", json=request_data, headers=bad).status_code == 403
        assert (
            client.post("/api/auth/logout", headers={"Origin": ORIGIN}, json={}).status_code == 403
        )
        assert client.get("/api/auth/session").json() == session
    assert runtime.samples == creations == []


def test_two_accounts_cannot_read_write_delete_or_use_other_history(
    environment, entry, provider_factory
):
    provider, runtime, creations = provider_factory(changes={"reflection_sharing_approved": True})
    with TestClient(environment.app(provider), base_url=ORIGIN) as client:
        a = sign_in(client).json()
        assert a["owner_id"] != CONFIG.owner_id
        upload = {"owner_id": a["owner_id"], "entry": entry.model_dump()}
        assert (
            client.post("/api/journal/entries", headers=headers(a), json=upload).status_code == 200
        )
        b = sign_in(client, "person-b").json()
        assert client.get("/api/journal/status").json()["owner_id"] == b["owner_id"]
        assert client.get("/api/journal/entries", headers=headers(b)).json()["entries"] == []
        assert (
            client.get("/api/journal/entries", headers=headers(b, a["owner_id"])).status_code == 409
        )
        assert (
            client.post("/api/journal/entries", headers=headers(b), json=upload).status_code == 409
        )
        assert (
            client.delete(
                f"/api/journal/entries/{entry.id}", headers=headers(b, a["owner_id"])
            ).status_code
            == 409
        )
        assert (
            client.post(
                "/api/followups",
                headers=headers(b),
                json={"source_id": entry.id, "context_ids": []},
            ).status_code
            == 404
        )
        a_again = sign_in(client).json()
        assert a_again["owner_id"] == a["owner_id"]
        assert (
            len(client.get("/api/journal/entries", headers=headers(a_again)).json()["entries"]) == 1
        )
        assert len(environment.journal.documents) == 1
    assert runtime.samples == creations == []


def test_https_cookie_secure_and_signing_key_never_returned(environment):
    secure_origin = "https://fictional.onrender.com"
    auth = replace(AUTH, origins=(secure_origin,))
    with TestClient(environment.app(auth=auth), base_url=secure_origin) as client:
        response = client.get("/api/auth/challenge")
        assert "Secure" in response.headers["set-cookie"]
        assert AUTH.signing_key not in response.text


def test_bundled_google_app_does_not_require_a_legacy_token(tmp_path):
    (tmp_path / "index.html").write_text("OneLap auth fixture", encoding="utf-8")
    app = create_app(
        Settings(serve_frontend=True, frontend_directory=tmp_path),
        auth_settings=AUTH,
    )
    with TestClient(app, base_url=ORIGIN) as client:
        assert client.get("/").status_code == 200
        assert client.get("/api/model/status").json() == {"error": "sign_in_required"}
        assert client.get("/").headers["referrer-policy"] == "no-referrer-when-downgrade"


def test_expired_challenge_and_oversized_login_never_create_a_session(environment, monkeypatch):
    with TestClient(environment.app(), base_url=ORIGIN) as client:
        challenge = client.get("/api/auth/challenge").json()
        current = time()
        monkeypatch.setattr("onelap.auth.time", lambda: current + 301)
        response = client.post(
            "/api/auth/google",
            headers={"Origin": ORIGIN},
            json={"credential": "fictional", "csrf": challenge["csrf"]},
        )
        assert response.json() == {"error": "auth_challenge_invalid"}
        assert (
            client.post(
                "/api/auth/google", headers={"Origin": ORIGIN}, content=b"a" * 8193
            ).status_code
            == 413
        )
        assert environment.sessions.documents == {}


@pytest.mark.parametrize(
    "origin",
    [
        "http://example.invalid",
        "https://example.invalid/",
        "https://user:pw@example.invalid",
        "*",
        "https://*.example.invalid",
    ],
)
def test_bad_origin_config_is_rejected(origin):
    with pytest.raises(ValueError):
        replace(AUTH, origins=(origin,))


def test_google_library_really_checks_rsa_signature_audience_issuer_and_expiry(monkeypatch):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from google.auth.exceptions import GoogleAuthError
    from google.auth.transport.requests import Request

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    monkeypatch.setattr(
        Request,
        "__call__",
        lambda *args, **kwargs: SimpleNamespace(
            status=200, data=json.dumps({"fictional-key": public}).encode()
        ),
    )

    def encoded(value):
        return base64.urlsafe_b64encode(value).rstrip(b"=")

    def token(payload):
        message = (
            encoded(json.dumps({"alg": "RS256", "kid": "fictional-key"}).encode())
            + b"."
            + encoded(json.dumps(payload).encode())
        )
        signature = key.sign(message, padding.PKCS1v15(), hashes.SHA256())
        return (message + b"." + encoded(signature)).decode()

    payload = claims("nonce")
    signed = token(payload)
    assert verify_google(signed, AUTH.client_id)["sub"] == "person-a"
    for updates in [{"aud": "wrong"}, {"iss": "wrong"}, {"exp": int(time()) - 3600}]:
        with pytest.raises((ValueError, GoogleAuthError)):
            verify_google(token({**payload, **updates}), AUTH.client_id)
    pieces = signed.split(".")
    pieces[2] = ("B" if pieces[2][0] == "A" else "A") + pieces[2][1:]
    with pytest.raises(ValueError):
        verify_google(".".join(pieces), AUTH.client_id)
