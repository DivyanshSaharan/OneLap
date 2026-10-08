from typing import Annotated

from fastapi import APIRouter, Depends, Header

from .errors import MissionError
from .followup import FollowUpService
from .journal_models import FollowUpRequest, FollowUpResponse, FollowUpStatus
from .models import ProviderStatus


def followup_routes(settings, journal_settings, journal, provider, authorize, limiter):
    router = APIRouter(prefix="/api/followups", dependencies=[Depends(authorize)])
    service = FollowUpService(provider)

    def readiness() -> FollowUpStatus:
        journal_reason = journal_settings.disabled_reason()
        if journal_reason:
            return FollowUpStatus(enabled=False, disabled_reason=journal_reason)
        if not settings.reflection_sharing_approved:
            return FollowUpStatus(
                enabled=False,
                disabled_reason="reflection_sharing_not_approved",
            )
        provider_status: ProviderStatus = provider.status()
        if not provider_status.enabled:
            return FollowUpStatus(
                enabled=False,
                disabled_reason=(provider_status.disabled_reason or "provider_unavailable"),
            )
        return FollowUpStatus(enabled=True, disabled_reason=None)

    def require_owner(expected: str) -> str:
        current = readiness()
        if not current.enabled:
            raise MissionError(current.disabled_reason or "provider_unavailable")
        if expected != journal_settings.owner_id:
            raise MissionError("journal_owner_mismatch", 409)
        limiter.admit()
        return journal_settings.owner_id

    @router.get("/status", response_model=FollowUpStatus)
    def status() -> FollowUpStatus:
        return readiness()

    @router.post("", response_model=FollowUpResponse)
    def create(
        request: FollowUpRequest,
        expected: Annotated[str, Header(alias="X-OneLap-Journal-Owner")],
    ) -> FollowUpResponse:
        owner = require_owner(expected)
        ids = [request.source_id, *request.context_ids]
        records = journal.selected(owner, ids)
        source, context = records[0], records[1:]
        if any(
            record.entry.outcome != "completed" or not record.entry.observation
            for record in records
        ):
            raise MissionError("followup_source_needs_observation", 422)
        if any(record.entry.recorded_at >= source.entry.recorded_at for record in context):
            raise MissionError("followup_context_must_precede_source", 422)
        reflection, mission = service.generate(source, context)
        return FollowUpResponse(
            reflection=reflection,
            mission=mission,
            source_ids=ids,
        )

    return router
