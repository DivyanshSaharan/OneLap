import json
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from onelap import browser_smoke
from onelap.browser_fixtures import FixtureJournal, FixtureRuntime
from onelap.browser_smoke import OBSERVATION, REQUEST, SyntheticJournal
from onelap.budget import BudgetLedger
from onelap.config import Settings
from onelap.errors import MissionError
from onelap.journal_models import MissionSnapshot, OutingInput
from onelap.journal_repository import now
from onelap.models import GenerationIdentity, MissionPlan
from test_journal import CONFIG


@pytest.fixture
def tracked():
    return SyntheticJournal(FixtureJournal(CONFIG))


@pytest.fixture
def entry():
    plan = json.loads(FixtureRuntime(REQUEST).sample([]))
    return OutingInput(
        id=str(uuid4()),
        mission=MissionSnapshot(
            id=str(uuid4()),
            mission=MissionPlan(**plan),
            generation=GenerationIdentity(),
            safety_note="Skip if unsuitable.",
        ),
        observation=OBSERVATION,
        outcome="completed",
        feedback="too_difficult",
        recorded_at=now(),
    )


@pytest.mark.parametrize("operation", ["save", "page", "selected", "delete"])
def test_wrapper_rejects_other_owner_before_repository_access(tracked, entry, operation):
    arguments = {
        "save": entry,
        "page": None,
        "selected": [entry.id],
        "delete": entry.id,
    }
    with pytest.raises(MissionError, match="journal_owner_mismatch"):
        getattr(tracked, operation)(str(uuid4()), arguments[operation])
    assert not tracked.repository.records
    assert not tracked.repository.deleted


@pytest.mark.parametrize(
    "change",
    [
        {"observation": "PRIVATE PERSONAL NOTE"},
        {"feedback": "useful"},
        {"outcome": "skipped"},
    ],
)
def test_nonfictional_or_different_input_cannot_be_written(tracked, entry, change):
    with pytest.raises(MissionError, match="synthetic_test_boundary"):
        tracked.save(CONFIG.owner_id, entry.model_copy(update=change))
    assert tracked.cleanup() == "not_needed"
    assert not tracked.repository.records


def test_only_one_exact_entry_and_no_extra_context_can_be_used(tracked, entry):
    tracked.save(CONFIG.owner_id, entry)
    tracked.save(CONFIG.owner_id, entry)
    with pytest.raises(MissionError, match="synthetic_test_boundary"):
        tracked.save(CONFIG.owner_id, entry.model_copy(update={"id": str(uuid4())}))
    with pytest.raises(MissionError, match="synthetic_test_boundary"):
        tracked.selected(CONFIG.owner_id, [entry.id, str(uuid4())])
    with pytest.raises(MissionError, match="synthetic_test_boundary"):
        tracked.delete(CONFIG.owner_id, str(uuid4()))
    assert tracked.cleanup() == "verified"
    assert not tracked.repository.records
    assert tracked.repository.deleted == {entry.id}


def test_lost_storage_reply_is_tracked_and_cleaned(tracked, entry, monkeypatch):
    original = tracked.repository.save

    def interrupted(owner, value):
        original(owner, value)
        raise RuntimeError("PRIVATE URI")

    monkeypatch.setattr(tracked.repository, "save", interrupted)
    with pytest.raises(RuntimeError):
        tracked.save(CONFIG.owner_id, entry)
    assert tracked.entry == entry
    assert tracked.cleanup() == "verified"


def test_deletion_or_replay_failure_never_counts_as_verified(tracked, entry, monkeypatch):
    tracked.save(CONFIG.owner_id, entry)
    monkeypatch.setattr(tracked.repository, "delete", lambda *_args: None)
    with pytest.raises(MissionError, match="journal_cleanup_not_verified"):
        tracked.cleanup()
    monkeypatch.undo()
    monkeypatch.setattr(tracked.repository, "save", lambda *_args: None)
    with pytest.raises(MissionError, match="deleted_entry_replayed"):
        tracked.cleanup()


def test_browser_child_does_not_inherit_credentials(monkeypatch):
    monkeypatch.setenv("TINKER_API_KEY", "PRIVATE KEY")
    monkeypatch.setenv("MONGODB_URI", "PRIVATE URI")
    monkeypatch.setenv("SENTRY_DSN", "PRIVATE DSN")
    monkeypatch.setenv("ONELAP_ACCESS_TOKEN", "PRIVATE TOKEN")
    env = browser_smoke.browser_environment()
    assert not {"TINKER_API_KEY", "MONGODB_URI", "SENTRY_DSN", "ONELAP_ACCESS_TOKEN"} & env.keys()
    assert "PRIVATE" not in json.dumps(env)


def test_occupied_server_port_does_not_attach_to_or_terminate_other_process(monkeypatch):
    closed = []

    class OccupiedSocket:
        def setsockopt(self, *_args):
            pass

        def bind(self, address):
            assert address == ("127.0.0.1", 8770)
            raise OSError("already in use")

        def close(self):
            closed.append(True)

    monkeypatch.setattr(browser_smoke.socket, "socket", lambda *_args: OccupiedSocket())
    monkeypatch.setattr("uvicorn.Server", lambda *_args: pytest.fail("must not start"))
    with pytest.raises(OSError, match="already in use"), browser_smoke.local_server(object()):
        pytest.fail("must not yield")
    assert closed == [True]


def test_live_flag_and_consent_never_override_disabled_saved_gates(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(browser_smoke, "load_dotenv", lambda *_args, **_kw: None)
    monkeypatch.setattr(Settings, "from_environment", lambda: Settings(data_dir=tmp_path))
    monkeypatch.setattr(browser_smoke, "run", lambda *_args, **_kw: pytest.fail("must not run"))
    assert browser_smoke.main(["--live", "--approve-synthetic-sharing"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert "hosted_requests_disabled" in result["blockers"]
    assert "reflection_sharing_not_approved" in result["blockers"]
    assert not list(tmp_path.iterdir())


def test_live_mode_requires_separate_synthetic_consent(monkeypatch, capsys):
    monkeypatch.setattr(browser_smoke, "load_dotenv", lambda *_args, **_kw: None)
    monkeypatch.setattr(browser_smoke, "run", lambda *_args, **_kw: pytest.fail("must not run"))
    assert browser_smoke.main(["--live"]) == 2
    assert (
        "browser_synthetic_sharing_not_approved" in json.loads(capsys.readouterr().out)["blockers"]
    )


@pytest.mark.parametrize("fail_after_upload", [False, True])
def test_fixture_run_uses_real_app_and_isolated_budget_and_always_cleans_up(
    tmp_path,
    monkeypatch,
    fail_after_upload,
):
    build = tmp_path / "dist"
    build.mkdir()
    (build / "index.html").write_text("fixture build", encoding="utf-8")
    settings = Settings(
        api_key="fixture-only",
        hosted_enabled=True,
        data_sharing_approved=True,
        reflection_sharing_approved=True,
        budget_microdollars=50_000,
        data_dir=tmp_path / "data",
        frontend_directory=build,
    )
    original_ledger = BudgetLedger(settings.data_dir)
    original_ledger.reserve(1000, 50_000, 10)
    before = original_ledger.snapshot()
    clients = []

    @contextmanager
    def server(app):
        with TestClient(app) as client:
            clients.append(client)
            yield

    def browser(payload):
        client = clients[0]
        owner = payload["owner"]
        headers = {"Authorization": "Bearer " + payload["token"], "X-OneLap-Journal-Owner": owner}
        response = client.post("/api/missions", headers=headers, json=REQUEST.model_dump())
        assert response.status_code == 201
        mission = response.json()
        entry = {
            "id": str(uuid4()),
            "mission": mission,
            "outcome": "completed",
            "feedback": "too_difficult",
            "recorded_at": now(),
            "observation": OBSERVATION,
        }
        response = client.post(
            "/api/journal/entries",
            headers=headers,
            json={"owner_id": owner, "entry": entry},
        )
        assert response.status_code == 200
        if fail_after_upload:
            raise RuntimeError("PRIVATE BROWSER DETAIL")
        assert (
            client.post(
                "/api/followups",
                headers=headers,
                json={"source_id": entry["id"], "context_ids": []},
            ).status_code
            == 200
        )
        (Path(payload["output"]) / "browser.json").write_text(
            json.dumps(
                {
                    "status": "passed",
                    "model_request_attempts": 2,
                    "blocked_requests": 0,
                    "page_errors": 0,
                }
            ),
            encoding="utf-8",
        )
        return 0

    monkeypatch.setattr(browser_smoke, "local_server", server)
    report, path = browser_smoke.run(settings, CONFIG, fixture=True, browser=browser)
    assert report["status"] == ("failed" if fail_after_upload else "passed")
    assert report["cleanup"] == "verified"
    assert report["mode"] == "fixture"
    assert report["test_owner_id"] != CONFIG.owner_id
    assert report["reserved_model_requests_in_run"] == (1 if fail_after_upload else 2)
    assert original_ledger.snapshot() == before
    assert "PRIVATE" not in path.read_text(encoding="utf-8")
    assert not settings.access_token


def test_fixture_cli_never_reads_dotenv_or_initializes_hosted_clients(
    tmp_path, monkeypatch, capsys
):
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(browser_smoke, "ROOT", tmp_path)
    monkeypatch.setattr(browser_smoke, "load_dotenv", lambda *_args, **_kw: pytest.fail("dotenv"))
    monkeypatch.setattr(Settings, "from_environment", lambda: pytest.fail("saved settings"))

    def run(settings, _journal, **kwargs):
        assert settings.api_key == "fixture-only"
        assert kwargs == {"fixture": True}
        return {
            "mode": "fixture",
            "status": "passed",
            "cleanup": "verified",
            "reserved_model_requests_in_run": 2,
        }, tmp_path / "report.json"

    monkeypatch.setattr(browser_smoke, "run", run)
    assert browser_smoke.main(["--fixture"]) == 0
    assert json.loads(capsys.readouterr().out)["mode"] == "fixture"
