import builtins
import json
import socket
from copy import deepcopy

import pytest
from onelap import evaluation
from onelap.evaluation import (
    DEFAULT_DATASET,
    EvaluationError,
    cases_for,
    compare,
    digest,
    load_artifact,
    messages_for,
    output_digest,
    prepare,
    records_for,
    score,
)
from onelap.evaluation_models import EvaluationDataset, EvaluationRun
from onelap.followup import validate_output
from pydantic import ValidationError


@pytest.fixture
def dataset():
    return load_artifact(DEFAULT_DATASET, EvaluationDataset)


def valid_output(case):
    plan = {
        "title": "Notice an optional small detail",
        "instruction": "In your familiar area, notice one small change if you find one.",
        "remember": "What detail stayed with you? Skip if the task does not fit.",
        **case.request.model_dump(),
        "requires_camera": False,
        "phone_use": "none_during_outing",
    }
    if case.workflow == "followup":
        return json.dumps(
            {"reflection": "Your note describes a detail you noticed.", "mission": plan}
        )
    return json.dumps(plan)


def bundle(dataset, split="dev"):
    data = prepare(dataset, split)["run_template"]
    for case, result in zip(cases_for(dataset, split), data["results"], strict=True):
        result.update(raw_output=valid_output(case), error=None)
    return data


def reviewed_bundle(dataset, *, adapter=False):
    data = bundle(dataset, "heldout")
    data.update(origin="provider_capture", run_id="candidate" if adapter else "baseline")
    if adapter:
        data["identity"].update(
            target="adapter",
            checkpoint="tinker://fictional-checkpoint/sampler_weights/step-1",
            training_dataset_sha256="a" * 64,
        )
    for case, result in zip(cases_for(dataset, "heldout"), data["results"], strict=True):
        result.update(
            latency_ms=100.0,
            input_tokens=100,
            output_tokens=80,
            estimated_reserved_usd=0.001,
            review={
                "rubric": "onelap-human-v1",
                "reviewer": "fictional-test-reviewer",
                "output_sha256": output_digest(result["raw_output"]),
                "grounding": 2,
                "suitability": 2,
                "screen_light": 2,
                "adaptation": 2 if case.workflow == "followup" else None,
                "rationale": "Fictional test review, not actual model evidence.",
            },
        )
    return data


def reviewed_dataset(dataset):
    return EvaluationDataset.model_validate(
        {**dataset.model_dump(), "review_status": "human_reviewed", "reviewer": "test-reviewer"}
    )


def test_seed_split_is_small_synthetic_and_unreviewed(dataset):
    assert dataset.provenance == "synthetic_assistant_authored"
    assert dataset.review_status == "unreviewed"
    assert {split: len(cases_for(dataset, split)) for split in ("train", "dev", "heldout")} == {
        "train": 6,
        "dev": 6,
        "heldout": 6,
    }
    assert len(dataset.families) == 9
    assert all(
        sum(case.family == family for case in dataset.cases) == 2 for family in dataset.families
    )


@pytest.mark.parametrize(
    "change", ["unknown_family", "duplicate_id", "missing_family", "duplicate_input"]
)
def test_dataset_rejects_split_and_duplicate_errors(dataset, change):
    data = dataset.model_dump()
    if change == "unknown_family":
        data["cases"][0]["family"] = "unassigned"
    elif change == "duplicate_id":
        data["cases"][1]["id"] = data["cases"][0]["id"]
    elif change == "missing_family":
        data["families"]["unused-family"] = "heldout"
    else:
        data["cases"][1] = {
            **data["cases"][0],
            "id": "new-id",
            "semantic_checks": ["Changed rubric."],
        }
    with pytest.raises(ValidationError):
        EvaluationDataset.model_validate(data)


@pytest.mark.parametrize(
    "change", ["source_missing", "source_changed", "mission_context", "reviewer_missing"]
)
def test_dataset_rejects_unsupported_shapes(dataset, change):
    data = dataset.model_dump()
    if change == "source_missing":
        data["cases"][2]["source"] = None
    elif change == "source_changed":
        data["cases"][2]["source"]["mission"]["focus"] = "sounds"
    elif change == "mission_context":
        data["cases"][0]["context"] = [data["cases"][2]["source"]]
    else:
        data["review_status"] = "human_reviewed"
    with pytest.raises(ValidationError):
        EvaluationDataset.model_validate(data)


def test_preparation_uses_exact_app_prompts_and_synthetic_prior_records(dataset):
    prepared = prepare(dataset, "dev")
    assert prepared["run_template"]["origin"] == "fixture"
    for case, item in zip(cases_for(dataset, "dev"), prepared["inputs"], strict=True):
        assert item["messages"] == messages_for(case)
        assert item["input_sha256"] == evaluation.input_digest(case)
    context_case = next(case for case in cases_for(dataset, "heldout") if case.context)
    source, context = records_for(context_case)
    assert all(record.entry.recorded_at < source.entry.recorded_at for record in context)
    assert "recorded_at" not in json.loads(messages_for(context_case)[1]["content"])


def test_template_cannot_be_mistaken_for_a_completed_run(dataset):
    report = score(dataset, EvaluationRun.model_validate(prepare(dataset, "dev")["run_template"]))
    assert report["evidence_status"] == "fixture_not_model_evidence"
    assert report["not_run"] == 6
    assert report["application_acceptance"]["passed"] == 0
    assert report["failures"] == {"not_run": 6}


def test_fixture_passes_are_not_model_accuracy_or_human_scores(dataset):
    report = score(dataset, EvaluationRun.model_validate(bundle(dataset)))
    assert report["evidence_status"] == "fixture_not_model_evidence"
    assert report["application_acceptance"] == {
        "passed": 6,
        "checked": 6,
        "total_cases": 6,
        "rate_among_checked": 1.0,
    }
    assert report["human_review_pending"] == 6
    assert report["by_workflow"]["mission"]["application_acceptance"]["total_cases"] == 2
    assert report["by_workflow"]["followup"]["application_acceptance"]["total_cases"] == 4
    assert report["semantic"]["grounding"]["mean_0_to_2"] is None
    assert report["measurements"]["latency_ms"]["sum"] is None
    assert report["measurements"]["output_tokens"]["measured_cases"] == 0
    assert "raw_output" not in json.dumps(report)


def test_failures_remain_in_denominator_and_checks_show_coverage(dataset):
    data = bundle(dataset)
    data["results"][0].update(raw_output=None, error="timeout", latency_ms=45000.0)
    data["results"][1]["raw_output"] = "not JSON"
    output = json.loads(data["results"][4]["raw_output"])
    output["mission"]["focus"] = "general"
    data["results"][4]["raw_output"] = json.dumps(output)
    report = score(dataset, EvaluationRun.model_validate(data))
    assert report["application_acceptance"]["passed"] == 3
    assert report["application_acceptance"]["total_cases"] == 6
    assert report["deterministic"]["schema"]["passed"] == 4
    assert report["deterministic"]["constraints"]["checked"] == 4
    assert report["deterministic"]["constraints"]["passed"] == 3
    assert report["deterministic"]["policy"]["checked"] == 3
    assert report["measurements"]["latency_ms"]["mean"] == 45000.0
    assert report["measurements"]["latency_ms"]["measured_cases"] == 1
    assert report["failures"]["timeout"] == 1


@pytest.mark.parametrize(
    "bad", ["prohibited", "duplicate_json_key", "repeated", "overlong", "near_copy"]
)
def test_replay_uses_application_checks_including_known_limitations(dataset, bad):
    data = bundle(dataset)
    case = next(case for case in cases_for(dataset, "dev") if case.workflow == "followup")
    result = next(row for row in data["results"] if row["case_id"] == case.id)
    output = json.loads(result["raw_output"])
    expected = "mission_policy_rejected"
    if bad == "prohibited":
        output["mission"]["instruction"] = "Use a camera to photograph a surface."
    elif bad == "duplicate_json_key":
        result["raw_output"] = '{"reflection":"a","reflection":"b","mission":{}}'
        expected = "invalid_model_output"
    elif bad == "repeated":
        output["mission"]["instruction"] = case.source.mission.instruction.upper()
        expected = "followup_repeated_mission"
    elif bad == "near_copy":
        output["mission"]["instruction"] = case.source.mission.instruction + " If appropriate."
        expected = None  # Semantic novelty needs a person, not exact string agreement.
    else:
        result["raw_output"] = "x" * 9000
        expected = "invalid_model_output"
    if bad not in ("duplicate_json_key", "overlong"):
        result["raw_output"] = json.dumps(output)
    report = score(dataset, EvaluationRun.model_validate(data))
    row = next(row for row in report["cases"] if row["case_id"] == case.id)
    assert row["error"] == expected
    if expected is None:
        assert validate_output(result["raw_output"], *records_for(case))
    else:
        assert row["accepted"] is False


@pytest.mark.parametrize(
    "change,code",
    [
        ("dataset", "dataset_hash_mismatch"),
        ("method", "method_hash_mismatch"),
        ("input", "input_hash_mismatch"),
        ("missing", "results_must_cover_every_case_once"),
        ("duplicate", "results_must_cover_every_case_once"),
        ("extra", "results_must_cover_every_case_once"),
    ],
)
def test_score_refuses_mismatched_or_selected_only_results(dataset, change, code):
    data = bundle(dataset)
    if change in ("dataset", "method"):
        data[change + "_sha256"] = "0" * 64
    elif change == "input":
        data["results"][0]["input_sha256"] = "0" * 64
    elif change == "missing":
        data["results"].pop()
    elif change == "duplicate":
        data["results"].append(deepcopy(data["results"][0]))
    else:
        data["results"][0]["case_id"] = "unknown-case"
    with pytest.raises(EvaluationError, match=code):
        score(dataset, EvaluationRun.model_validate(data))


def test_order_does_not_change_report_and_rubric_hash_binds_exact_reply(dataset):
    reviewed = reviewed_dataset(dataset)
    data = reviewed_bundle(reviewed)
    original = score(reviewed, EvaluationRun.model_validate(data))
    data["results"].reverse()
    assert score(reviewed, EvaluationRun.model_validate(data)) == original
    data["results"][0]["raw_output"] += " "
    with pytest.raises(EvaluationError, match="review_output_hash_mismatch"):
        score(reviewed, EvaluationRun.model_validate(data))


@pytest.mark.parametrize(
    "change",
    [
        "base_checkpoint",
        "adapter_missing",
        "nan",
        "bool_tokens",
        "two_outputs",
        "both_error_and_output",
        "missing_both",
    ],
)
def test_artifact_metadata_is_strict(dataset, change):
    data = bundle(dataset)
    if change == "base_checkpoint":
        data["identity"]["checkpoint"] = "tinker://test"
    elif change == "adapter_missing":
        data["identity"]["target"] = "adapter"
    elif change == "nan":
        data["results"][0]["latency_ms"] = float("nan")
    elif change == "bool_tokens":
        data["results"][0]["output_tokens"] = True
    elif change == "two_outputs":
        data["decoding"]["num_samples"] = 2
    elif change == "both_error_and_output":
        data["results"][0]["error"] = "timeout"
    else:
        data["results"][0]["raw_output"] = None
    with pytest.raises(ValidationError):
        EvaluationRun.model_validate(data)


def test_matched_comparison_has_no_automatic_promotion_and_counts_failed_cases(dataset):
    dataset = reviewed_dataset(dataset)
    baseline, candidate = reviewed_bundle(dataset), reviewed_bundle(dataset, adapter=True)
    baseline["results"][0].update(raw_output=None, error="timeout", review=None)
    candidate["results"][1]["review"]["grounding"] = 1
    report = compare(
        dataset, EvaluationRun.model_validate(baseline), EvaluationRun.model_validate(candidate)
    )
    assert report["promotion"] == "human_decision_required"
    assert report["metrics"]["application_acceptance"]["baseline_passed"] == 5
    assert report["metrics"]["application_acceptance"]["candidate_passed"] == 6
    # One recovered output and one weaker review are a wash for full grounding marks.
    assert report["metrics"]["grounding"]["fully_meets_rubric_delta_over_all_eligible"] == 0
    assert report["measurements"]["latency_ms"]["mean_delta"] == 0.0
    candidate["results"][1]["latency_ms"] = None
    partial = compare(
        dataset, EvaluationRun.model_validate(baseline), EvaluationRun.model_validate(candidate)
    )
    assert partial["measurements"]["latency_ms"]["mean_delta"] is None


@pytest.mark.parametrize(
    "change,code",
    [
        ("fixture", "fixtures_cannot_support_model_comparison"),
        ("dev", "comparison_requires_heldout_split"),
        ("unreviewed", "comparison_requires_complete_reviewed_captures"),
        ("pending", "comparison_requires_complete_reviewed_captures"),
        ("not_run", "comparison_requires_complete_reviewed_captures"),
        ("same_id", "comparison_requires_distinct_runs"),
        ("base_candidate", "comparison_requires_base_and_adapter"),
        ("decoding", "decoding_mismatch"),
        ("conditions", "run_conditions_mismatch"),
        ("missing_version", "software_versions_incomplete"),
    ],
)
def test_comparison_refuses_invalid_evidence(dataset, change, code):
    if change != "unreviewed":
        dataset = reviewed_dataset(dataset)
    before, after = reviewed_bundle(dataset), reviewed_bundle(dataset, adapter=True)
    if change == "fixture":
        after["origin"] = "fixture"
    elif change == "dev":
        before = bundle(dataset)
        after = deepcopy(before)
        before["origin"] = after["origin"] = "provider_capture"
    elif change == "pending":
        after["results"][0]["review"] = None
    elif change == "not_run":
        after["results"][0].update(error="not_run", raw_output=None, review=None)
    elif change == "same_id":
        after["run_id"] = before["run_id"]
    elif change == "base_candidate":
        after["identity"] = before["identity"]
    elif change == "decoding":
        after["decoding"]["temperature"] = 0.5
    elif change == "conditions":
        after["conditions"]["client_lifecycle"] = "cold_each_case"
    elif change == "missing_version":
        before["conditions"]["software_versions"]["tinker"] = "not-installed"
        after["conditions"]["software_versions"]["tinker"] = "not-installed"
    with pytest.raises(EvaluationError, match=code):
        compare(dataset, EvaluationRun.model_validate(before), EvaluationRun.model_validate(after))


def test_cli_never_imports_hosted_sdks_reads_secrets_or_connects(
    dataset, monkeypatch, tmp_path, capsys
):
    original_import, original_read = builtins.__import__, evaluation.Path.read_text

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"tinker", "pymongo", "sentry_sdk"}:
            pytest.fail("Evaluation must not initialize a provider SDK")
        return original_import(name, *args, **kwargs)

    def guarded_read(path, *args, **kwargs):
        assert not path.name.startswith(".env")
        return original_read(path, *args, **kwargs)

    def no_network(*args, **kwargs):
        pytest.fail("Evaluation must stay offline")

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(evaluation.Path, "read_text", guarded_read)
    monkeypatch.setattr(socket, "create_connection", no_network)
    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(evaluation, "ROOT", tmp_path)
    assert evaluation.main(["validate"]) == 0
    output = tmp_path / ".data" / "evaluation" / "dev.json"
    assert evaluation.main(["prepare", "--output", str(output)]) == 0
    assert json.loads(output.read_text("utf-8"))["run_template"]["origin"] == "fixture"
    assert '"hosted_requests": 0' in capsys.readouterr().out
    assert evaluation.main(["prepare", "--output", str(output)]) == 2


def test_cli_errors_do_not_echo_private_data_and_writes_stay_ignored(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(evaluation, "ROOT", tmp_path)
    bad = tmp_path / "private.json"
    bad.write_text('{"private":"fictional-private-sentinel"}', encoding="utf-8")
    assert evaluation.main(["--dataset", str(bad), "validate"]) == 2
    assert "fictional-private-sentinel" not in capsys.readouterr().out
    with pytest.raises(EvaluationError, match="output_must_be_under_ignored_evaluation_directory"):
        evaluation.write_artifact(tmp_path / "public.json", {})


def test_duplicate_keys_are_rejected_and_whitespace_does_not_change_dataset_hash(dataset, tmp_path):
    path = tmp_path / "data.json"
    path.write_text('{"version":1,"version":1}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_artifact(path, EvaluationDataset)
    path.write_text(json.dumps(dataset.model_dump(), indent=4), encoding="utf-8")
    assert digest(load_artifact(path, EvaluationDataset).model_dump()) == digest(
        dataset.model_dump()
    )


@pytest.mark.parametrize("change", ["bool_version", "bad_timestamp", "bool_samples"])
def test_version_timestamp_and_sample_primitives_are_strict(dataset, change):
    data = bundle(dataset)
    if change == "bool_version":
        data["version"] = True
    elif change == "bad_timestamp":
        data["captured_at"] = "2026-99-99T12:00:00.000Z"
    else:
        data["decoding"]["num_samples"] = True
    with pytest.raises(ValidationError):
        EvaluationRun.model_validate(data)


def test_prepare_templates_do_not_share_mutable_decoding(dataset):
    first = prepare(dataset, "dev")
    first["run_template"]["decoding"]["stop"].append("different-stop")
    first["run_template"]["decoding"]["num_samples"] = 2
    second = prepare(dataset, "dev")
    assert second["run_template"]["decoding"] == evaluation.DECODING


def test_artifact_loader_does_not_read_environment_files(tmp_path):
    path = tmp_path / ".env"
    path.write_text("FICTIONAL_KEY=private-sentinel", encoding="utf-8")
    with pytest.raises(EvaluationError, match="artifacts_must_be_json_files"):
        load_artifact(path, EvaluationDataset)


@pytest.mark.parametrize(
    "change,code",
    [
        ("mission_adaptation", "review_adaptation_workflow_mismatch"),
        ("followup_adaptation", "review_adaptation_workflow_mismatch"),
        ("malformed_review", "semantic_review_requires_parsed_output"),
    ],
)
def test_review_cannot_score_inapplicable_or_unparsed_output(dataset, change, code):
    dataset = reviewed_dataset(dataset)
    data = reviewed_bundle(dataset)
    workflow = "followup" if change == "followup_adaptation" else "mission"
    case = next(case for case in cases_for(dataset, "heldout") if case.workflow == workflow)
    row = next(row for row in data["results"] if row["case_id"] == case.id)
    if change == "malformed_review":
        row["raw_output"] = "invalid JSON"
        row["review"]["output_sha256"] = output_digest(row["raw_output"])
    else:
        row["review"]["adaptation"] = None if workflow == "followup" else 2
    with pytest.raises(EvaluationError, match=code):
        score(dataset, EvaluationRun.model_validate(data))


def test_cli_scores_fixture_artifacts_without_exposing_raw_output(dataset, tmp_path, monkeypatch):
    monkeypatch.setattr(evaluation, "ROOT", tmp_path)
    run = tmp_path / ".data" / "evaluation" / "fixture-run.json"
    run.parent.mkdir(parents=True)
    run.write_text(json.dumps(bundle(dataset)), encoding="utf-8")
    output = run.with_name("fixture-score.json")
    assert evaluation.main(["score", "--run", str(run), "--output", str(output)]) == 0
    report = json.loads(output.read_text("utf-8"))
    assert report["evidence_status"] == "fixture_not_model_evidence"
    assert "raw_output" not in json.dumps(report)
