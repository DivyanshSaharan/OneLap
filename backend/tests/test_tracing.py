import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from conftest import ACCESS_TOKEN, plan_for
from fastapi.testclient import TestClient
from onelap import tracing
from onelap.errors import MissionError
from onelap.journal_models import MissionSnapshot, OutingInput
from onelap.main import create_app
from onelap.models import GenerationIdentity, MissionPlan
from onelap.tracing import Tracer, TracingSettings, filter_transaction, safe_data
from sentry_sdk.transport import Transport
from test_followup import JOURNAL_SETTINGS, OWNER, SelectedJournal, record
from test_journal import CONFIG, Collection
from test_smoke import offline_journal

DSN = "https://fictionalkey@o0.ingest.sentry.io/0"
APPROVED = TracingSettings(enabled=True, sharing_approved=True, dsn=DSN)
HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}", "X-OneLap-Journal-Owner": OWNER}


class Collector(Transport):
    """Capture actual SDK envelopes in memory; no HTTP transport is constructed."""

    def __init__(self, options):
        super().__init__(options)
        self.serialized = []
        self.events = []

    def capture_envelope(self, envelope):
        assert all(item.type == "transaction" for item in envelope.items)
        self.serialized.append(envelope.serialize())
        self.events.extend(item.payload.json for item in envelope.items)


@pytest.fixture
def collector_trace(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("No HTTP transport is allowed in tracing tests")

    monkeypatch.setattr("sentry_sdk.transport.HttpTransport.__init__", forbidden)
    tracer = Tracer(APPROVED, transport=Collector)
    yield tracer, tracer.client.transport
    tracer.close()


@pytest.mark.parametrize(
    "settings,reason",
    [
        (TracingSettings(), "tracing_disabled"),
        (TracingSettings(enabled=True, dsn=DSN), "trace_sharing_not_approved"),
        (TracingSettings(enabled=True, sharing_approved=True), "tracing_not_configured"),
    ],
)
def test_disabled_gates_do_not_import_sdk_or_construct_a_client(monkeypatch, settings, reason):
    def forbidden(*_args):
        raise AssertionError("Disabled tracing must not import any SDK")

    monkeypatch.setattr(tracing.importlib, "import_module", forbidden)
    tracer = Tracer(settings)
    with tracer.run("mission", prompt_version="mission-v1"):
        with tracer.span("sample") as span:
            span.set(**{"gen_ai.usage.input_tokens": 100})
    tracer.close()
    assert settings.disabled_reason() == reason
    assert tracer.client is None
    assert DSN not in repr(settings)


@pytest.mark.parametrize(
    "dsn",
    [
        "http://fictionalkey@o0.ingest.sentry.io/0",
        "https://fictionalkey@private.example/0",
        "https://fictionalkey:private-password@o0.ingest.sentry.io/0",
        "https://fictionalkey@o0.ingest.sentry.io/private-journal",
        "https://fictionalkey@o0.ingest.sentry.io/0?secret=private",
        "https://fictionalkey@o0.ingest.sentry.io/0#private",
    ],
)
def test_dsn_validation_never_returns_its_value(dsn):
    with pytest.raises(ValueError, match="^Invalid Sentry DSN$"):
        TracingSettings(dsn=dsn)


def test_environment_requires_both_explicit_gates(monkeypatch):
    monkeypatch.setenv("ONELAP_SENTRY_DSN", DSN)
    monkeypatch.delenv("ONELAP_TRACING_ENABLED", raising=False)
    monkeypatch.delenv("ONELAP_TRACE_SHARING_APPROVED", raising=False)
    assert TracingSettings.from_environment().disabled_reason() == "tracing_disabled"
    monkeypatch.setenv("ONELAP_TRACING_ENABLED", "true")
    assert TracingSettings.from_environment().disabled_reason() == "trace_sharing_not_approved"
    monkeypatch.setenv("ONELAP_TRACE_SHARING_APPROVED", "true")
    assert TracingSettings.from_environment() == APPROVED
    monkeypatch.setenv("ONELAP_TRACING_ENABLED", "yes")
    with pytest.raises(ValueError):
        TracingSettings.from_environment()


def test_allowlist_rejects_content_even_under_known_keys():
    assert safe_data(
        {
            "gen_ai.request.model": "PRIVATE MODEL LABEL",
            "gen_ai.usage.input_tokens": "private text",
            "gen_ai.usage.output_tokens": True,
            "error.type": "private_secret",
            "onelap.estimated_reserved_usd": float("nan"),
            "gen_ai.input.messages": "PRIVATE PROMPT",
            "gen_ai.usage.input_tokens.extra": "PRIVATE",
            "onelap.workflow": "mission",
        }
    ) == {"onelap.workflow": "mission"}


def test_final_transaction_filter_rebuilds_instead_of_redacting():
    span = {
        "op": "gen_ai.chat",
        "description": "chat Qwen/Qwen3.5-4B",
        "span_id": "a" * 16,
        "trace_id": "b" * 32,
        "start_timestamp": 1.0,
        "timestamp": 2.0,
        "data": {"gen_ai.usage.input_tokens": 100, "unknown": "PRIVATE"},
        "tags": {"password": "PRIVATE"},
    }
    event = {
        "type": "transaction",
        "transaction": "invoke_agent OneLap",
        "start_timestamp": 1.0,
        "timestamp": 2.0,
        "contexts": {
            "trace": {
                "op": "gen_ai.invoke_agent",
                "span_id": "c" * 16,
                "trace_id": "b" * 32,
                "data": {"onelap.workflow": "mission"},
                "dynamic_sampling_context": {"release": "PRIVATE"},
            },
            "device": {"name": "PRIVATE"},
        },
        "request": {"headers": {"authorization": "PRIVATE"}, "data": "PRIVATE"},
        "user": {"email": "PRIVATE"},
        "breadcrumbs": [{"message": "PRIVATE"}],
        "extra": {"new_sdk_field": "PRIVATE"},
        "spans": [span, {**span, "description": "PRIVATE database query"}],
    }
    clean = filter_transaction(event, {})
    assert "PRIVATE" not in json.dumps(clean)
    assert len(clean["spans"]) == 1
    assert clean["spans"][0]["data"] == {"gen_ai.usage.input_tokens": 100}
    assert set(clean["contexts"]) == {"trace"}
    assert filter_transaction({**event, "transaction": "PRIVATE"}, {}) is None
    assert filter_transaction({**event, "type": "error"}, {}) is None


def test_actual_sdk_envelope_excludes_inherited_scope_and_exception_content(collector_trace):
    import sentry_sdk

    tracer, collector = collector_trace
    with sentry_sdk.isolation_scope() as scope:
        scope.set_user({"email": "PRIVATE EMAIL"})
        scope.set_context("private_context", {"data": "PRIVATE CONTEXT"})
        scope.set_extra("private_extra", "PRIVATE EXTRA")
        scope.set_tag("private_tag", "PRIVATE TAG")
        with pytest.raises(RuntimeError, match="PRIVATE EXCEPTION"):
            with tracer.run("mission", prompt_version="mission-v1"):
                with tracer.span("sample", **{"gen_ai.input.messages": "PRIVATE PROMPT"}):
                    raise RuntimeError("PRIVATE EXCEPTION")
    assert len(collector.events) == 1
    assert b"PRIVATE" not in b"".join(collector.serialized)
    event = collector.events[0]
    assert event["contexts"]["trace"]["status"] == "internal_error"
    assert event["contexts"]["trace"]["data"]["error.type"] == "internal_error"
    assert event["spans"][0]["status"] == "internal_error"
    assert "start_timestamp" in event and "timestamp" in event


def test_sdk_options_disable_every_automatic_content_channel(collector_trace):
    tracer, collector = collector_trace
    options = tracer.client.options
    assert options["trace_lifecycle"] == "static"
    assert options["stream_gen_ai_spans"] is False
    assert tracer.client.integrations == {}
    for key in (
        "default_integrations",
        "auto_enabling_integrations",
        "send_default_pii",
        "include_local_variables",
        "include_source_context",
        "enable_logs",
        "enable_metrics",
        "auto_session_tracking",
        "send_client_reports",
        "propagate_traces",
    ):
        assert options[key] is False
    assert options["max_request_body_size"] == "never"
    assert options["trace_propagation_targets"] == []
    assert options["before_send"]({"exception": "PRIVATE"}, {}) is None
    assert options["before_breadcrumb"]({"message": "PRIVATE"}, {}) is None
    assert collector.events == []


def test_mission_api_emits_only_measured_metadata(provider_factory, collector_trace, request_data):
    tracer, collector = collector_trace
    provider, runtime, _ = provider_factory()
    runtime.output_token_count = 37  # Explicit reported usage from an offline double.
    with TestClient(create_app(provider.settings, provider=provider, tracer=tracer)) as client:
        response = client.post("/api/missions", headers=HEADERS, json=request_data)
    assert response.status_code == 201
    assert len(collector.events) == 1
    event = collector.events[0]
    by_op = {span["op"]: span for span in event["spans"]}
    model = by_op["gen_ai.chat"]["data"]
    assert model["gen_ai.usage.input_tokens"] == 100
    assert model["gen_ai.usage.output_tokens"] == 37
    assert by_op["onelap.budget.reserve"]["data"]["onelap.estimated_reserved_usd"] > 0
    assert event["contexts"]["trace"]["data"]["onelap.prompt_version"] == "mission-v1"
    wire = b"".join(collector.serialized)
    for private in (ACCESS_TOKEN, provider.settings.api_key, response.json()["id"], "courtyard"):
        assert private.encode() not in wire
    assert response.json()["mission"]["instruction"].encode() not in wire


def test_provider_failure_keeps_existing_response_and_reservation(
    provider_factory, collector_trace
):
    tracer, collector = collector_trace
    provider, runtime, _ = provider_factory()
    runtime.failure = TimeoutError("PRIVATE PROVIDER DETAIL")
    with TestClient(create_app(provider.settings, provider=provider, tracer=tracer)) as client:
        response = client.post(
            "/api/missions",
            headers=HEADERS,
            json={"minutes": 15, "setting": "courtyard", "conditions": "evening"},
        )
    assert response.json() == {"error": "provider_failed_restart_required"}
    assert len(runtime.samples) == 1
    assert provider.ledger.snapshot()["reserved_requests"] == 1
    assert provider._failed is True
    assert collector.events[0]["contexts"]["trace"]["data"]["error.type"] == (
        "provider_failed_restart_required"
    )
    assert b"PRIVATE" not in b"".join(collector.serialized)


def test_live_focus_drift_is_visible_without_exporting_observation(
    provider_factory,
    collector_trace,
    mission_request,
):
    tracer, collector = collector_trace
    source = OutingInput(
        id="11111111-1111-4111-8111-111111111111",
        mission=MissionSnapshot(
            id="22222222-2222-4222-8222-222222222222",
            mission=MissionPlan(**plan_for(mission_request)),
            generation=GenerationIdentity(),
            safety_note="Skip if unsuitable.",
        ),
        outcome="completed",
        feedback="too_difficult",
        observation="PRIVATE OBSERVATION",
        recorded_at="2026-10-10T10:00:00.000Z",
    )
    output = {"reflection": "PRIVATE REFLECTION", "mission": plan_for(mission_request)}
    output["mission"]["focus"] = "light"
    provider, runtime, _ = provider_factory(
        text=json.dumps(output), changes={"reflection_sharing_approved": True}
    )
    journal = SelectedJournal([record(source)])
    with TestClient(
        create_app(
            provider.settings,
            provider=provider,
            journal_settings=JOURNAL_SETTINGS,
            journal=journal,
            tracer=tracer,
        )
    ) as client:
        response = client.post(
            "/api/followups",
            headers=HEADERS,
            json={"source_id": source.id, "context_ids": []},
        )
    assert response.json() == {"error": "mission_constraint_mismatch"}
    assert len(runtime.samples) == 1
    event = collector.events[0]
    root = event["contexts"]["trace"]
    assert root["data"]["onelap.prompt_version"] == "follow-up-v2"
    assert root["data"]["error.type"] == "mission_constraint_mismatch"
    validation = next(span for span in event["spans"] if span["op"] == "onelap.validate")
    assert validation["status"] == "internal_error"
    assert validation["data"]["error.type"] == "mission_constraint_mismatch"
    retrieval = next(span for span in event["spans"] if span["op"] == "gen_ai.execute_tool")
    assert retrieval["data"]["onelap.selected_records"] == 1
    wire = b"".join(collector.serialized)
    for private in ("PRIVATE", source.id, OWNER, JOURNAL_SETTINGS.uri):
        assert private.encode() not in wire


def test_health_status_and_unauthorized_calls_do_not_emit_traces(settings, collector_trace):
    tracer, collector = collector_trace
    with TestClient(create_app(replace(settings, hosted_enabled=False), tracer=tracer)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/api/model/status", headers=HEADERS).status_code == 200
        assert client.post("/api/missions", json={}).status_code == 401
    assert collector.events == []


def test_unknown_error_code_is_not_exported(collector_trace):
    tracer, collector = collector_trace
    with pytest.raises(MissionError):
        with tracer.run("journal_save"):
            raise MissionError("private_password_as_code")
    assert collector.events[0]["contexts"]["trace"]["data"]["error.type"] == "internal_error"
    assert b"private_password" not in b"".join(collector.serialized)


def test_missing_usage_is_omitted_not_estimated(provider_factory, collector_trace, request_data):
    tracer, collector = collector_trace
    provider, _runtime, _ = provider_factory()
    with TestClient(create_app(provider.settings, provider=provider, tracer=tracer)) as client:
        assert client.post("/api/missions", headers=HEADERS, json=request_data).status_code == 201
    span = next(span for span in collector.events[0]["spans"] if span["op"] == "gen_ai.chat")
    assert "gen_ai.usage.output_tokens" not in span["data"]
    assert "gen_ai.cost.total_tokens" not in span["data"]


def test_journal_operations_trace_timings_but_no_record_content(
    settings, collector_trace, mission_request
):
    tracer, collector = collector_trace
    entry = OutingInput(
        id="11111111-1111-4111-8111-111111111111",
        mission=MissionSnapshot(
            id="22222222-2222-4222-8222-222222222222",
            mission=MissionPlan(**plan_for(mission_request)),
            generation=GenerationIdentity(),
            safety_note="Skip if unsuitable.",
        ),
        outcome="completed",
        feedback="useful",
        observation="PRIVATE JOURNAL OBSERVATION",
        recorded_at="2026-10-10T10:00:00.000Z",
    )
    journal = offline_journal(CONFIG, Collection())
    with TestClient(
        create_app(
            settings,
            journal_settings=CONFIG,
            journal=journal,
            tracer=tracer,
        )
    ) as client:
        upload = {"owner_id": CONFIG.owner_id, "entry": entry.model_dump()}
        assert client.post("/api/journal/entries", headers=HEADERS, json=upload).status_code == 200
        assert client.get("/api/journal/entries", headers=HEADERS).status_code == 200
        assert client.delete(f"/api/journal/entries/{entry.id}", headers=HEADERS).status_code == 200
    assert len(collector.events) == 3
    assert [
        event["contexts"]["trace"]["data"]["onelap.workflow"] for event in collector.events
    ] == [
        "journal_save",
        "journal_load",
        "journal_delete",
    ]
    assert all(event["spans"][0]["op"] == "db" for event in collector.events)
    wire = b"".join(collector.serialized)
    for private in ("PRIVATE", CONFIG.owner_id, CONFIG.uri, entry.id, entry.recorded_at):
        assert private.encode() not in wire


def test_tracing_failure_does_not_retry_or_break_generation(
    provider_factory,
    collector_trace,
    request_data,
    monkeypatch,
):
    tracer, collector = collector_trace

    def fail(*_args, **_kwargs):
        raise RuntimeError("PRIVATE TRACING FAILURE")

    monkeypatch.setattr(tracer.sdk, "start_span", fail)
    provider, runtime, _ = provider_factory()
    with TestClient(create_app(provider.settings, provider=provider, tracer=tracer)) as client:
        response = client.post("/api/missions", headers=HEADERS, json=request_data)
    assert response.status_code == 201
    assert len(runtime.samples) == 1
    assert provider.ledger.snapshot()["reserved_requests"] == 1
    assert b"PRIVATE" not in b"".join(collector.serialized)


def test_threaded_runs_keep_span_parentage_and_usage_separate(collector_trace):
    tracer, collector = collector_trace

    def run(token_count):
        with tracer.run("mission", prompt_version="mission-v1"):
            with tracer.span("sample", **{"gen_ai.usage.input_tokens": token_count}):
                pass

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(run, [101, 203]))
    assert len(collector.events) == 2
    assert len({event["contexts"]["trace"]["trace_id"] for event in collector.events}) == 2
    assert {
        event["spans"][0]["data"]["gen_ai.usage.input_tokens"] for event in collector.events
    } == {
        101,
        203,
    }
    for event in collector.events:
        root = event["contexts"]["trace"]
        assert event["spans"][0]["trace_id"] == root["trace_id"]
        assert event["spans"][0]["parent_span_id"] == root["span_id"]


def test_span_outside_an_explicit_run_emits_nothing(collector_trace):
    tracer, collector = collector_trace
    with tracer.span("sample", **{"gen_ai.usage.input_tokens": 10}):
        pass
    assert collector.events == []


def test_transport_failure_does_not_change_application_result(
    provider_factory,
    collector_trace,
    request_data,
    monkeypatch,
):
    tracer, collector = collector_trace

    def fail(*_args, **_kwargs):
        raise RuntimeError("PRIVATE TRANSPORT FAILURE")

    monkeypatch.setattr(collector, "capture_envelope", fail)
    provider, runtime, _ = provider_factory()
    with TestClient(create_app(provider.settings, provider=provider, tracer=tracer)) as client:
        response = client.post("/api/missions", headers=HEADERS, json=request_data)
    assert response.status_code == 201
    assert len(runtime.samples) == 1


def test_enabling_tracing_with_missing_sdk_fails_with_a_safe_message(monkeypatch):
    def missing(*_args):
        raise ImportError("PRIVATE PATH")

    monkeypatch.setattr(tracing.importlib, "import_module", missing)
    with pytest.raises(RuntimeError, match="^OneLap tracing dependencies are missing$"):
        Tracer(APPROVED)
