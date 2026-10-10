import json
from dataclasses import replace
from uuid import UUID

import pytest
from conftest import ACCESS_TOKEN, plan_for
from fastapi.testclient import TestClient
from onelap.errors import MissionError
from onelap.followup import FollowUpService, build_messages
from onelap.journal_config import JournalSettings
from onelap.journal_models import (
    JournalRecord,
    MissionSnapshot,
    OutingInput,
)
from onelap.main import create_app
from onelap.models import GenerationIdentity, MissionPlan, MissionRequest

OWNER = "11111111-1111-4111-8111-111111111111"
HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "X-OneLap-Journal-Owner": OWNER,
}
JOURNAL_SETTINGS = JournalSettings(
    enabled=True,
    sharing_approved=True,
    owner_id=OWNER,
    uri="mongodb+srv://fictional:private-test-password@fictional.mongodb.net/",
)


class TextProvider:
    def __init__(self, text):
        self.text = text
        self.messages = None

    def sample_text(self, messages):
        self.messages = messages
        return self.text


class SelectedJournal:
    def __init__(self, records):
        self.settings = JOURNAL_SETTINGS
        self.records = {row.entry.id: row for row in records}
        self.selections = []

    def selected(self, owner, entry_ids):
        self.selections.append((owner, entry_ids))
        if owner != self.settings.owner_id or any(
            entry_id not in self.records for entry_id in entry_ids
        ):
            raise MissionError("journal_source_not_found", 404)
        return [self.records[entry_id] for entry_id in entry_ids]

    def close(self):
        pass


def record(entry):
    return JournalRecord(entry=entry, received_at=entry.recorded_at)


@pytest.fixture
def entry(mission_request):
    return OutingInput(
        id=str(UUID(int=100)),
        mission=MissionSnapshot(
            id=str(UUID(int=1)),
            mission=MissionPlan(**plan_for(mission_request)),
            generation=GenerationIdentity(),
            safety_note="Skip if unsuitable.",
        ),
        outcome="completed",
        observation="I noticed a soft shadow on a rough surface.",
        feedback="useful",
        recorded_at="2026-10-06T14:00:00.000Z",
    )


def followup_output(mission_request):
    plan = plan_for(mission_request)
    plan["title"] = "Notice a quiet detail"
    plan["instruction"] = "From where you are, notice one small texture shift nearby."
    return {"reflection": "You noticed a contrast in texture.", "mission": plan}


def test_prompt_contains_only_selected_note_fields(entry):
    source = record(entry)
    context = record(
        entry.model_copy(
            update={
                "id": str(UUID(int=101)),
                "observation": "A different surface felt smoother.",
                "recorded_at": "2026-10-05T14:00:00.000Z",
            }
        )
    )

    messages = build_messages(source, [context])
    payload = json.loads(messages[1]["content"])
    assert [message["role"] for message in messages] == ["system", "user"]
    assert payload["selected_observation"]["observation"] == entry.observation
    assert payload["optional_previous_context"][0]["observation"] == (
        "A different surface felt smoother."
    )
    assert "id" not in payload["selected_observation"]
    assert "recorded_at" not in payload["selected_observation"]
    assert "id" not in payload["optional_previous_context"][0]


def test_service_preserves_source_constraints_and_marks_followup(entry, request_data):
    source = record(entry)
    provider = TextProvider(json.dumps(followup_output(MissionRequest(**request_data))))

    reflection, response = FollowUpService(provider).generate(source, [])

    assert reflection == "You noticed a contrast in texture."
    assert response.generation.prompt_version == "follow-up-v2"
    assert response.mission.minutes == source.entry.mission.mission.minutes
    assert response.mission.setting == source.entry.mission.mission.setting
    assert response.mission.conditions == source.entry.mission.mission.conditions
    assert response.mission.focus == source.entry.mission.mission.focus
    assert provider.messages is not None


@pytest.mark.parametrize("focus", ["textures", "light", "sounds", "general"])
def test_followup_prompt_schema_locks_all_selected_constraints(entry, focus):
    source = record(entry)
    source.entry.mission.mission.focus = focus
    payload = json.loads(build_messages(source, [])[1]["content"])
    required = {
        "minutes": source.entry.mission.mission.minutes,
        "setting": source.entry.mission.mission.setting,
        "conditions": source.entry.mission.mission.conditions,
        "focus": focus,
    }

    assert payload["required_next_mission_constraints"] == required
    properties = payload["required_response_schema"]["$defs"]["MissionPlan"]["properties"]
    for name, value in required.items():
        assert properties[name]["const"] == value
        assert "enum" not in properties[name]


def test_service_keeps_rejecting_the_focus_drift_observed_live(entry, request_data):
    output = followup_output(MissionRequest(**request_data))
    output["mission"]["focus"] = "light"
    provider = TextProvider(json.dumps(output))

    with pytest.raises(MissionError, match="mission_constraint_mismatch"):
        FollowUpService(provider).generate(record(entry), [])


def test_service_rejects_repeated_instruction(entry, request_data):
    repeated = plan_for(MissionRequest(**request_data))
    provider = TextProvider(json.dumps({"reflection": "A reflection.", "mission": repeated}))

    with pytest.raises(MissionError, match="followup_repeated_mission"):
        FollowUpService(provider).generate(record(entry), [])


def test_service_rejects_malformed_output(entry):
    with pytest.raises(MissionError, match="invalid_model_output"):
        FollowUpService(TextProvider("not JSON")).generate(record(entry), [])


def test_api_keeps_followup_disabled_without_reflection_approval(
    tmp_path, settings, provider_factory, entry
):
    provider, runtime, _ = provider_factory()
    journal = SelectedJournal([record(entry)])
    app = create_app(
        settings,
        provider=provider,
        journal_settings=JOURNAL_SETTINGS,
        journal=journal,
    )

    with TestClient(app) as client:
        status = client.get("/api/followups/status", headers=HEADERS)
        response = client.post(
            "/api/followups",
            headers=HEADERS,
            json={"source_id": entry.id, "context_ids": []},
        )

    assert status.json()["disabled_reason"] == "reflection_sharing_not_approved"
    assert response.json() == {"error": "reflection_sharing_not_approved"}
    assert journal.selections == []
    assert runtime.samples == []


def test_api_reloads_selected_owner_records_before_sampling(
    tmp_path, settings, provider_factory, entry, request_data
):
    changes = {"reflection_sharing_approved": True}
    approved_settings = replace(settings, **changes)
    output = followup_output(MissionRequest(**request_data))
    provider, runtime, _ = provider_factory(changes=changes, text=json.dumps(output))
    journal = SelectedJournal([record(entry)])
    app = create_app(
        approved_settings,
        provider=provider,
        journal_settings=JOURNAL_SETTINGS,
        journal=journal,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/followups",
            headers=HEADERS,
            json={"source_id": entry.id, "context_ids": []},
        )

    assert response.status_code == 200, response.text
    assert response.json()["source_ids"] == [entry.id]
    assert response.json()["mission"]["generation"]["prompt_version"] == "follow-up-v2"
    assert journal.selections == [(OWNER, [entry.id])]
    assert len(runtime.samples) == 1


def test_api_rejects_later_context_before_spending(tmp_path, settings, provider_factory, entry):
    changes = {"reflection_sharing_approved": True}
    provider, runtime, _ = provider_factory(changes=changes)
    later = record(
        entry.model_copy(
            update={
                "id": str(UUID(int=102)),
                "recorded_at": "2026-10-07T14:00:00.000Z",
            }
        )
    )
    journal = SelectedJournal([record(entry), later])
    app = create_app(
        replace(settings, **changes),
        provider=provider,
        journal_settings=JOURNAL_SETTINGS,
        journal=journal,
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/followups",
            headers=HEADERS,
            json={"source_id": entry.id, "context_ids": [later.entry.id]},
        )

    assert response.json() == {"error": "followup_context_must_precede_source"}
    assert runtime.samples == []
