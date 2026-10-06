import itertools
import json

import pytest
from conftest import plan_for
from onelap.errors import MissionError
from onelap.models import MissionPlan, MissionRequest
from onelap.policy import validate_plan
from onelap.prompts import build_messages
from onelap.provider import parse_plan
from onelap.service import MissionService
from pydantic import ValidationError


@pytest.mark.parametrize(
    "minutes,setting,conditions,focus",
    list(
        itertools.product(
            [10, 15, 20],
            ["courtyard", "park", "familiar_walking_area"],
            ["daylight", "evening"],
            ["light", "textures", "sounds", "general"],
        )
    ),
)
def test_valid_request_combinations(minutes, setting, conditions, focus):
    request = MissionRequest(minutes=minutes, setting=setting, conditions=conditions, focus=focus)
    plan = parse_plan(json.dumps(plan_for(request)))
    validate_plan(plan, request)


@pytest.mark.parametrize(
    "field,value",
    [
        ("minutes", 5),
        ("minutes", 30),
        ("minutes", "15"),
        ("minutes", 15.0),
        ("minutes", True),
        ("setting", "precise-address"),
        ("conditions", "unknown"),
        ("focus", "species_identification"),
        ("latitude", 1),
        ("photo", "private-photo"),
    ],
)
def test_request_rejects_invalid_or_extra_data(request_data, field, value):
    request_data[field] = value
    with pytest.raises(ValidationError):
        MissionRequest(**request_data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("title", ""),
        ("title", "   "),
        ("title", " leading space"),
        ("instruction", "trailing space "),
        ("instruction", "line\nbreak"),
        ("remember", "zero\u200bwidth"),
        ("title", "<script>"),
        ("title", "`code`"),
        ("title", "a" * 81),
        ("instruction", "a" * 281),
        ("remember", "a" * 161),
        ("requires_camera", True),
        ("requires_camera", 0),
        ("phone_use", "record_during_outing"),
        ("extra", "unexpected"),
    ],
)
def test_invalid_model_fields_rejected(mission_request, field, value):
    data = plan_for(mission_request)
    data[field] = value
    with pytest.raises(MissionError, match="invalid_model_output"):
        parse_plan(json.dumps(data))


@pytest.mark.parametrize(
    "text",
    [
        "",
        "not JSON",
        "[]",
        "null",
        "{}",
        "```json\n{}\n```",
        "{} trailing",
        '{"title":"first","title":"second"}',
        "a" * 8193,
    ],
)
def test_malformed_model_output_rejected(text):
    with pytest.raises(MissionError, match="invalid_model_output"):
        parse_plan(text)


@pytest.mark.parametrize("text", [None, 1, {}, b"{}", "[" * 2000 + "]" * 2000])
def test_invalid_runtime_output_is_redacted(text):
    with pytest.raises(MissionError, match="invalid_model_output"):
        parse_plan(text)


@pytest.mark.parametrize(
    "field,value",
    [
        ("minutes", 20),
        ("setting", "park"),
        ("conditions", "daylight"),
        ("focus", "sounds"),
    ],
)
def test_model_cannot_change_constraints(mission_request, field, value):
    data = plan_for(mission_request)
    data[field] = value
    with pytest.raises(MissionError, match="mission_constraint_mismatch"):
        validate_plan(MissionPlan(**data), mission_request)


@pytest.mark.parametrize(
    "instruction",
    [
        "Take a photo of a leaf.",
        "Use your camera.",
        "Record the sound.",
        "Look at the map.",
        "Touch a leaf.",
        "Collect a stone.",
        "Taste a berry.",
        "Feed a bird.",
        "Climb a wall.",
        "Approach strangers.",
        "Pick up a flower.",
        "Cross the road.",
        "Close your eyes while walking.",
        "Open https://example.com.",
    ],
)
def test_conservative_policy_rejections(mission_request, instruction):
    data = plan_for(mission_request)
    data["instruction"] = instruction
    with pytest.raises(MissionError, match="mission_policy_rejected"):
        validate_plan(MissionPlan(**data), mission_request)


def test_prompt_contains_schema_and_only_supplied_context(mission_request):
    messages = build_messages(mission_request)
    assert [message["role"] for message in messages] == ["system", "user"]
    assert "SCHEMA=" in messages[0]["content"]
    assert json.loads(messages[1]["content"]) == mission_request.model_dump()
    assert "There is no location" in messages[0]["content"]


def test_service_returns_actual_identity_and_new_ids(provider_factory, mission_request):
    provider, runtime, _ = provider_factory()
    service = MissionService(provider)
    first = service.generate(mission_request)
    second = service.generate(mission_request)
    assert first.id != second.id
    assert first.generation.target == "base"
    assert first.generation.model == "Qwen/Qwen3.5-4B"
    assert "does not assess safety" in first.safety_note
    assert len(runtime.samples) == 2


def test_rejected_plan_never_returns_a_mission(provider_factory, mission_request):
    data = plan_for(mission_request)
    data["requires_camera"] = True
    provider, _, _ = provider_factory(text=json.dumps(data))
    with pytest.raises(MissionError):
        MissionService(provider).generate(mission_request)
