from typing import Annotated

from fastapi import APIRouter, Depends, Header

from .errors import MissionError
from .journal_models import (
    JournalAck,
    JournalPage,
    JournalStatus,
    JournalUpload,
    identifier,
)


def journal_routes(settings, repository, authorize, limiter):
    router = APIRouter(prefix="/api/journal", dependencies=[Depends(authorize)])

    def require_owner(expected: str):
        reason = settings.disabled_reason()
        if reason:
            raise MissionError(reason)
        if expected != settings.owner_id:
            raise MissionError("journal_owner_mismatch", 409)
        limiter.admit()
        return settings.owner_id

    @router.get("/status")
    def status() -> JournalStatus:
        return settings.status()

    @router.post("/entries")
    def save(upload: JournalUpload) -> JournalAck:
        owner = require_owner(upload.owner_id)
        repository.save(owner, upload.entry)
        return JournalAck(owner_id=owner, id=upload.entry.id, status="stored")

    @router.get("/entries")
    def entries(
        expected: Annotated[str, Header(alias="X-OneLap-Journal-Owner")],
        after: str | None = None,
    ) -> JournalPage:
        owner = require_owner(expected)
        try:
            if after is not None:
                identifier(after)
        except ValueError:
            raise MissionError("invalid_request", 422) from None
        return repository.page(owner, after)

    @router.delete("/entries/{entry_id}")
    def delete(
        entry_id: str,
        expected: Annotated[str, Header(alias="X-OneLap-Journal-Owner")],
    ) -> JournalAck:
        owner = require_owner(expected)
        try:
            identifier(entry_id)
        except ValueError:
            raise MissionError("invalid_request", 422) from None
        repository.delete(owner, entry_id)
        return JournalAck(owner_id=owner, id=entry_id, status="deleted")

    return router
