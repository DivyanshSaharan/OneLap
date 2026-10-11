from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request

from .errors import MissionError
from .journal_models import (
    JournalAck,
    JournalPage,
    JournalStatus,
    JournalUpload,
    identifier,
)
from .tracing import Tracer


def journal_routes(settings, repository, authorize, limiter, tracer: Tracer, resolve_owner):
    router = APIRouter(prefix="/api/journal", dependencies=[Depends(authorize)])

    def require_owner(expected: str, request: Request):
        reason = settings.disabled_reason()
        if reason:
            raise MissionError(reason)
        owner = resolve_owner(request)
        if expected != owner:
            raise MissionError("journal_owner_mismatch", 409)
        limiter.admit()
        return owner

    @router.get("/status")
    def status(request: Request) -> JournalStatus:
        current = settings.status()
        if current.enabled:
            current.owner_id = resolve_owner(request)
        return current

    @router.post("/entries")
    def save(upload: JournalUpload, request: Request) -> JournalAck:
        with tracer.run("journal_save"):
            owner = require_owner(upload.owner_id, request)
            with tracer.span("persist"):
                repository.save(owner, upload.entry)
            return JournalAck(owner_id=owner, id=upload.entry.id, status="stored")

    @router.get("/entries")
    def entries(
        request: Request,
        expected: Annotated[str, Header(alias="X-OneLap-Journal-Owner")],
        after: str | None = None,
    ) -> JournalPage:
        with tracer.run("journal_load"):
            owner = require_owner(expected, request)
            try:
                if after is not None:
                    identifier(after)
            except ValueError:
                raise MissionError("invalid_request", 422) from None
            with tracer.span("load"):
                return repository.page(owner, after)

    @router.delete("/entries/{entry_id}")
    def delete(
        request: Request,
        entry_id: str,
        expected: Annotated[str, Header(alias="X-OneLap-Journal-Owner")],
    ) -> JournalAck:
        with tracer.run("journal_delete"):
            owner = require_owner(expected, request)
            try:
                identifier(entry_id)
            except ValueError:
                raise MissionError("invalid_request", 422) from None
            with tracer.span("delete"):
                repository.delete(owner, entry_id)
            return JournalAck(owner_id=owner, id=entry_id, status="deleted")

    return router
