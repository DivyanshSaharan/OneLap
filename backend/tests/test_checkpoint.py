import hashlib
import json
import sys
from dataclasses import replace
from types import SimpleNamespace

import pytest
from onelap import checkpoint
from onelap.budget import BudgetLedger
from onelap.config import MODEL, ROOT, Settings
from onelap.evaluation import method_digest
from onelap.models import GenerationIdentity
from onelap.provider import TinkerProvider, TinkerRuntime
from pydantic import ValidationError


def receipt_file(tmp_path, changes=None):
    manifest = json.loads((ROOT / "datasets/onelap-sft-v1.manifest.json").read_text())
    receipt = {
        "version": 1,
        "status": "completed",
        "model": MODEL,
        "corpus_sha256": manifest["corpus_sha256"],
        "training_dataset_sha256": manifest["training_dataset_sha256"],
        "method_sha256": method_digest(),
        "parameters": dict(checkpoint.PARAMETERS),
        "completed_updates": 30,
        "expected_updates": 30,
        "checkpoint": "tinker://fictional/sampler_weights/final",
    }
    receipt.update(changes or {})
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt))
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def selection(tmp_path, changes=None):
    path, receipt_hash = receipt_file(tmp_path, changes)
    return Settings(
        model_target="adapter",
        checkpoint_approved=True,
        checkpoint_receipt=path,
        checkpoint_receipt_sha256=receipt_hash,
        data_dir=tmp_path,
    )


def test_default_has_no_adapter_and_legacy_identity_exact_keys():
    assert checkpoint.load_checkpoint(Settings()) is None
    assert GenerationIdentity().model_dump() == {
        "provider": "tinker",
        "model": MODEL,
        "target": "base",
        "prompt_version": "mission-v1",
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"checkpoint_approved": False},
        {"checkpoint_receipt": None},
        {"checkpoint_receipt_sha256": "bad"},
        {"model_target": "unknown"},
    ],
)
def test_explicit_approval_and_receipt_are_required(tmp_path, changes):
    with pytest.raises(ValueError):
        replace(selection(tmp_path), **changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "failed"},
        {"version": True},
        {"model": "another-model"},
        {"corpus_sha256": "0" * 64},
        {"training_dataset_sha256": "0" * 64},
        {"method_sha256": "0" * 64},
        {"completed_updates": 29},
        {"expected_updates": True},
        {"parameters": {"rank": 32}},
        {"checkpoint": "tinker://fictional/weights/not-a-sampler"},
        {"checkpoint": "tinker://fictional/sampler_weights/final\n"},
    ],
)
def test_invalid_receipt_fails_closed_without_exposing_path(tmp_path, changes):
    with pytest.raises(ValueError, match="invalid_or_unapproved_checkpoint_receipt"):
        checkpoint.load_checkpoint(selection(tmp_path, changes))


def test_receipt_digest_and_truthful_provider_identity(tmp_path):
    settings = selection(tmp_path)
    selected = checkpoint.load_checkpoint(settings)
    assert selected.training_dataset_sha256
    assert "tinker://" not in repr(selected)
    provider = TinkerProvider(
        settings,
        BudgetLedger(tmp_path),
        lambda _: pytest.fail("not a sampling operation"),
        lambda: True,
    )
    assert provider.status().target == "adapter"
    identity = provider.identity("follow-up-v2")
    assert identity.target == "adapter"
    assert identity.checkpoint_sha256 == settings.checkpoint_receipt_sha256
    assert identity.training_dataset_sha256 == selected.training_dataset_sha256
    assert "tinker://" not in identity.model_dump_json()
    with pytest.raises(ValueError, match="invalid_or_unapproved"):
        checkpoint.load_checkpoint(replace(settings, checkpoint_receipt_sha256="0" * 64))


@pytest.mark.parametrize(
    "data",
    [
        {"target": "adapter"},
        {"checkpoint_sha256": "a" * 64},
        {"target": "adapter", "checkpoint_sha256": "bad", "training_dataset_sha256": "b" * 64},
    ],
)
def test_generation_identity_requires_consistent_hashes(data):
    with pytest.raises(ValidationError):
        GenerationIdentity(**data)


def test_runtime_selects_checkpoint_and_rejects_wrong_model_before_tokenizer(monkeypatch):
    from tinker.lib.retry_handler import RetryConfig  # Load the real nested module before stubbing.

    assert RetryConfig
    selections = []

    class Client:
        def get_base_model(self):
            return "wrong-model"

        def get_tokenizer(self):
            pytest.fail("must reject wrong model first")

    class Service:
        def __init__(self, **kwargs):
            pass

        def create_sampling_client(self, **kwargs):
            selections.append(kwargs)
            return Client()

    monkeypatch.setitem(sys.modules, "tinker", SimpleNamespace(ServiceClient=Service))
    from onelap.errors import MissionError

    with pytest.raises(MissionError, match="provider_model_mismatch"):
        TinkerRuntime("fictional", "tinker://fictional/sampler_weights/final")
    assert selections[0]["model_path"] == "tinker://fictional/sampler_weights/final"
    assert "base_model" not in selections[0]
