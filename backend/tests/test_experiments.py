import json

import pytest
from onelap import experiments
from onelap.evaluation import DEFAULT_DATASET, load_artifact
from onelap.evaluation_models import EvaluationDataset, EvaluationRun, RunIdentity
from onelap.experiment_budget import ExperimentBudget, ExperimentError


class Tokenizer:
    def apply_chat_template(self, messages, **kwargs):
        assert kwargs["enable_thinking"] is False
        return [1, 2, 3]


class FakeSampler:
    tokenizer = Tokenizer()

    def __init__(self, identity):
        self.identity = identity

    def sample(self, tokens):
        return "{}", 2


def fixture_setup(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "REPORT_ROOT", tmp_path)
    dataset = load_artifact(DEFAULT_DATASET, EvaluationDataset)
    identity = RunIdentity(
        provider="tinker",
        model="Qwen/Qwen3.5-4B",
        target="base",
        checkpoint=None,
        training_dataset_sha256=None,
    )
    return dataset, identity, ExperimentBudget(tmp_path)


def test_capture_accounts_every_case_and_preserves_invalid_reply(tmp_path, monkeypatch):
    dataset, identity, budget = fixture_setup(tmp_path, monkeypatch)
    output = tmp_path / "base.json"
    result = experiments.capture(
        dataset, "dev", identity, "base", output, Tokenizer(), budget, FakeSampler
    )
    run = load_artifact(output, EvaluationRun)
    assert len(run.results) == 6
    assert all(row.raw_output == "{}" and row.review is None for row in run.results)
    assert result["application_acceptance"]["passed"] == 0
    assert result["evidence_status"] == "dataset_review_pending"
    assert budget.snapshot()["reserved_operations"] == 6


def test_failure_stops_without_paid_retry_and_retains_not_run_cases(tmp_path, monkeypatch):
    dataset, identity, budget = fixture_setup(tmp_path, monkeypatch)

    class Failing(FakeSampler):
        def sample(self, tokens):
            raise TimeoutError("sensitive provider failure")

    output = tmp_path / "failure.json"
    with pytest.raises(ExperimentError, match="capture_stopped"):
        experiments.capture(
            dataset, "dev", identity, "failed", output, Tokenizer(), budget, Failing
        )
    rows = json.loads(output.read_text())["results"]
    assert rows[0]["error"] == "timeout"
    assert all(row["error"] == "not_run" for row in rows[1:])
    assert "sensitive provider" not in output.read_text()
    assert budget.snapshot()["reserved_operations"] == 1


def test_tokenizer_mismatch_stops_before_sampling(tmp_path, monkeypatch):
    dataset, identity, budget = fixture_setup(tmp_path, monkeypatch)

    class DifferentTokenizer(Tokenizer):
        def apply_chat_template(self, messages, **kwargs):
            return [99]

    class Mismatched(FakeSampler):
        tokenizer = DifferentTokenizer()

        def sample(self, tokens):
            pytest.fail("must not sample mismatched tokens")

    with pytest.raises(ExperimentError, match="capture_stopped"):
        experiments.capture(
            dataset,
            "dev",
            identity,
            "mismatch",
            tmp_path / "mismatch.json",
            Tokenizer(),
            budget,
            Mismatched,
        )
    assert budget.snapshot()["reserved_operations"] == 1


def test_output_must_be_ignored_and_not_overwritten(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "REPORT_ROOT", tmp_path / "reports")
    with pytest.raises(ExperimentError, match="ignored_experiments"):
        experiments.write_report(tmp_path / "public.json", {})
    path = tmp_path / "reports" / "report.json"
    experiments.write_report(path, {"first": True})
    with pytest.raises(FileExistsError):
        experiments.write_report(path, {"first": False})
    assert json.loads(path.read_text()) == {"first": True}


def test_fixture_cannot_claim_deterministic_model_improvement(tmp_path, monkeypatch):
    dataset, identity, budget = fixture_setup(tmp_path, monkeypatch)
    output = tmp_path / "fixture.json"
    experiments.capture(
        dataset, "heldout", identity, "base", output, Tokenizer(), budget, FakeSampler
    )
    run = load_artifact(output, EvaluationRun).model_copy(update={"origin": "fixture"})
    with pytest.raises(ExperimentError, match="fixtures_are_not"):
        experiments.deterministic_comparison(dataset, run, run)
