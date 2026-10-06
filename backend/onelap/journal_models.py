import re
import unicodedata
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import StringConstraints, field_validator, model_validator

from .models import GenerationIdentity, MissionPlan, StrictModel

Identifier = Annotated[str, StringConstraints(min_length=36, max_length=36)]
Timestamp = Annotated[str, StringConstraints(min_length=24, max_length=24)]


def identifier(value: str) -> str:
    if str(UUID(value)) != value:
        raise ValueError("Identifier must be a canonical UUID")
    return value


def timestamp(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", value):
        raise ValueError("Timestamp must be UTC with millisecond precision")
    datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


class MissionSnapshot(StrictModel):
    id: Identifier
    mission: MissionPlan
    generation: GenerationIdentity
    safety_note: Annotated[str, StringConstraints(min_length=1, max_length=280)]

    _identifier = field_validator("id")(identifier)
    _plain = field_validator("safety_note")(MissionPlan.plain_text.__func__)


class OutingInput(StrictModel):
    id: Identifier
    mission: MissionSnapshot
    outcome: Literal["completed", "stopped", "skipped"]
    observation: Annotated[str, StringConstraints(max_length=1000)]
    feedback: Literal["useful", "too_difficult", "not_for_me"] | None
    recorded_at: Timestamp

    _identifier = field_validator("id")(identifier)
    _timestamp = field_validator("recorded_at")(timestamp)

    @field_validator("observation")
    @classmethod
    def observation_text(cls, value: str) -> str:
        if value != value.strip():
            raise ValueError("Observation must be trimmed")
        if any(unicodedata.category(char).startswith("C") and char != "\n" for char in value):
            raise ValueError("Control characters are not permitted")
        return value

    @model_validator(mode="after")
    def completed_observation(self):
        if self.outcome == "completed" and not self.observation:
            raise ValueError("Completed outings require an observation")
        return self


class JournalUpload(StrictModel):
    owner_id: Identifier
    entry: OutingInput

    _identifier = field_validator("owner_id")(identifier)


class JournalAck(StrictModel):
    owner_id: Identifier
    id: Identifier
    status: Literal["stored", "deleted"]


class JournalRecord(StrictModel):
    entry: OutingInput
    received_at: Timestamp
    mission_source: Literal["client_submitted"] = "client_submitted"

    _timestamp = field_validator("received_at")(timestamp)


class JournalPage(StrictModel):
    owner_id: Identifier
    entries: list[JournalRecord]
    next_after: Identifier | None


class JournalStatus(StrictModel):
    enabled: bool
    disabled_reason: str | None
    owner_id: Identifier | None
    data_boundary: str = (
        "Explicit sync sends observations, feedback and mission snapshots to MongoDB Atlas. "
        "No journal text is sent to Tinker in this increment."
    )
