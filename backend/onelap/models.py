import unicodedata
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, StringConstraints, field_validator


def exact_integer(value: object) -> object:
    if type(value) is not int:
        raise ValueError("Minutes must be an integer")
    return value


def false_only(value: object) -> object:
    if value is not False:
        raise ValueError("Camera requirement must be the boolean false")
    return value


Minutes = Annotated[Literal[10, 15, 20], BeforeValidator(exact_integer)]
Setting = Literal["courtyard", "park", "familiar_walking_area"]
Conditions = Literal["daylight", "evening"]
Focus = Literal["light", "textures", "sounds", "general"]
ShortText = Annotated[str, StringConstraints(min_length=1, max_length=280)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class MissionRequest(StrictModel):
    minutes: Minutes
    setting: Setting
    conditions: Conditions
    focus: Focus = "general"


class MissionPlan(StrictModel):
    title: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    instruction: ShortText
    remember: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    minutes: Minutes
    setting: Setting
    conditions: Conditions
    focus: Focus
    requires_camera: Annotated[Literal[False], BeforeValidator(false_only)]
    phone_use: Literal["none_during_outing"]

    @field_validator("title", "instruction", "remember")
    @classmethod
    def plain_text(cls, value: str) -> str:
        if value != value.strip() or not value.strip():
            raise ValueError("Text must be nonblank and trimmed")
        if any(unicodedata.category(char).startswith("C") for char in value):
            raise ValueError("Control characters are not permitted")
        if any(char in value for char in "<>`"):
            raise ValueError("Markup is not permitted")
        return value


class GenerationIdentity(StrictModel):
    provider: Literal["tinker"] = "tinker"
    model: Literal["Qwen/Qwen3.5-4B"] = "Qwen/Qwen3.5-4B"
    target: Literal["base"] = "base"
    prompt_version: Literal["mission-v1"] = "mission-v1"


class MissionResponse(StrictModel):
    id: UUID
    mission: MissionPlan
    generation: GenerationIdentity
    safety_note: str = (
        "Stay within a familiar area you choose. Skip or stop if conditions are unsuitable. "
        "This mission does not assess safety or provide navigation."
    )


class ProviderStatus(StrictModel):
    model: str
    target: Literal["base"] = "base"
    enabled: bool
    disabled_reason: str | None
    estimated_reserved_usd: float
    approved_budget_usd: float
    reserved_requests: int
    maximum_requests: int
    data_boundary: str = "Mission inputs go to Tinker. No raw photos or audio are accepted."
