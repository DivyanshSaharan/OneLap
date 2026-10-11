import base64
import hashlib
import hmac
import json
import math
import re
import secrets
from datetime import UTC, datetime
from time import time
from typing import Annotated
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

from fastapi import APIRouter, Request, Response
from pydantic import StringConstraints

from .errors import MissionError
from .journal_models import identifier
from .models import StrictModel

COOKIE = "onelap_session"
CHALLENGE_COOKIE = "onelap_challenge"
TOKEN = re.compile(r"[a-zA-Z0-9_-]{43}")


class LoginInput(StrictModel):
    credential: Annotated[str, StringConstraints(min_length=1, max_length=6000)]
    csrf: Annotated[str, StringConstraints(min_length=43, max_length=43)]


def verify_google(credential, audience):
    from google.auth.transport.requests import Request as GoogleRequest
    from google.oauth2 import id_token

    class BoundedRequest(GoogleRequest):
        def __call__(self, *args, **kwargs):
            kwargs["timeout"] = 5
            return super().__call__(*args, **kwargs)

    return id_token.verify_oauth2_token(credential, BoundedRequest(), audience)


class Authentication:
    def __init__(self, settings, repository, limiter, verifier=None):
        self.settings = settings
        self.repository = repository
        self.limiter = limiter
        self.verifier = verifier or verify_google

    def origin(self, request, *, mutation=False):
        host = request.headers.get("host", "")
        origins = [item for item in self.settings.origins if urlsplit(item).netloc == host]
        supplied = request.headers.get("origin")
        if (
            not origins
            or request.headers.get("sec-fetch-site") == "cross-site"
            or (supplied is not None and supplied not in origins)
            or (mutation and supplied not in origins)
        ):
            raise MissionError("auth_origin_rejected", 403)
        return origins[0]

    def set_cookie(self, response, request, name, value, max_age):
        response.set_cookie(
            name,
            value,
            max_age=max_age,
            secure=self.origin(request).startswith("https:"),
            httponly=True,
            samesite="strict",
            path="/",
        )

    def signature(self, data):
        return hmac.new(
            self.settings.signing_key.encode(),
            b"OneLap/login-challenge/v1:" + data.encode(),
            hashlib.sha256,
        ).hexdigest()

    def challenge(self, request, response):
        self.origin(request)
        self.limiter.admit()
        payload = {"nonce": secrets.token_urlsafe(32), "csrf": secrets.token_urlsafe(32)}
        data = base64.urlsafe_b64encode(
            json.dumps({**payload, "expires": int(time()) + 300}).encode()
        ).decode()
        self.set_cookie(response, request, CHALLENGE_COOKIE, data + "." + self.signature(data), 300)
        return payload

    def read_challenge(self, request, csrf):
        try:
            value = request.cookies.get(CHALLENGE_COOKIE, "")
            if len(value) > 1024:
                raise ValueError
            data, signature = value.split(".")
            if not secrets.compare_digest(signature, self.signature(data)):
                raise ValueError
            payload = json.loads(base64.urlsafe_b64decode(data))
            if (
                not time() < payload["expires"] <= time() + 300
                or not secrets.compare_digest(payload["csrf"], csrf)
                or not TOKEN.fullmatch(payload["nonce"])
            ):
                raise ValueError
            return payload
        except (ValueError, KeyError, TypeError, UnicodeError):
            raise MissionError("auth_challenge_invalid", 401) from None

    def session(self, request):
        self.origin(request, mutation=request.method not in {"GET", "HEAD"})
        cached = getattr(request.state, "onelap_session", None)
        if cached is not None:
            return cached
        token = request.cookies.get(COOKIE, "")
        if not TOKEN.fullmatch(token):
            raise MissionError("sign_in_required", 401)
        row = self.repository.get(token)
        if not row:
            raise MissionError("sign_in_required", 401)
        try:
            identifier(row["owner"])
            expires = row["expires_at"].replace(tzinfo=UTC)
            if expires <= datetime.now(UTC) or not TOKEN.fullmatch(row["csrf"]):
                raise ValueError
        except (ValueError, KeyError, TypeError, AttributeError):
            raise MissionError("sign_in_required", 401) from None
        if request.method not in {"GET", "HEAD"} and not secrets.compare_digest(
            request.headers.get("x-onelap-csrf", "").encode("utf-8"), row["csrf"].encode("ascii")
        ):
            raise MissionError("auth_csrf_rejected", 403)
        request.state.onelap_session = row
        return row

    def login(self, request, response, body):
        self.origin(request, mutation=True)
        self.limiter.admit()
        challenge = self.read_challenge(request, body.csrf)
        try:
            claims = self.verifier(body.credential, self.settings.client_id)
            if (
                claims.get("aud") != self.settings.client_id
                or claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}
                or type(claims.get("exp")) not in {int, float}
                or not math.isfinite(claims["exp"])
                or claims["exp"] <= time()
                or not isinstance(claims.get("sub"), str)
                or not re.fullmatch(r"[a-zA-Z0-9_-]{1,255}", claims["sub"])
                or not secrets.compare_digest(claims.get("nonce", ""), challenge["nonce"])
            ):
                raise ValueError
        except Exception:
            raise MissionError("google_sign_in_failed", 401) from None
        owner = str(uuid5(NAMESPACE_URL, "https://accounts.google.com/" + claims["sub"]))
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        self.repository.create(
            token, owner, csrf, time() + self.settings.session_seconds, challenge["nonce"]
        )
        old = request.cookies.get(COOKIE, "")
        if TOKEN.fullmatch(old):
            self.repository.delete(old)
        self.set_cookie(response, request, COOKIE, token, self.settings.session_seconds)
        self.set_cookie(response, request, CHALLENGE_COOKIE, "", 0)
        return {
            "enabled": True,
            "client_id": self.settings.client_id,
            "owner_id": owner,
            "csrf": csrf,
        }

    def router(self):
        router = APIRouter(prefix="/api/auth")

        @router.get("/session")
        def status(request: Request):
            if not self.settings.enabled:
                return {"enabled": False, "client_id": None, "owner_id": None, "csrf": None}
            self.origin(request)
            try:
                row = self.session(request)
            except MissionError as error:
                if error.code != "sign_in_required":
                    raise
                row = None
            return {
                "enabled": True,
                "client_id": self.settings.client_id,
                "owner_id": row["owner"] if row else None,
                "csrf": row["csrf"] if row else None,
            }

        @router.get("/challenge")
        def challenge(request: Request, response: Response):
            if not self.settings.enabled:
                raise MissionError("auth_disabled")
            return self.challenge(request, response)

        @router.post("/google")
        def login(request: Request, response: Response, body: LoginInput):
            if not self.settings.enabled:
                raise MissionError("auth_disabled")
            return self.login(request, response, body)

        @router.post("/logout")
        def logout(request: Request, response: Response):
            if not self.settings.enabled:
                raise MissionError("auth_disabled")
            self.session(request)
            self.repository.delete(request.cookies[COOKIE])
            self.set_cookie(response, request, COOKIE, "", 0)
            return {"status": "signed_out"}

        return router
