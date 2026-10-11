import json

import pytest
from onelap import experiments, training
from onelap.experiment_budget import ExperimentBudget, ExperimentError
from onelap.training_data import load_corpus


class Tokenizer:
    def apply_chat_template(self, messages, **kwargs):
        assert kwargs["enable_thinking"] is False
        return [10, 11, 12]

    def encode(self, text, **kwargs):
        assert text.endswith("<|im_end|>\n")
        assert kwargs == {"add_special_tokens": False}
        return [20, 21, 22, 23]


class FakeTrainer:
    tokenizer = Tokenizer()

    def __init__(self):
        self.batches = []
        self.closed = None
        self.saved = 0

    def step(self, rows):
        self.batches.append(rows)
        return {"loss": 1.5}

    def save(self):
        self.saved += 1
        return "tinker://fictional-session/sampler_weights/onelap-final"

    def close(self, successful):
        self.closed = successful


def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "REPORT_ROOT", tmp_path)
    return load_corpus(), ExperimentBudget(tmp_path), tmp_path / "training.json"


def test_train_only_shifted_sequences_and_assistant_loss_mask():
    corpus = load_corpus()
    rows = training.prepare_sequences(corpus, Tokenizer())
    assert len(rows) == 100
    assert {row["case_id"] for row in rows} == {
        example.case.id
        for example in corpus.examples
        if corpus.families[example.case.family] == "train"
    }
    for row in rows:
        assert row["input"] == [10, 11, 12, 20, 21, 22]
        assert row["target"] == [11, 12, 20, 21, 22, 23]
        assert row["weights"] == [0.0, 0.0, 1.0, 1.0, 1.0, 1.0]


def test_one_candidate_thirty_updates_single_save_and_bound_receipt(tmp_path, monkeypatch):
    corpus, budget, output = setup(tmp_path, monkeypatch)
    trainer = FakeTrainer()
    receipt = training.train(corpus, Tokenizer(), budget, "pilot", output, lambda: trainer)
    assert len(trainer.batches) == 30
    assert all(len(batch) == 10 for batch in trainer.batches)
    assert all(
        len({row["case_id"] for batch in trainer.batches[offset : offset + 10] for row in batch})
        == 100
        for offset in (0, 10, 20)
    )
    assert trainer.saved == 1 and trainer.closed is True
    assert receipt["checkpoint_ttl_seconds"] == 604800
    assert receipt["completed_updates"] == receipt["expected_updates"] == 30
    assert receipt["status"] == "completed"
    assert training.load_receipt(output, corpus) == receipt
    assert budget.snapshot()["reserved_operations"] == 30
    assert "automatically_activated" not in receipt
    with pytest.raises(ExperimentError, match="already_admitted"):
        training.train(
            corpus,
            Tokenizer(),
            budget,
            "another",
            tmp_path / "another.json",
            lambda: pytest.fail("must not create another candidate"),
        )


def test_failed_update_retains_reservation_and_never_saves_or_retries(tmp_path, monkeypatch):
    corpus, budget, output = setup(tmp_path, monkeypatch)

    class Failing(FakeTrainer):
        def step(self, rows):
            raise TimeoutError("PRIVATE-PROVIDER-DATA")

    trainer = Failing()
    with pytest.raises(TimeoutError):
        training.train(corpus, Tokenizer(), budget, "pilot", output, lambda: trainer)
    report = json.loads(output.read_text())
    assert report["status"] == "failed" and report["completed_updates"] == 0
    assert "PRIVATE" not in output.read_text()
    assert budget.snapshot()["reserved_operations"] == 1
    assert trainer.saved == 0 and trainer.closed is False
    with pytest.raises(ExperimentError, match="binding_mismatch"):
        training.load_receipt(output, corpus)


def test_preflight_budget_precedes_client_and_checkpoint_creation(tmp_path, monkeypatch):
    corpus, budget, output = setup(tmp_path, monkeypatch)
    budget.claim("earlier", "different")
    budget.reserve("earlier", "already-used", 749_999)
    with pytest.raises(ExperimentError, match="remaining_pilot_budget"):
        training.train(
            corpus,
            Tokenizer(),
            budget,
            "pilot",
            output,
            lambda: pytest.fail("must not create training client"),
        )
    assert not output.exists()


def test_training_tokenizer_mismatch_stops_before_first_update(tmp_path, monkeypatch):
    corpus, budget, output = setup(tmp_path, monkeypatch)

    class Different(Tokenizer):
        def encode(self, text, **kwargs):
            return [90]

    trainer = FakeTrainer()
    trainer.tokenizer = Different()
    with pytest.raises(ExperimentError, match="tokenizer_binding_mismatch"):
        training.train(corpus, Tokenizer(), budget, "pilot", output, lambda: trainer)
    assert budget.snapshot()["reserved_operations"] == 0
    assert trainer.saved == 0 and trainer.closed is False


def test_preview_is_credential_free_and_storage_is_separate():
    preview = training.training_preview(load_corpus(), Tokenizer())
    assert preview["hosted_requests"] == 0
    assert preview["human_review"] == "pending"
    assert preview["storage"]["excluded_from_token_estimate"] is True
    assert preview["storage"]["saved_checkpoints"] == 1
    assert preview["training_estimated_reserved_usd"] < 0.75
