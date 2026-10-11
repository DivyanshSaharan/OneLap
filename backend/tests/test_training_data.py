import json
import socket
from collections import Counter
from copy import deepcopy

import pytest
from onelap.evaluation import cases_for, input_digest, messages_for, records_for
from onelap.followup import validate_output
from onelap.policy import validate_plan
from onelap.training_data import (
    DEFAULT_CORPUS,
    DEFAULT_MANIFEST,
    TrainingCorpus,
    evaluation_dataset,
    frozen_manifest,
    load_corpus,
    main,
    supervised_examples,
    target_text,
    verify_frozen_corpus,
)
from pydantic import ValidationError


@pytest.fixture
def corpus():
    return load_corpus()


def test_frozen_corpus_counts_provenance_and_workflows(corpus):
    assert corpus.review_status == "agent_reviewed"
    assert corpus.provenance == "synthetic_assistant_authored"
    assert len(corpus.families) == 30
    assert Counter(corpus.families[item.case.family] for item in corpus.examples) == {
        "train": 100,
        "dev": 20,
        "heldout": 30,
    }
    assert Counter(item.case.workflow for item in supervised_examples(corpus)) == {
        "mission": 20,
        "followup": 80,
    }
    assert len({item.case.id for item in corpus.examples}) == 150


def test_agent_review_is_not_misrepresented_as_human_review(corpus):
    dataset = evaluation_dataset(corpus)
    assert dataset.review_status == "unreviewed"
    assert dataset.reviewer is None
    assert frozen_manifest(corpus)["human_reviewed"] is False
    assert len(cases_for(dataset, "dev")) == 20
    assert len(cases_for(dataset, "heldout")) == 30


def test_all_supervised_targets_pass_exact_application_validation(corpus):
    for example in supervised_examples(corpus):
        assert example.assistant_target is not None
        case = example.case
        if case.workflow == "mission":
            validate_plan(example.assistant_target, case.request)
        else:
            output = validate_output(target_text(example), *records_for(case))
            assert output == example.assistant_target
        assert json.loads(target_text(example)) == example.assistant_target.model_dump(mode="json")


def test_only_training_examples_have_targets_and_use_exact_application_prompts(corpus):
    training = supervised_examples(corpus)
    assert len(training) == 100
    assert [item.case.id for item in training] == sorted(item.case.id for item in training)
    for example in corpus.examples:
        split = corpus.families[example.case.family]
        assert (example.assistant_target is not None) == (split == "train")
        assert messages_for(example.case)[0]["role"] == "system"
        if split != "train":
            with pytest.raises(ValueError, match="no assistant target"):
                target_text(example)


@pytest.mark.parametrize(
    "change",
    [
        "human_review_claim",
        "wrong_count",
        "missing_train_target",
        "dev_target",
        "unknown_family",
        "duplicate_variant",
        "duplicate_case_id",
        "duplicate_input",
        "normalized_observation_leak",
        "target_minutes",
        "target_policy",
        "target_repeat",
        "wrong_target_shape",
        "invalid_target_json_shape",
    ],
)
def test_corpus_rejects_label_leakage_and_invalid_targets(corpus, change):
    data = deepcopy(corpus.model_dump(mode="json"))
    rows = data["examples"]
    followup = next(row for row in rows if row["case"]["workflow"] == "followup")
    dev = next(row for row in rows if data["families"][row["case"]["family"]] == "dev")
    if change == "human_review_claim":
        data["review_status"] = "human_reviewed"
    elif change == "wrong_count":
        rows.pop()
    elif change == "missing_train_target":
        rows[0]["assistant_target"] = None
    elif change == "dev_target":
        dev["assistant_target"] = deepcopy(followup["assistant_target"])
    elif change == "unknown_family":
        rows[0]["case"]["family"] = "unassigned"
    elif change == "duplicate_variant":
        rows[1]["variant"] = rows[0]["variant"]
    elif change == "duplicate_case_id":
        rows[1]["case"]["id"] = rows[0]["case"]["id"]
    elif change == "duplicate_input":
        rows[1]["case"] = {**deepcopy(rows[0]["case"]), "id": rows[1]["case"]["id"]}
    elif change == "normalized_observation_leak":
        dev["case"]["source"]["observation"] = (
            followup["case"]["source"]["observation"].upper().replace(" ", "  ") + "!"
        )
    elif change == "target_minutes":
        rows[0]["assistant_target"]["minutes"] = 20
    elif change == "target_policy":
        rows[0]["assistant_target"]["instruction"] = "Take a photograph of one pattern."
    elif change == "target_repeat":
        followup["assistant_target"]["mission"]["instruction"] = followup["case"]["source"][
            "mission"
        ]["instruction"]
    elif change == "wrong_target_shape":
        rows[0]["assistant_target"] = deepcopy(followup["assistant_target"])
    else:
        rows[0]["assistant_target"]["requires_camera"] = "false"
    with pytest.raises(ValidationError):
        TrainingCorpus.model_validate(data)


def test_manifest_binds_prompts_targets_and_case_identity(corpus):
    manifest = frozen_manifest(corpus)
    assert manifest == json.loads(DEFAULT_MANIFEST.read_text("utf-8"))
    assert manifest["hosted_requests"] == 0
    indexed = {item["case_id"]: item for item in manifest["inputs"]}
    for example in corpus.examples:
        assert indexed[example.case.id]["input_sha256"] == input_digest(example.case)
        assert (indexed[example.case.id]["target_sha256"] is not None) == (
            corpus.families[example.case.family] == "train"
        )
    data = corpus.model_dump(mode="json")
    data["examples"][0]["assistant_target"]["remember"] = "Which detail was visible?"
    updated = frozen_manifest(TrainingCorpus.model_validate(data))
    assert manifest["corpus_sha256"] != updated["corpus_sha256"]
    assert manifest["training_dataset_sha256"] != updated["training_dataset_sha256"]
    assert manifest["evaluation_dataset_sha256"] == updated["evaluation_dataset_sha256"]


def test_verify_frozen_corpus_returns_exact_committed_corpus(corpus):
    assert verify_frozen_corpus() == corpus


def test_verify_frozen_corpus_refuses_changed_target(corpus, tmp_path):
    data = corpus.model_dump(mode="json")
    data["examples"][0]["assistant_target"]["remember"] = "Which detail was visible?"
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="^invalid_or_changed_frozen_corpus$"):
        verify_frozen_corpus(path)


def test_verify_frozen_corpus_refuses_changed_application_prompt(monkeypatch):
    from onelap import evaluation

    original = evaluation.messages_for

    def altered(case):
        messages = original(case)
        messages[0]["content"] += " An unreviewed prompt change."
        return messages

    monkeypatch.setattr(evaluation, "messages_for", altered)
    with pytest.raises(ValueError, match="^invalid_or_changed_frozen_corpus$"):
        verify_frozen_corpus()


def test_verify_frozen_corpus_errors_never_echo_invalid_payload(tmp_path, capsys):
    private_marker = "fictional-private-marker-for-exception-test"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps({"unknown": private_marker}), encoding="utf-8")
    with pytest.raises(ValueError) as failure:
        verify_frozen_corpus(path)
    assert str(failure.value) == "invalid_or_changed_frozen_corpus"
    assert private_marker not in str(failure.value)
    assert failure.value.__suppress_context__ is True
    assert main(["--corpus", str(path)]) == 2
    assert private_marker not in capsys.readouterr().out


def test_verify_frozen_corpus_rejects_duplicate_manifest_keys(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"version":1,"version":1}', encoding="utf-8")
    with pytest.raises(ValueError, match="^invalid_or_changed_frozen_corpus$"):
        verify_frozen_corpus(manifest=path)


def test_cli_is_offline_and_does_not_load_environment(corpus, monkeypatch, capsys):
    def prohibited(*args, **kwargs):
        pytest.fail("Corpus validation must not make a network connection")

    monkeypatch.setattr(socket, "create_connection", prohibited)
    monkeypatch.setattr(socket.socket, "connect", prohibited)
    assert main([]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["counts"] == {"train": 100, "dev": 20, "heldout": 30}
    assert report["human_reviewed"] is False
    assert report["hosted_requests"] == 0


def test_cli_fails_closed_for_changed_manifest(tmp_path, capsys):
    changed = json.loads(DEFAULT_MANIFEST.read_text("utf-8"))
    changed["corpus_sha256"] = "0" * 64
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(changed), encoding="utf-8")
    assert main(["--manifest", str(path)]) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "invalid_corpus_or_manifest"


def test_cli_rejects_non_json_corpus_without_traceback(capsys):
    assert main(["--corpus", "never-read.txt"]) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "invalid_corpus_or_manifest"


def test_loader_rejects_duplicate_keys_and_unknown_fields(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"version":1,"version":1}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_corpus(path)
    data = json.loads(DEFAULT_CORPUS.read_text("utf-8"))
    data["user_location"] = "This field must not be accepted."
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValidationError):
        load_corpus(path)
