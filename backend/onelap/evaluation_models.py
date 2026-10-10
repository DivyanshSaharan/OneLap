"""Offline evaluation artifacts, not API inputs or training targets."""

from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, StringConstraints, field_validator, model_validator

from .journal_models import Timestamp, timestamp
from .models import MissionPlan, MissionRequest, StrictModel, exact_integer

Label = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9_-]{0,63}$")]
Digest = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
Note = Annotated[str, StringConstraints(min_length=1, max_length=1000)]
Split = Literal["train", "dev", "heldout"]
Score = Annotated[int, Field(strict=True, ge=0, le=2)]
Version = Annotated[Literal[1], BeforeValidator(exact_integer)]


class SeedObservation(StrictModel):
    mission: MissionPlan
    observation: Annotated[str, StringConstraints(min_length=1, max_length=1000)]
    feedback: Literal["useful", "too_difficult", "not_for_me"] | None


class EvaluationCase(StrictModel):
    id: Label
    family: Label
    workflow: Literal["mission", "followup"]
    request: MissionRequest
    source: SeedObservation | None = None
    context: list[SeedObservation] = Field(default_factory=list, max_length=2)
    semantic_checks: list[Note] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def shape(self):
        if self.workflow == "mission" and (self.source is not None or self.context):
            raise ValueError("Initial missions cannot have journal context")
        if self.workflow == "followup":
            if self.source is None:
                raise ValueError("Follow-ups need a source observation")
            selected = self.source.mission.model_dump(include=set(MissionRequest.model_fields))
            if selected != self.request.model_dump():
                raise ValueError("Follow-up selections must match the source")
        return self


class EvaluationDataset(StrictModel):
    version: Version
    name: Label
    provenance: Literal["synthetic_assistant_authored"]
    review_status: Literal["unreviewed", "human_reviewed"]
    reviewer: Label | None
    split_method: Literal["family_before_variants"]
    families: dict[Label, Split]
    cases: list[EvaluationCase] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def separation(self):
        if self.review_status == "human_reviewed" and self.reviewer is None:
            raise ValueError("Human dataset review needs a reviewer label")
        if self.review_status == "unreviewed" and self.reviewer is not None:
            raise ValueError("Unreviewed data cannot name a reviewer")
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("Case IDs must be unique")
        if set(self.families) != {case.family for case in self.cases}:
            raise ValueError("Every family must be assigned exactly one split and have cases")
        fingerprints = [
            case.model_dump_json(exclude={"id", "family", "semantic_checks"}) for case in self.cases
        ]
        if len(set(fingerprints)) != len(fingerprints):
            raise ValueError("Duplicate inputs are not separate evaluation cases")
        return self


class Decoding(StrictModel):
    temperature: Annotated[float, Field(ge=0, le=2, allow_inf_nan=False)]
    max_tokens: Annotated[int, Field(ge=1, le=4096)]
    thinking: bool
    num_samples: Literal[1]
    stop: list[Annotated[str, StringConstraints(min_length=1, max_length=80)]] = Field(
        min_length=1, max_length=5
    )

    @model_validator(mode="before")
    @classmethod
    def exact_sample_count(cls, values):
        if isinstance(values, dict) and type(values.get("num_samples")) is not int:
            raise ValueError("Sample count must be an integer")
        return values


class RunIdentity(StrictModel):
    provider: Literal["tinker"]
    model: Literal["Qwen/Qwen3.5-4B"]
    target: Literal["base", "adapter"]
    checkpoint: Annotated[str, StringConstraints(min_length=1, max_length=200)] | None
    training_dataset_sha256: Digest | None

    @model_validator(mode="after")
    def target_identity(self):
        if self.target == "base" and (
            self.checkpoint is not None or self.training_dataset_sha256 is not None
        ):
            raise ValueError("A base model cannot claim a trained checkpoint")
        if self.target == "adapter" and (
            self.checkpoint is None or self.training_dataset_sha256 is None
        ):
            raise ValueError("An adapter needs its checkpoint and training-data digest")
        if self.checkpoint is not None and (
            not self.checkpoint.startswith("tinker://")
            or any(char.isspace() for char in self.checkpoint)
        ):
            raise ValueError("Use the exact Tinker checkpoint path")
        return self


class HumanReview(StrictModel):
    rubric: Literal["onelap-human-v1"]
    reviewer: Label
    output_sha256: Digest
    grounding: Score
    suitability: Score
    screen_light: Score
    adaptation: Score | None
    rationale: Note


class RunConditions(StrictModel):
    latency_scope: Literal["provider_call_including_setup"]
    client_lifecycle: Literal["shared_client", "cold_each_case"]
    execution: Literal["serial"]
    software_versions: dict[Label, Annotated[str, StringConstraints(min_length=1, max_length=80)]]

    @model_validator(mode="after")
    def required_versions(self):
        if set(self.software_versions) != {"python", "tinker", "transformers"}:
            raise ValueError("Record Python, Tinker and tokenizer-library versions")
        return self


class CapturedResult(StrictModel):
    case_id: Label
    input_sha256: Digest
    raw_output: Annotated[str, StringConstraints(max_length=32768)] | None
    error: Literal["provider_failed", "timeout", "budget_refused", "not_run"] | None
    latency_ms: Annotated[float, Field(ge=0, le=3_600_000, allow_inf_nan=False)] | None
    input_tokens: Annotated[int, Field(ge=0, le=100_000)] | None
    output_tokens: Annotated[int, Field(ge=0, le=100_000)] | None
    estimated_reserved_usd: Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)] | None
    review: HumanReview | None

    @model_validator(mode="after")
    def output_or_failure(self):
        if (self.raw_output is None) == (self.error is None):
            raise ValueError("Each case needs either the raw reply or an explicit failure")
        if self.raw_output is None and self.review is not None:
            raise ValueError("A missing reply cannot have a semantic review")
        return self


class EvaluationRun(StrictModel):
    version: Version
    run_id: Label
    origin: Literal["fixture", "provider_capture"]
    captured_at: Timestamp
    dataset_sha256: Digest
    method_sha256: Digest
    split: Literal["dev", "heldout"]
    identity: RunIdentity
    decoding: Decoding
    conditions: RunConditions
    results: list[CapturedResult] = Field(max_length=500)

    _timestamp = field_validator("captured_at")(timestamp)
