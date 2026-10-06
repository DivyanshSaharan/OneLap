import json
import sys
from dataclasses import replace
from threading import Event, Thread
from types import SimpleNamespace

import pytest
from onelap.budget import BudgetLedger, reservation
from onelap.config import MODEL
from onelap.errors import MissionError
from onelap.prompts import build_messages
from onelap.provider import MAX_INPUT_TOKENS, MAX_OUTPUT_TOKENS, TinkerProvider, TinkerRuntime


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"hosted_enabled": False}, "hosted_requests_disabled"),
        ({"data_sharing_approved": False}, "data_sharing_not_approved"),
        ({"budget_microdollars": 0}, "budget_not_approved"),
        ({"api_key": ""}, "provider_not_configured"),
    ],
)
def test_approval_gates_before_client_creation(provider_factory, changes, reason):
    provider, runtime, creations = provider_factory(changes=changes)
    assert provider.status().disabled_reason == reason
    with pytest.raises(MissionError, match=reason):
        provider.generate([])
    assert creations == runtime.samples == []
    assert provider.ledger.snapshot()["reserved_requests"] == 0


def test_missing_dependencies_does_not_create_client(provider_factory):
    provider, _, creations = provider_factory(available=False)
    with pytest.raises(MissionError, match="provider_dependencies_missing"):
        provider.generate([])
    assert creations == []


def test_client_reused_and_budget_persists(provider_factory, mission_request, settings):
    provider, runtime, creations = provider_factory()
    provider.generate(build_messages(mission_request))
    provider.generate(build_messages(mission_request))
    assert creations == [settings.api_key]
    assert len(runtime.samples) == 2
    restored = BudgetLedger(settings.data_dir).snapshot()
    assert restored["reserved_requests"] == 2
    assert restored["reserved_microdollars"] == 2 * reservation(100, MAX_OUTPUT_TOKENS)


@pytest.mark.parametrize("count", [0, MAX_INPUT_TOKENS + 1])
def test_token_limit_precedes_reservation_and_sample(provider_factory, count):
    provider, runtime, _ = provider_factory()
    runtime.tokens = [1] * count
    with pytest.raises(MissionError, match="input_token_limit"):
        provider.generate([])
    assert runtime.samples == []
    assert provider.ledger.snapshot()["reserved_requests"] == 0


def test_insufficient_budget_does_not_sample(provider_factory):
    provider, runtime, _ = provider_factory(changes={"budget_microdollars": 1})
    with pytest.raises(MissionError, match="budget_exhausted"):
        provider.generate([])
    assert runtime.samples == []


def test_request_limit_persists_across_provider_restart(provider_factory, settings):
    provider, _, _ = provider_factory(changes={"max_model_requests": 1})
    provider.generate([])
    second = TinkerProvider(
        replace(settings, max_model_requests=1),
        BudgetLedger(settings.data_dir),
        lambda _: pytest.fail("must not create runtime"),
        lambda: True,
    )
    with pytest.raises(MissionError, match="model_request_limit_reached"):
        second.generate([])


@pytest.mark.parametrize(
    "failure", [RuntimeError("PRIVATE_KEY_AND_PROMPT"), TimeoutError("PRIVATE")]
)
def test_failure_is_redacted_reserved_and_disables_further_requests(provider_factory, failure):
    provider, runtime, _ = provider_factory()
    runtime.failure = failure
    with pytest.raises(MissionError) as caught:
        provider.generate([])
    assert str(caught.value) == "provider_failed_restart_required"
    assert "PRIVATE" not in str(caught.value)
    assert provider.ledger.snapshot()["reserved_requests"] == 1
    assert provider.status().disabled_reason == "provider_restart_required"
    with pytest.raises(MissionError, match="provider_restart_required"):
        provider.generate([])
    assert len(runtime.samples) == 1


def test_invalid_output_keeps_reservation_without_retry(provider_factory):
    provider, runtime, _ = provider_factory(text="not JSON")
    with pytest.raises(MissionError, match="invalid_model_output"):
        provider.generate([])
    assert len(runtime.samples) == 1
    assert provider.ledger.snapshot()["reserved_requests"] == 1


def test_concurrent_request_is_rejected(provider_factory):
    provider, runtime, _ = provider_factory()
    entered, release = Event(), Event()
    original = runtime.sample
    results = []

    def blocked(tokens):
        entered.set()
        assert release.wait(5)
        return original(tokens)

    def generate():
        try:
            results.append(provider.generate([]))
        except Exception as error:
            results.append(error)

    runtime.sample = blocked
    thread = Thread(target=generate)
    thread.start()
    try:
        assert entered.wait(5)
        with pytest.raises(MissionError, match="generation_in_progress"):
            provider.generate([])
    finally:
        release.set()
        thread.join(5)
    assert not thread.is_alive()
    assert len(results) == 1 and not isinstance(results[0], Exception)


def install_fake_sdk(monkeypatch, *, model=MODEL):
    calls = {}

    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            calls["template"] = (messages, kwargs)
            return [1, 2]

        def decode(self, tokens, **kwargs):
            calls["decode"] = (tokens, kwargs)
            return "fixture output"

    class Client:
        def get_base_model(self):
            return model

        def get_tokenizer(self):
            calls["tokenizer"] = True
            return Tokenizer()

        def sample(self, **kwargs):
            calls["sample"] = kwargs

            def result(**kwargs):
                calls["result"] = kwargs
                return SimpleNamespace(sequences=[SimpleNamespace(tokens=[3, 4])])

            return SimpleNamespace(result=result)

    class Service:
        def __init__(self, **kwargs):
            calls["service"] = kwargs

        def create_sampling_client(self, **kwargs):
            calls["client"] = kwargs
            return Client()

    types = SimpleNamespace(
        ModelInput=SimpleNamespace(from_ints=lambda tokens: tokens),
        SamplingParams=lambda **kwargs: kwargs,
    )
    monkeypatch.setitem(sys.modules, "tinker", SimpleNamespace(ServiceClient=Service, types=types))
    monkeypatch.setitem(
        sys.modules,
        "tinker.lib.retry_handler",
        SimpleNamespace(RetryConfig=lambda **kwargs: kwargs),
    )
    return calls


def test_sdk_adapter_contract_without_network(monkeypatch):
    calls = install_fake_sdk(monkeypatch)
    runtime = TinkerRuntime("fictional-test-key")
    tokens = runtime.encode([{"role": "user", "content": "fictional"}])
    assert runtime.sample(tokens) == "fixture output"
    assert calls["service"] == {"api_key": "fictional-test-key"}
    assert calls["client"]["base_model"] == MODEL
    assert calls["client"]["retry_config"]["enable_retry_logic"] is False
    assert calls["template"][1]["enable_thinking"] is False
    assert calls["sample"]["num_samples"] == 1
    assert calls["sample"]["sampling_params"] == {
        "max_tokens": 512,
        "temperature": 0.2,
        "stop": ["<|im_end|>"],
    }
    assert calls["result"] == {"timeout": 45}


def test_sdk_model_mismatch_before_tokenizer_or_sample(monkeypatch):
    calls = install_fake_sdk(monkeypatch, model="another-model")
    with pytest.raises(MissionError, match="provider_model_mismatch"):
        TinkerRuntime("fictional-test-key")
    assert "tokenizer" not in calls and "sample" not in calls


def test_status_never_contains_key_or_token(provider_factory, settings):
    provider, _, _ = provider_factory()
    status = json.dumps(provider.status().model_dump())
    assert settings.api_key not in status
    assert settings.access_token not in status
