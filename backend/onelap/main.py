import json
import secrets
from collections import deque
from contextlib import asynccontextmanager
from threading import Lock
from time import monotonic
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .access import local_request
from .budget import BudgetLedger
from .config import ROOT, Settings
from .errors import MissionError
from .journal_config import JournalSettings
from .journal_repository import AtlasJournal
from .journal_routes import journal_routes
from .models import MissionRequest, MissionResponse, ProviderStatus
from .provider import TinkerProvider
from .provider_json import unique_keys
from .service import MissionService

MAX_BODY_BYTES = 8192


class RequestLimiter:
    def __init__(self, maximum=6):
        self.maximum = maximum
        self._times: deque[float] = deque()
        self._lock = Lock()

    def admit(self):
        with self._lock:
            now = monotonic()
            while self._times and self._times[0] <= now - 60:
                self._times.popleft()
            if len(self._times) >= self.maximum:
                raise MissionError("request_rate_limited", 429)
            self._times.append(now)


def create_app(
    settings: Settings | None = None,
    provider: TinkerProvider | None = None,
    journal_settings: JournalSettings | None = None,
    journal: AtlasJournal | None = None,
) -> FastAPI:
    if settings is None:
        load_dotenv(ROOT / ".env", override=False)
        settings = Settings.from_environment()
        journal_settings = journal_settings or JournalSettings.from_environment()
    journal_settings = journal_settings or JournalSettings()
    if journal is not None and journal.settings != journal_settings:
        raise ValueError("Journal and application settings must match")
    journal = journal or AtlasJournal(journal_settings)
    if provider is not None and provider.settings != settings:
        raise ValueError("Provider and application settings must match")
    provider = provider or TinkerProvider(settings, BudgetLedger(settings.data_dir))
    service = MissionService(provider)
    limiter = RequestLimiter()

    @asynccontextmanager
    async def lifespan(_app):
        yield
        journal.close()

    app = FastAPI(
        title="OneLap",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    def authorize(request: Request, authorization: Annotated[str | None, Header()] = None):
        if not settings.access_token:
            if not local_request(request):
                raise MissionError("local_access_only", 403)
            return
        expected = "Bearer " + settings.access_token
        if authorization is None or not secrets.compare_digest(
            authorization.encode("utf-8"), expected.encode("ascii")
        ):
            raise MissionError("unauthorized", 401)

    @app.exception_handler(MissionError)
    async def mission_error(_request: Request, error: MissionError):
        headers = {"WWW-Authenticate": "Bearer"} if error.status_code == 401 else None
        return JSONResponse({"error": error.code}, status_code=error.status_code, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _error: RequestValidationError):
        return JSONResponse({"error": "invalid_request"}, status_code=422)

    @app.middleware("http")
    async def bounded_body(request: Request, call_next):
        if request.method == "POST":
            try:
                authorize(request, request.headers.get("authorization"))
            except MissionError as error:
                return await mission_error(request, error)
            length = request.headers.get("content-length")
            if length is not None and (
                not length.isascii()
                or not length.isdigit()
                or len(length) > 12
                or int(length) > MAX_BODY_BYTES
            ):
                return JSONResponse({"error": "request_too_large"}, status_code=413)
            data = bytearray()
            async for chunk in request.stream():
                if len(data) + len(chunk) > MAX_BODY_BYTES:
                    return JSONResponse({"error": "request_too_large"}, status_code=413)
                data.extend(chunk)
            request._body = bytes(data)
            try:
                json.loads(data, object_pairs_hook=unique_keys)
            except (ValueError, UnicodeError, RecursionError):
                return JSONResponse({"error": "invalid_request"}, status_code=422)
        return await call_next(request)

    @app.middleware("http")
    async def private_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/health")
    def health():
        return {"service": "onelap", "status": "ok"}

    @app.get("/api/model/status", dependencies=[Depends(authorize)])
    def status() -> ProviderStatus:
        return provider.status()

    @app.post("/api/missions", dependencies=[Depends(authorize)], status_code=201)
    def generate(request: MissionRequest) -> MissionResponse:
        limiter.admit()
        return service.generate(request)

    app.include_router(journal_routes(journal_settings, journal, authorize, RequestLimiter(30)))
    return app
