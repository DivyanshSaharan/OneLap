"""Explicitly admitted synthetic captures; ordinary preview never creates a Tinker client."""

import argparse
import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path

from .budget import reservation
from .config import MODEL, ROOT
from .evaluation import (
    DECODING,
    cases_for,
    digest,
    input_digest,
    load_artifact,
    messages_for,
    method_digest,
    score,
    software_versions,
)
from .evaluation_models import CapturedResult, EvaluationRun, RunIdentity
from .experiment_budget import MAX_MICRODOLLARS, ExperimentBudget, ExperimentError

REPORT_ROOT = ROOT / ".data" / "experiments"
TOKENIZER_ROOT = ROOT / ".data/model-cache/hub/models--Qwen--Qwen3.5-4B/snapshots"


def load_tokenizer(path: Path | None = None):
    from transformers import AutoTokenizer

    if path is None:
        candidates = sorted(TOKENIZER_ROOT.glob("*/tokenizer.json"))
        if len(candidates) != 1:
            raise ExperimentError("specify_one_cached_tokenizer_snapshot")
        path = candidates[0].parent
    return AutoTokenizer.from_pretrained(str(path), local_files_only=True)


def encode(tokenizer, case):
    tokens = tokenizer.apply_chat_template(
        messages_for(case),
        tokenize=True,
        return_dict=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    if not tokens or len(tokens) > 4096:
        raise ExperimentError("input_token_limit")
    return tokens


def write_report(path: Path, data, *, replace=False):
    path = path.resolve()
    if not path.is_relative_to(REPORT_ROOT.resolve()) or path.suffix != ".json":
        raise ExperimentError("report_must_be_under_ignored_experiments_directory")
    if any(parent.is_symlink() or parent.is_junction() for parent in (path, *path.parents)):
        raise ExperimentError("report_path_must_not_redirect")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not replace:
        with path.open("x", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2, allow_nan=False)
            file.write("\n")
    else:
        temporary = path.with_suffix(".json.tmp")
        with temporary.open("x", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2, allow_nan=False)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)


class Sampler:
    def __init__(self, identity: RunIdentity):
        import tinker
        from tinker.lib.retry_handler import RetryConfig

        key = os.environ.get("TINKER_API_KEY", "")
        if not key:
            raise ExperimentError("provider_not_configured")
        self.service = tinker.ServiceClient(api_key=key)
        kwargs = (
            {"base_model": MODEL}
            if identity.target == "base"
            else {"model_path": identity.checkpoint}
        )
        self.client = self.service.create_sampling_client(
            **kwargs,
            retry_config=RetryConfig(enable_retry_logic=False, progress_timeout=60),
        )
        if self.client.get_base_model() != MODEL:
            raise ExperimentError("provider_model_mismatch")
        self.tokenizer = self.client.get_tokenizer()

    def sample(self, tokens):
        from tinker import types

        response = self.client.sample(
            prompt=types.ModelInput.from_ints(tokens),
            num_samples=1,
            sampling_params=types.SamplingParams(
                max_tokens=512,
                temperature=0.2,
                stop=["<|im_end|>"],
            ),
        ).result(timeout=90)
        output = response.sequences[0].tokens
        return self.tokenizer.decode(output, skip_special_tokens=True), len(output)

    def close(self, successful):
        self.service.close("success" if successful else "errored").result(timeout=30)


def capture(
    dataset, split, identity, run_id, output: Path, tokenizer, budget, sampler_factory=Sampler
):
    cases = cases_for(dataset, split)
    prepared = [(case, encode(tokenizer, case)) for case in cases]
    fingerprint = digest(
        {
            "dataset": digest(dataset.model_dump(mode="json")),
            "method": method_digest(),
            "split": split,
            "identity": identity.model_dump(),
            "decoding": DECODING,
        }
    )
    template = EvaluationRun(
        version=1,
        run_id=run_id,
        origin="provider_capture",
        captured_at=datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        dataset_sha256=digest(dataset.model_dump(mode="json")),
        method_sha256=method_digest(),
        split=split,
        identity=identity,
        decoding=DECODING,
        conditions={
            "latency_scope": "provider_call_including_setup",
            "client_lifecycle": "shared_client",
            "execution": "serial",
            "software_versions": software_versions(),
        },
        results=[
            CapturedResult(
                case_id=case.id,
                input_sha256=input_digest(case),
                raw_output=None,
                error="not_run",
                latency_ms=None,
                input_tokens=None,
                output_tokens=None,
                estimated_reserved_usd=None,
                review=None,
            )
            for case in cases
        ],
    )
    write_report(output, template.model_dump(mode="json"))
    budget.claim(run_id, fingerprint)
    sampler = None
    try:
        for index, (case, tokens) in enumerate(prepared):
            estimate = reservation(len(tokens), 512)
            budget.reserve(run_id, f"{run_id}:{case.id}", estimate)
            started = time.monotonic()
            row = template.results[index]
            row.input_tokens = len(tokens)
            row.estimated_reserved_usd = estimate / 1_000_000
            try:
                if sampler is None:
                    sampler = sampler_factory(identity)
                actual = encode(sampler.tokenizer, case)
                if actual != tokens:
                    raise ExperimentError("tokenizer_binding_mismatch")
                row.raw_output, row.output_tokens = sampler.sample(tokens)
                row.error = None
            except TimeoutError:
                row.error = "timeout"
            except Exception:
                row.error = "provider_failed"
            row.latency_ms = (time.monotonic() - started) * 1000
            write_report(output, template.model_dump(mode="json"), replace=True)
            print(
                json.dumps(
                    {
                        "case": case.id,
                        "target": identity.target,
                        "error": row.error,
                        "completed": index + 1,
                        "total": len(cases),
                    }
                ),
                flush=True,
            )
            if row.error is not None:
                raise ExperimentError("capture_stopped_after_provider_failure_no_retry")
        budget.finish(run_id, "completed")
    except BaseException:
        budget.finish(run_id, "failed")
        raise
    finally:
        if sampler is not None and hasattr(sampler, "close"):
            try:
                sampler.close(all(row.error is None for row in template.results))
            except Exception:
                pass
    summary = score(dataset, template)
    write_report(output.with_name(output.stem + "-score.json"), summary)
    return summary


def deterministic_comparison(dataset, baseline, candidate):
    """Paired application metrics only; does not bypass the human-semantic comparison gate."""
    if (baseline.origin, candidate.origin) != ("provider_capture", "provider_capture"):
        raise ExperimentError("fixtures_are_not_model_evidence")
    if baseline.identity.target != "base" or candidate.identity.target != "adapter":
        raise ExperimentError("comparison_requires_base_and_adapter")
    if baseline.run_id == candidate.run_id or baseline.split != candidate.split:
        raise ExperimentError("comparison_requires_distinct_matched_runs")
    if baseline.split != "heldout" or baseline.decoding != candidate.decoding:
        raise ExperimentError("heldout_and_identical_decoding_required")
    if baseline.conditions != candidate.conditions:
        raise ExperimentError("run_conditions_mismatch")
    before, after = score(dataset, baseline), score(dataset, candidate)
    if before["not_run"] or after["not_run"]:
        raise ExperimentError("comparison_requires_complete_attempts")
    return {
        "dataset_sha256": baseline.dataset_sha256,
        "method_sha256": baseline.method_sha256,
        "total_cases": before["total_cases"],
        "application_acceptance": {
            "baseline": before["application_acceptance"],
            "candidate": after["application_acceptance"],
        },
        "deterministic": {
            key: {
                "baseline": before["deterministic"][key],
                "candidate": after["deterministic"][key],
            }
            for key in before["deterministic"]
        },
        "failures": {"baseline": before["failures"], "candidate": after["failures"]},
        "measurements": {"baseline": before["measurements"], "candidate": after["measurements"]},
        "semantic_review": "human_review_pending",
        "promotion": "not_automatic",
        "limitations": before["limitations"],
    }


def main(argv=None):
    from .training_data import DEFAULT_CORPUS, evaluation_dataset, load_corpus, verify_frozen_corpus

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--tokenizer", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("preview")
    live = commands.add_parser("capture")
    live.add_argument("--live", action="store_true")
    live.add_argument("--ack-agent-reviewed-synthetic", action="store_true")
    live.add_argument("--ack-sdk-retries", action="store_true")
    live.add_argument("--split", choices=("dev", "heldout"), required=True)
    live.add_argument("--target", choices=("base", "adapter"), required=True)
    live.add_argument("--run-id", required=True)
    live.add_argument("--output", type=Path, required=True)
    live.add_argument("--checkpoint-receipt", type=Path)
    comparison = commands.add_parser("compare-checks")
    comparison.add_argument("--baseline", type=Path, required=True)
    comparison.add_argument("--candidate", type=Path, required=True)
    comparison.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        corpus = load_corpus(args.corpus)
        dataset = evaluation_dataset(corpus)
        if args.command == "compare-checks":
            result = deterministic_comparison(
                dataset,
                load_artifact(args.baseline, EvaluationRun),
                load_artifact(args.candidate, EvaluationRun),
            )
            write_report(args.output, result)
            print(json.dumps(result, indent=2))
            return 0
        tokenizer = load_tokenizer(args.tokenizer)
        if args.command == "preview":
            result = {
                "hosted_requests": 0,
                "new_pilot_cap_usd": MAX_MICRODOLLARS / 1_000_000,
                "dataset_review": corpus.review_status,
                "splits": {},
            }
            for split in ("dev", "heldout"):
                counts = [len(encode(tokenizer, case)) for case in cases_for(dataset, split)]
                result["splits"][split] = {
                    "cases": len(counts),
                    "input_tokens": sum(counts),
                    "per_arm_reserved_usd": sum(reservation(count, 512) for count in counts)
                    / 1_000_000,
                }
            print(json.dumps(result, indent=2))
            return 0
        if not (args.live and args.ack_agent_reviewed_synthetic and args.ack_sdk_retries):
            raise ExperimentError(
                "live_capture_requires_explicit_synthetic_and_retry_acknowledgement"
            )
        if re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", args.run_id) is None:
            raise ExperimentError("invalid_run_id")
        corpus = verify_frozen_corpus(args.corpus)
        dataset = evaluation_dataset(corpus)
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env", override=False)
        identity = RunIdentity(
            provider="tinker",
            model=MODEL,
            target="base",
            checkpoint=None,
            training_dataset_sha256=None,
        )
        if args.target == "adapter":
            from .training import load_receipt

            receipt = load_receipt(args.checkpoint_receipt, corpus)
            identity = RunIdentity(
                provider="tinker",
                model=MODEL,
                target="adapter",
                checkpoint=receipt["checkpoint"],
                training_dataset_sha256=receipt["training_dataset_sha256"],
            )
        result = capture(
            dataset,
            args.split,
            identity,
            args.run_id,
            args.output,
            tokenizer,
            ExperimentBudget(REPORT_ROOT),
        )
        print(
            json.dumps(
                {
                    "application_acceptance": result["application_acceptance"],
                    "semantic_review": "human_review_pending",
                },
                indent=2,
            )
        )
        return 0
    except Exception as error:
        code = str(error) if isinstance(error, ExperimentError) else "invalid_or_failed_experiment"
        print(json.dumps({"error": code}), flush=True)
        return 2
