import json
from dataclasses import replace

import pytest
from conftest import FakeRuntime, plan_for
from fastapi.testclient import TestClient
from onelap import smoke
from onelap.config import Settings
from onelap.journal_config import JournalSettings
from onelap.journal_repository import AtlasJournal
from onelap.main import create_app
from onelap.models import MissionResponse
from onelap.smoke_workflow import OBSERVATION, REQUEST, run_workflow
from test_journal import CONFIG, Collection


def offline_journal(config, collection):
    class Client:
        def __getitem__(self, _name):
            return self

        def get_collection(self, _name, **_options):
            return collection

        def close(self):
            pass

    return AtlasJournal(config, client_factory=lambda *_args, **_kwargs: Client())


@pytest.fixture
def scenario(provider_factory):
    provider, runtime, _ = provider_factory(
        changes={"reflection_sharing_approved": True, "access_token": ""}
    )
    next_mission = {
        **plan_for(REQUEST),
        "title": "One texture at a time",
        "instruction": (
            "If a surface catches your attention, notice one texture from a comfortable spot."
        ),
    }
    outputs = iter(
        [
            json.dumps(plan_for(REQUEST)),
            json.dumps(
                {
                    "reflection": (
                        "You noticed rough and smooth textures; next time, focus on just one."
                    ),
                    "mission": next_mission,
                }
            ),
        ]
    )

    def sample(tokens):
        runtime.samples.append(tokens)
        return next(outputs)

    runtime.sample = sample
    collection = Collection()
    journal = offline_journal(CONFIG, collection)
    return provider, runtime, journal, collection


def workflow_client(provider, journal):
    return TestClient(
        create_app(provider.settings, provider, CONFIG, journal),
        base_url="http://127.0.0.1:8770",
        client=("127.0.0.1", 50000),
    )


def test_preflight_never_creates_clients_or_files_and_does_not_print_secrets(tmp_path):
    settings = Settings(api_key="PRIVATE TINKER KEY", data_dir=tmp_path / "nonexistent")
    journal = replace(CONFIG, enabled=False, sharing_approved=False)
    report = smoke.preflight(settings, journal, available=lambda _name: None)

    assert not report["ready"]
    assert "hosted_requests_disabled" in report["blockers"]
    assert "smoke_dependencies_missing" in report["blockers"]
    assert "PRIVATE TINKER KEY" not in json.dumps(report)
    assert journal.uri not in json.dumps(report)
    assert not settings.data_dir.exists()


def test_preflight_accepts_only_enough_existing_budget_and_request_allowance(settings):
    settings = replace(settings, reflection_sharing_approved=True)

    def available(_name):
        return object()

    assert smoke.preflight(settings, CONFIG, available=available)["ready"]
    small_budget = replace(settings, budget_microdollars=1, max_model_requests=1)
    report = smoke.preflight(small_budget, CONFIG, available=available)

    assert "insufficient_smoke_budget" in report["blockers"]
    assert "insufficient_smoke_request_allowance" in report["blockers"]


def test_preflight_fails_closed_on_an_invalid_spending_ledger(settings):
    (settings.data_dir / "inference-budget.json").write_text("invalid", encoding="utf-8")
    report = smoke.preflight(settings, CONFIG, available=lambda _name: object())

    assert not report["ready"]
    assert "budget_ledger_unavailable" in report["blockers"]


def test_complete_api_flow_is_idempotent_and_leaves_only_a_tombstone(scenario):
    provider, runtime, journal, collection = scenario
    with workflow_client(provider, journal) as client:
        report = run_workflow(client, CONFIG.owner_id, mode="offline_test")

    assert report["status"] == "passed"
    assert report["mode"] == "offline_test"
    assert report["synthetic"] is True
    assert report["semantic_review"] == "pending_human_review"
    assert report["cleanup"] == "verified"
    assert len(runtime.samples) == 2
    assert len(report["steps"]) == 7
    assert all(step["status"] == "passed" for step in report["steps"])
    assert len(collection.documents) == 1
    document = next(iter(collection.documents.values()))
    assert set(document) == {"_id", "owner_id", "deleted"}
    assert document["deleted"] is True
    assert provider.ledger.snapshot()["reserved_requests"] == 2


def test_invalid_followup_is_reported_and_stored_text_is_still_deleted(scenario):
    provider, runtime, journal, collection = scenario
    original_sample = runtime.sample

    def sample(tokens):
        if runtime.samples:
            runtime.samples.append(tokens)
            return "not valid model JSON"
        return original_sample(tokens)

    runtime.sample = sample
    with workflow_client(provider, journal) as client:
        report = run_workflow(client, CONFIG.owner_id, mode="offline_test")

    assert report["status"] == "failed"
    assert report["error"] == "invalid_model_output"
    assert report["cleanup"] == "verified"
    assert next(iter(collection.documents.values()))["deleted"] is True
    assert len(runtime.samples) == 2
    assert report["steps"][-2]["status"] == "failed"


def test_failed_first_generation_never_writes_to_atlas(scenario):
    provider, runtime, journal, collection = scenario
    runtime.sample = lambda _tokens: "invalid JSON"
    with workflow_client(provider, journal) as client:
        report = run_workflow(client, CONFIG.owner_id, mode="offline_test")

    assert report["status"] == "failed"
    assert report["error"] == "invalid_model_output"
    assert report["steps"][0]["status"] == "failed"
    assert report["cleanup"] == "not_needed"
    assert collection.documents == {}


def test_lost_upload_reply_still_cleans_up_the_attempted_entry(scenario, monkeypatch):
    provider, _runtime, journal, collection = scenario
    with workflow_client(provider, journal) as client:
        original_post = client.post
        interrupted = False

        def lose_first_ack(path, **kwargs):
            nonlocal interrupted
            response = original_post(path, **kwargs)
            if path == "/api/journal/entries" and not interrupted:
                interrupted = True
                raise RuntimeError("PRIVATE TRANSPORT DETAIL")
            return response

        monkeypatch.setattr(client, "post", lose_first_ack)
        report = run_workflow(client, CONFIG.owner_id, mode="offline_test")

    assert report["status"] == "failed"
    assert report["cleanup"] == "verified"
    assert next(iter(collection.documents.values()))["deleted"] is True
    assert "PRIVATE TRANSPORT DETAIL" not in json.dumps(report)


def test_cleanup_failure_cannot_be_reported_as_a_success(scenario, monkeypatch):
    provider, _runtime, journal, collection = scenario

    def fail(*_args, **_kwargs):
        raise RuntimeError("PRIVATE DATABASE PASSWORD")

    monkeypatch.setattr(collection, "replace_one", fail)
    with workflow_client(provider, journal) as client:
        report = run_workflow(client, CONFIG.owner_id, mode="offline_test")

    assert report["status"] == "failed"
    assert report["cleanup"] == "failed"
    assert report["cleanup_error"] == "journal_unavailable"
    assert "PRIVATE DATABASE PASSWORD" not in json.dumps(report)


def test_live_run_uses_a_fresh_owner_and_the_existing_spending_ledger(scenario, monkeypatch):
    provider, _runtime, _journal, collection = scenario
    configurations = []
    personal_document = {
        "_id": "personal",
        "owner_id": CONFIG.owner_id,
        "deleted": False,
        "record": {"observation": "PRIVATE PERSONAL OBSERVATION"},
    }
    collection.documents["personal"] = personal_document.copy()

    def factory(config):
        configurations.append(config)
        return offline_journal(config, collection)

    monkeypatch.setattr("onelap.provider.TinkerProvider", lambda *_args, **_kwargs: provider)
    monkeypatch.setattr("onelap.journal_repository.AtlasJournal", factory)
    report = smoke.live_run(provider.settings, CONFIG)

    assert report["status"] == "passed"
    assert configurations[0].owner_id != CONFIG.owner_id
    assert report["test_owner_id"] == configurations[0].owner_id
    assert report["reserved_model_requests_in_run"] == 2
    assert report["estimated_reserved_usd_in_run"] > 0
    assert provider.ledger.snapshot()["reserved_requests"] == 2
    assert collection.documents["personal"] == personal_document
    assert "PRIVATE PERSONAL OBSERVATION" not in json.dumps(report)


def test_invalid_synthetic_reply_is_captured_before_validation_without_retrying():
    runtime = FakeRuntime("malformed synthetic response")
    outputs = []
    captured = smoke.CapturedRuntime(runtime, outputs)
    messages = [{"role": "user", "content": "fictional test"}]
    tokens = captured.encode(messages)

    assert captured.sample(tokens) == "malformed synthetic response"
    assert outputs == [
        {
            "sample_index": 1,
            "text": "malformed synthetic response",
            "truncated_in_report": False,
        }
    ]
    assert len(runtime.samples) == 1
    assert runtime.encodings == [messages]


def test_resumed_flow_uses_only_one_more_model_request(scenario):
    provider, runtime, journal, _collection = scenario
    with workflow_client(provider, journal) as client:
        first = client.post("/api/missions", json=REQUEST.model_dump())
        mission = MissionResponse.model_validate_json(first.text)
        before = provider.ledger.snapshot()["reserved_requests"]
        report = run_workflow(client, CONFIG.owner_id, mode="offline_test", source_mission=mission)

    assert report["status"] == "passed"
    assert report["steps"][0]["name"] == "reuse_validated_mission"
    assert report["mission"]["id"] == str(mission.id)
    assert provider.ledger.snapshot()["reserved_requests"] - before == 1
    assert len(runtime.samples) == 2


def test_resume_report_checks_synthetic_inputs_and_matching_original_reply(tmp_path):
    plan = plan_for(REQUEST)
    source = {
        "version": 1,
        "mode": "live",
        "synthetic": True,
        "request": REQUEST.model_dump(),
        "observation": OBSERVATION,
        "mission": {
            "id": "11111111-1111-4111-8111-111111111111",
            "mission": plan,
            "generation": {
                "provider": "tinker",
                "model": "Qwen/Qwen3.5-4B",
                "target": "base",
                "prompt_version": "mission-v1",
            },
            "safety_note": "Skip if unsuitable.",
        },
        "raw_synthetic_model_outputs": [{"text": json.dumps(plan)}],
    }
    path = smoke.save_report(source, tmp_path)
    mission, digest = smoke.resume_mission(path)
    assert mission.mission.model_dump() == plan
    assert len(digest) == 64

    source["mission"]["mission"]["remember"] = "Changed after generation."
    changed = smoke.save_report(source, tmp_path)
    with pytest.raises(ValueError, match="Captured reply does not match"):
        smoke.resume_mission(changed)

    source["observation"] = "Private note substituted for the synthetic test."
    private = smoke.save_report(source, tmp_path)
    with pytest.raises(ValueError, match="Invalid resume report"):
        smoke.resume_mission(private)


def test_cli_live_flag_does_not_override_disabled_server_configuration(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(smoke, "load_dotenv", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(Settings, "from_environment", lambda: Settings(data_dir=tmp_path))
    monkeypatch.setattr(JournalSettings, "from_environment", JournalSettings)

    def forbidden(*_args):
        raise AssertionError("live_run must never be called when configuration is disabled")

    monkeypatch.setattr(smoke, "live_run", forbidden)
    assert smoke.main(["--live"]) == 2
    assert json.loads(capsys.readouterr().out)["mode"] == "preflight"
    assert list(tmp_path.iterdir()) == []
