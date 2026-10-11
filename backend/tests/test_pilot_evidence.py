"""The checked-in public summary is bounded, honest and free of private identifiers."""

import json

from onelap.config import ROOT
from onelap.training_data import frozen_manifest, load_corpus


def test_public_pilot_matches_frozen_corpus_and_never_claims_human_review():
    summary = json.loads((ROOT / "reports/onelap-pilot-v1.json").read_text())
    manifest = frozen_manifest(load_corpus())
    for name in ("corpus_sha256", "training_dataset_sha256", "evaluation_dataset_sha256"):
        assert summary[name] == manifest[name]
    assert summary["semantic_review"] == "pending"
    assert summary["automatically_activated"] is False
    assert "not_human_reviewed" in summary["review_status"]


def test_public_pilot_denominators_cost_and_activation_are_explicit():
    summary = json.loads((ROOT / "reports/onelap-pilot-v1.json").read_text())
    assert summary["training"]["completed_updates"] == 30
    assert summary["training"]["checkpoint_ttl_seconds"] == 604800
    assert summary["development"]["cases"] == 20
    assert summary["heldout"]["cases"] == 30
    assert summary["heldout"]["baseline_accepted"] == 20
    assert summary["heldout"]["adapter_accepted"] == 29
    assert summary["budget"]["logical_operations"] == 130
    assert summary["budget"]["token_reserved_usd"] <= 0.75
    assert summary["budget"]["not_an_invoice"] is True
    assert summary["budget"]["checkpoint_storage_excluded"] is True
    for split in ("development", "heldout"):
        assert 0 <= summary[split]["baseline_accepted"] <= summary[split]["cases"]
        assert 0 <= summary[split]["adapter_accepted"] <= summary[split]["cases"]


def test_public_summary_contains_no_sampler_path_credentials_or_raw_responses():
    raw = (ROOT / "reports/onelap-pilot-v1.json").read_text()
    assert "tinker://" not in raw
    assert "mongodb+srv://" not in raw
    assert "api_key" not in raw.lower()
    assert "raw_output" not in raw
    assert "observation" not in raw.lower()
