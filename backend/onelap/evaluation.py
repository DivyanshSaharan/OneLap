"""Validate and replay synthetic evaluation artifacts. No hosted execution path."""

import argparse
import hashlib
import json
import platform
import statistics
from collections import Counter
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from .errors import MissionError
from .evaluation_models import EvaluationCase, EvaluationDataset, EvaluationRun, SeedObservation
from .followup import _parse_output, validate_output
from .followup import build_messages as followup_messages
from .journal_models import JournalRecord, MissionSnapshot, OutingInput
from .models import GenerationIdentity
from .policy import validate_plan
from .prompts import build_messages as mission_messages
from .provider import MAX_OUTPUT_TOKENS, parse_plan
from .provider_json import unique_keys

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT / "datasets" / "onelap-seed-v1.json"
METHOD_FILES = (
    "evaluation.py",
    "evaluation_models.py",
    "followup.py",
    "journal_models.py",
    "models.py",
    "policy.py",
    "prompts.py",
    "provider.py",
    "provider_json.py",
)
DECODING = {
    "temperature": 0.2,
    "max_tokens": MAX_OUTPUT_TOKENS,
    "thinking": False,
    "num_samples": 1,
    "stop": ["<|im_end|>"],
}


class EvaluationError(Exception):
    pass


def digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def output_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def method_digest() -> str:
    return digest(
        {name: Path(__file__).with_name(name).read_text("utf-8") for name in METHOD_FILES}
    )


def software_versions() -> dict[str, str]:
    versions = {"python": platform.python_version()}
    for package in ("tinker", "transformers"):
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = "not-installed"
    return versions


def load_artifact(path: Path, model):
    if path.resolve().suffix.lower() != ".json":
        raise EvaluationError("artifacts_must_be_json_files")
    if path.stat().st_size > 4_194_304:
        raise EvaluationError("artifact_too_large")
    data = json.loads(path.read_text("utf-8"), object_pairs_hook=unique_keys)
    return model.model_validate(data)


def cases_for(dataset: EvaluationDataset, split: str) -> list[EvaluationCase]:
    cases = [case for case in dataset.cases if dataset.families[case.family] == split]
    if not cases:
        raise EvaluationError("empty_split")
    return sorted(cases, key=lambda case: case.id)


def _record(seed: SeedObservation, key: str, position: int) -> JournalRecord:
    date = f"2026-10-{10 - position:02d}T12:00:00.000Z"
    entry = OutingInput(
        id=str(uuid5(NAMESPACE_URL, "onelap-evaluation-entry-" + key)),
        mission=MissionSnapshot(
            id=str(uuid5(NAMESPACE_URL, "onelap-evaluation-mission-" + key)),
            mission=seed.mission,
            generation=GenerationIdentity(),
            safety_note="Skip if unsuitable. This fictional case does not assess safety.",
        ),
        outcome="completed",
        observation=seed.observation,
        feedback=seed.feedback,
        recorded_at=date,
    )
    return JournalRecord(entry=entry, received_at=date)


def records_for(case: EvaluationCase) -> tuple[JournalRecord, list[JournalRecord]]:
    if case.source is None:
        raise EvaluationError("missing_source")
    return _record(case.source, case.id, 0), [
        _record(seed, f"{case.id}-context-{index}", index + 1)
        for index, seed in enumerate(case.context)
    ]


def messages_for(case: EvaluationCase) -> list[dict[str, str]]:
    if case.workflow == "mission":
        return mission_messages(case.request)
    return followup_messages(*records_for(case))


def input_digest(case: EvaluationCase) -> str:
    return digest({"case": case.model_dump(mode="json"), "messages": messages_for(case)})


def prepare(dataset: EvaluationDataset, split: str) -> dict:
    cases = cases_for(dataset, split)
    return {
        "notice": "Synthetic inputs only. No requests made. Template is not a model run.",
        "dataset_review_status": dataset.review_status,
        "inputs": [
            {
                "case_id": case.id,
                "family": case.family,
                "workflow": case.workflow,
                "input_sha256": input_digest(case),
                "messages": messages_for(case),
                "semantic_checks": case.semantic_checks,
            }
            for case in cases
        ],
        "run_template": {
            "version": 1,
            "run_id": "replace-with-run-id",
            "origin": "fixture",
            "captured_at": "2026-10-10T12:00:00.000Z",
            "dataset_sha256": digest(dataset.model_dump(mode="json")),
            "method_sha256": method_digest(),
            "split": split,
            "identity": {
                "provider": "tinker",
                "model": "Qwen/Qwen3.5-4B",
                "target": "base",
                "checkpoint": None,
                "training_dataset_sha256": None,
            },
            "decoding": {**DECODING, "stop": list(DECODING["stop"])},
            "conditions": {
                "latency_scope": "provider_call_including_setup",
                "client_lifecycle": "shared_client",
                "execution": "serial",
                "software_versions": software_versions(),
            },
            "results": [
                {
                    "case_id": case.id,
                    "input_sha256": input_digest(case),
                    "raw_output": None,
                    "error": "not_run",
                    "latency_ms": None,
                    "input_tokens": None,
                    "output_tokens": None,
                    "estimated_reserved_usd": None,
                    "review": None,
                }
                for case in cases
            ],
        },
    }


def _check_output(case: EvaluationCase, text: str | None) -> dict:
    checks = {"schema": False, "constraints": None, "policy": None, "repetition": None}
    if text is None:
        return {"checks": checks, "accepted": False, "error": "missing_output"}
    try:
        plan = parse_plan(text) if case.workflow == "mission" else _parse_output(text).mission
        checks["schema"] = True
        checks["constraints"] = all(
            getattr(plan, name) == getattr(case.request, name)
            for name in ("minutes", "setting", "conditions", "focus")
        )
        if not checks["constraints"]:
            raise MissionError("mission_constraint_mismatch")
        checks["policy"] = False
        validate_plan(plan, case.request)
        checks["policy"] = True
        if case.workflow == "followup":
            checks["repetition"] = False
            validate_output(text, *records_for(case))
            checks["repetition"] = True
        return {"checks": checks, "accepted": True, "error": None}
    except MissionError as error:
        return {"checks": checks, "accepted": False, "error": error.code}


def _rate(values: list[bool | None], total: int) -> dict:
    checked = [value for value in values if value is not None]
    passed = sum(checked)
    return {
        "passed": passed,
        "checked": len(checked),
        "total_cases": total,
        "rate_among_checked": passed / len(checked) if checked else None,
    }


def _measure(values: list[int | float | None], total: int) -> dict:
    known = [value for value in values if value is not None]
    return {
        "measured_cases": len(known),
        "total_cases": total,
        "sum": sum(known) if known else None,
        "mean": statistics.mean(known) if known else None,
        "median": statistics.median(known) if known else None,
    }


def score(dataset: EvaluationDataset, run: EvaluationRun) -> dict:
    if run.dataset_sha256 != digest(dataset.model_dump(mode="json")):
        raise EvaluationError("dataset_hash_mismatch")
    if run.method_sha256 != method_digest():
        raise EvaluationError("method_hash_mismatch")
    cases = cases_for(dataset, run.split)
    by_id = {result.case_id: result for result in run.results}
    if len(by_id) != len(run.results) or set(by_id) != {case.id for case in cases}:
        raise EvaluationError("results_must_cover_every_case_once")
    rows = []
    for case in cases:
        result = by_id[case.id]
        if result.input_sha256 != input_digest(case):
            raise EvaluationError("input_hash_mismatch")
        row = _check_output(case, result.raw_output)
        row.update(case_id=case.id, workflow=case.workflow)
        if result.error is not None:
            row["error"] = result.error
        row["human_review"] = None
        if result.review is not None:
            if result.raw_output is None or result.review.output_sha256 != output_digest(
                result.raw_output
            ):
                raise EvaluationError("review_output_hash_mismatch")
            if not row["checks"]["schema"]:
                raise EvaluationError("semantic_review_requires_parsed_output")
            if (result.review.adaptation is None) != (case.workflow == "mission"):
                raise EvaluationError("review_adaptation_workflow_mismatch")
            row["human_review"] = result.review.model_dump(exclude={"rationale", "output_sha256"})
        rows.append(row)
    total = len(cases)
    pending = sum(row["checks"]["schema"] and row["human_review"] is None for row in rows)
    not_run = sum(result.error == "not_run" for result in run.results)
    status = "complete_self_attested_capture"
    if run.origin == "fixture":
        status = "fixture_not_model_evidence"
    elif dataset.review_status != "human_reviewed":
        status = "dataset_review_pending"
    elif not_run:
        status = "incomplete_capture"
    elif pending:
        status = "semantic_review_pending"
    semantic = {}
    for dimension in ("grounding", "suitability", "screen_light", "adaptation"):
        scores = [
            row["human_review"][dimension]
            for row in rows
            if row["human_review"] is not None and row["human_review"][dimension] is not None
        ]
        eligible = (
            sum(case.workflow == "followup" for case in cases)
            if dimension == "adaptation"
            else total
        )
        semantic[dimension] = {
            "reviewed": len(scores),
            "eligible_cases": eligible,
            "points": sum(scores),
            "possible_reviewed_points": 2 * len(scores),
            "mean_0_to_2": statistics.mean(scores) if scores else None,
            "fully_meets_rubric": scores.count(2),
        }
    return {
        "version": 1,
        "run_id": run.run_id,
        "origin": run.origin,
        "evidence_status": status,
        "capture_identity_is_self_attested": True,
        "dataset_sha256": run.dataset_sha256,
        "method_sha256": run.method_sha256,
        "split": run.split,
        "identity": run.identity.model_dump(),
        "decoding": run.decoding.model_dump(),
        "conditions": run.conditions.model_dump(),
        "total_cases": total,
        "not_run": not_run,
        "application_acceptance": _rate([row["accepted"] for row in rows], total),
        "deterministic": {
            name: _rate([row["checks"][name] for row in rows], total)
            for name in ("schema", "constraints", "policy", "repetition")
        },
        "failures": dict(Counter(row["error"] for row in rows if row["error"] is not None)),
        "human_review_pending": pending,
        "by_workflow": {
            workflow: {
                "application_acceptance": _rate(
                    [row["accepted"] for row in rows if row["workflow"] == workflow],
                    sum(row["workflow"] == workflow for row in rows),
                ),
                "human_review_pending": sum(
                    row["workflow"] == workflow
                    and row["checks"]["schema"]
                    and row["human_review"] is None
                    for row in rows
                ),
            }
            for workflow in ("mission", "followup")
        },
        "semantic": semantic,
        "measurements": {
            name: _measure([getattr(result, name) for result in run.results], total)
            for name in ("latency_ms", "input_tokens", "output_tokens", "estimated_reserved_usd")
        },
        "cases": rows,
        "limitations": [
            "Application acceptance is not semantic accuracy or a safety guarantee.",
            "Synthetic cases are not field evidence. Review and capture identity are attestations.",
            "Missing measurements are not zero; reservations are estimates, not invoices.",
            "Keyword policy and normalized exact-repeat checks miss paraphrases.",
            "No confidence intervals, statistical significance or automatic promotion.",
        ],
    }


def compare(dataset: EvaluationDataset, baseline: EvaluationRun, candidate: EvaluationRun) -> dict:
    before, after = score(dataset, baseline), score(dataset, candidate)
    if baseline.origin != "provider_capture" or candidate.origin != "provider_capture":
        raise EvaluationError("fixtures_cannot_support_model_comparison")
    if baseline.split != "heldout" or candidate.split != "heldout":
        raise EvaluationError("comparison_requires_heldout_split")
    if any(
        report["evidence_status"] != "complete_self_attested_capture" for report in (before, after)
    ):
        raise EvaluationError("comparison_requires_complete_reviewed_captures")
    if baseline.run_id == candidate.run_id:
        raise EvaluationError("comparison_requires_distinct_runs")
    if baseline.identity.target != "base" or candidate.identity.target != "adapter":
        raise EvaluationError("comparison_requires_base_and_adapter")
    if baseline.decoding != candidate.decoding:
        raise EvaluationError("decoding_mismatch")
    if baseline.conditions != candidate.conditions:
        raise EvaluationError("run_conditions_mismatch")
    if "not-installed" in baseline.conditions.software_versions.values():
        raise EvaluationError("software_versions_incomplete")
    metrics = {
        "application_acceptance": {
            "baseline_passed": before["application_acceptance"]["passed"],
            "candidate_passed": after["application_acceptance"]["passed"],
            "total_cases": before["total_cases"],
        }
    }
    for name in ("grounding", "suitability", "screen_light", "adaptation"):
        left, right = before["semantic"][name], after["semantic"][name]
        metrics[name] = {"baseline": left, "candidate": right}
        # Failed/malformed outputs receive zero rubric points in this coverage-aware rate.
        eligible = left["eligible_cases"]
        metrics[name]["fully_meets_rubric_delta_over_all_eligible"] = (
            (right["fully_meets_rubric"] - left["fully_meets_rubric"]) / eligible
            if eligible
            else None
        )
    measurements = {}
    for name in before["measurements"]:
        left, right = before["measurements"][name], after["measurements"][name]
        complete = left["measured_cases"] == right["measured_cases"] == before["total_cases"]
        measurements[name] = {
            "baseline": left,
            "candidate": right,
            "mean_delta": right["mean"] - left["mean"] if complete else None,
        }
    return {
        "baseline_run_id": baseline.run_id,
        "candidate_run_id": candidate.run_id,
        "dataset_sha256": baseline.dataset_sha256,
        "method_sha256": baseline.method_sha256,
        "baseline_identity": baseline.identity.model_dump(),
        "candidate_identity": candidate.identity.model_dump(),
        "decoding": baseline.decoding.model_dump(),
        "conditions": baseline.conditions.model_dump(),
        "metrics": metrics,
        "by_workflow": {
            name: {"baseline": before["by_workflow"][name], "candidate": after["by_workflow"][name]}
            for name in ("mission", "followup")
        },
        "measurements": measurements,
        "promotion": "human_decision_required",
        "limitations": before["limitations"],
    }


def write_artifact(path: Path, data: dict) -> None:
    destination = path.resolve()
    if not destination.is_relative_to(ROOT.resolve() / ".data" / "evaluation"):
        raise EvaluationError("output_must_be_under_ignored_evaluation_directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as file:
        file.write(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate")
    prepare_parser = commands.add_parser("prepare")
    prepare_parser.add_argument("--split", choices=("dev", "heldout"), default="dev")
    prepare_parser.add_argument("--output", type=Path, required=True)
    score_parser = commands.add_parser("score")
    score_parser.add_argument("--run", type=Path, required=True)
    score_parser.add_argument("--output", type=Path, required=True)
    comparison = commands.add_parser("compare")
    comparison.add_argument("--baseline", type=Path, required=True)
    comparison.add_argument("--candidate", type=Path, required=True)
    comparison.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        dataset = load_artifact(args.dataset, EvaluationDataset)
        if args.command == "validate":
            print(
                json.dumps(
                    {
                        "dataset_sha256": digest(dataset.model_dump(mode="json")),
                        "method_sha256": method_digest(),
                        "review_status": dataset.review_status,
                        "cases_by_split": dict(
                            Counter(dataset.families[case.family] for case in dataset.cases)
                        ),
                        "hosted_requests": 0,
                    },
                    indent=2,
                )
            )
            return 0
        if args.command == "prepare":
            data = prepare(dataset, args.split)
        elif args.command == "score":
            data = score(dataset, load_artifact(args.run, EvaluationRun))
        else:
            data = compare(
                dataset,
                load_artifact(args.baseline, EvaluationRun),
                load_artifact(args.candidate, EvaluationRun),
            )
        write_artifact(args.output, data)
        print(json.dumps({"artifact": str(args.output), "hosted_requests": 0}))
        return 0
    except EvaluationError as error:
        print(json.dumps({"error": str(error)}))
    except (OSError, ValueError, TypeError, RecursionError):
        # Validation exceptions may include private artifact contents: never echo them.
        print(json.dumps({"error": "invalid_or_unreadable_artifact"}))
    return 2
