"""One explicitly admitted LoRA candidate, frozen inputs and no automatic activation."""

import argparse
import json
import math
import random
import time
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

from .checkpoint import PARAMETERS, read_completed_receipt
from .config import MODEL, ROOT
from .evaluation import digest, method_digest
from .experiment_budget import MAX_MICRODOLLARS, ExperimentBudget, ExperimentError
from .experiments import REPORT_ROOT, encode, load_tokenizer, write_report

TRAIN_RATE = Decimal("0.737")
TTL_SECONDS = 7 * 24 * 3600


def corpus_hash(corpus):
    return digest(corpus.model_dump(mode="json"))


def training_estimate(token_count):
    return int((token_count * TRAIN_RATE).to_integral_value(rounding=ROUND_CEILING))


def prepare_sequences(corpus, tokenizer):
    from .training_data import supervised_examples, target_text

    sequences = []
    for example in supervised_examples(corpus):
        prompt = encode(tokenizer, example.case)
        response = tokenizer.encode(target_text(example) + "<|im_end|>\n", add_special_tokens=False)
        if not response or len(response) > 512:
            raise ExperimentError("supervised_answer_token_limit")
        full = prompt + response
        sequences.append(
            {
                "case_id": example.case.id,
                "input": full[:-1],
                "target": full[1:],
                "weights": [0.0] * (len(prompt) - 1) + [1.0] * len(response),
            }
        )
    if not 80 <= len(sequences) <= 100:
        raise ExperimentError("training_pilot_requires_80_to_100_examples")
    return sequences


def training_preview(corpus, tokenizer):
    from .training_data import frozen_manifest

    sequences = prepare_sequences(corpus, tokenizer)
    batches = math.ceil(len(sequences) / PARAMETERS["batch_size"])
    total = PARAMETERS["epochs"] * sum(len(row["input"]) for row in sequences)
    return {
        "hosted_requests": 0,
        "model": MODEL,
        "corpus_sha256": corpus_hash(corpus),
        "training_dataset_sha256": frozen_manifest(corpus)["training_dataset_sha256"],
        "method_sha256": method_digest(),
        "sequence_sha256": digest(sequences),
        "review_status": corpus.review_status,
        "human_review": "pending",
        "parameters": PARAMETERS,
        "examples": len(sequences),
        "expected_updates": PARAMETERS["epochs"] * batches,
        "full_sequence_tokens_across_epochs": total,
        "training_estimated_reserved_usd": (
            training_estimate(total) + PARAMETERS["epochs"] * batches
        )
        / 1_000_000,
        "new_pilot_cap_usd": MAX_MICRODOLLARS / 1_000_000,
        "storage": {
            "rate_usd_per_gb_month": 0.10,
            "excluded_from_token_estimate": True,
            "saved_checkpoints": 1,
            "ttl_seconds": TTL_SECONDS,
        },
    }


class Trainer:
    def __init__(self):
        import os

        import tinker

        key = os.environ.get("TINKER_API_KEY", "")
        if not key:
            raise ExperimentError("provider_not_configured")
        self.service = tinker.ServiceClient(api_key=key)
        self.client = self.service.create_lora_training_client(
            base_model=MODEL,
            rank=PARAMETERS["rank"],
            seed=PARAMETERS["seed"],
        )
        if self.client.get_info().model_data.model_name != MODEL:
            raise ExperimentError("training_model_mismatch")
        self.tokenizer = self.client.get_tokenizer()

    def step(self, rows):
        from tinker import types

        data = [
            types.Datum(
                model_input=types.ModelInput.from_ints(row["input"]),
                loss_fn_inputs={
                    "target_tokens": types.TensorData(data=row["target"], dtype="int64"),
                    "weights": types.TensorData(data=row["weights"], dtype="float32"),
                },
            )
            for row in rows
        ]
        gradients = self.client.forward_backward(data, "cross_entropy").result(timeout=120)
        self.client.optim_step(
            types.AdamParams(
                learning_rate=PARAMETERS["learning_rate"],
                grad_clip_norm=1.0,
            )
        ).result(timeout=120)
        return {
            key: float(value)
            for key, value in gradients.metrics.items()
            if isinstance(value, (int, float)) and math.isfinite(value)
        }

    def save(self):
        return (
            self.client.save_weights_for_sampler(
                "onelap-final",
                ttl_seconds=TTL_SECONDS,
            )
            .result(timeout=120)
            .path
        )

    def close(self, successful):
        self.service.close("success" if successful else "errored").result(timeout=30)


def train(corpus, tokenizer, budget, run_id, output, trainer_factory=Trainer):
    preview = training_preview(corpus, tokenizer)
    sequences = prepare_sequences(corpus, tokenizer)
    planned = math.ceil(preview["training_estimated_reserved_usd"] * 1_000_000)
    if budget.snapshot()["reserved_microdollars"] + planned > MAX_MICRODOLLARS:
        raise ExperimentError("training_would_exceed_remaining_pilot_budget")
    report = {
        "version": 1,
        "status": "running",
        **preview,
        "completed_updates": 0,
        "steps": [],
        "checkpoint": None,
        "checkpoint_ttl_seconds": TTL_SECONDS,
    }
    write_report(output, report)
    budget.claim(
        run_id,
        digest(
            {
                "corpus": preview["corpus_sha256"],
                "method": preview["method_sha256"],
                "sequences": preview["sequence_sha256"],
                "parameters": PARAMETERS,
            }
        ),
    )
    trainer = None
    try:
        trainer = trainer_factory()
        if digest(prepare_sequences(corpus, trainer.tokenizer)) != preview["sequence_sha256"]:
            raise ExperimentError("training_tokenizer_binding_mismatch")
        for epoch in range(PARAMETERS["epochs"]):
            rows = list(sequences)
            random.Random(PARAMETERS["seed"] + epoch).shuffle(rows)
            for offset in range(0, len(rows), PARAMETERS["batch_size"]):
                batch = rows[offset : offset + PARAMETERS["batch_size"]]
                amount = training_estimate(sum(len(row["input"]) for row in batch))
                update = report["completed_updates"] + 1
                budget.reserve(run_id, f"{run_id}:update-{update}", amount)
                started = time.monotonic()
                metrics = trainer.step(batch)
                report["completed_updates"] = update
                report["steps"].append(
                    {
                        "epoch": epoch + 1,
                        "update": update,
                        "estimated_reserved_usd": amount / 1_000_000,
                        "latency_ms": (time.monotonic() - started) * 1000,
                        "metrics": metrics,
                    }
                )
                write_report(output, report, replace=True)
                print(
                    json.dumps(
                        {
                            "epoch": epoch + 1,
                            "update": update,
                            "expected_updates": report["expected_updates"],
                            "metrics": metrics,
                        }
                    ),
                    flush=True,
                )
        checkpoint = trainer.save()
        if not isinstance(checkpoint, str) or not checkpoint.startswith("tinker://"):
            raise ExperimentError("invalid_saved_checkpoint")
        report.update(
            status="completed", checkpoint=checkpoint, hosted_requests=len(report["steps"])
        )
        report["training_estimated_reserved_usd"] = (
            sum(round(step["estimated_reserved_usd"] * 1_000_000) for step in report["steps"])
            / 1_000_000
        )
        write_report(output, report, replace=True)
        budget.finish(run_id, "completed")
    except BaseException:
        report["status"] = "failed"
        write_report(output, report, replace=True)
        budget.finish(run_id, "failed")
        raise
    finally:
        if trainer is not None:
            try:
                trainer.close(report["status"] == "completed")
            except Exception:
                pass
    return report


def load_receipt(path, corpus):
    if path is None:
        raise ExperimentError("checkpoint_receipt_required")
    from .training_data import frozen_manifest

    try:
        receipt, _ = read_completed_receipt(
            Path(path), corpus_hash(corpus), frozen_manifest(corpus)["training_dataset_sha256"]
        )
        return receipt
    except (OSError, ValueError, TypeError, RecursionError):
        raise ExperimentError("checkpoint_receipt_binding_mismatch") from None


def main(argv=None):
    from .training_data import DEFAULT_CORPUS, load_corpus, verify_frozen_corpus

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--tokenizer", type=Path)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--ack-agent-reviewed-synthetic", action="store_true")
    parser.add_argument("--ack-sdk-retries", action="store_true")
    parser.add_argument("--run-id", default="onelap-pilot-v1")
    parser.add_argument("--output", type=Path, default=REPORT_ROOT / "training.json")
    args = parser.parse_args(argv)
    try:
        corpus, tokenizer = load_corpus(args.corpus), load_tokenizer(args.tokenizer)
        if not args.live:
            print(json.dumps(training_preview(corpus, tokenizer), indent=2))
            return 0
        if not (args.ack_agent_reviewed_synthetic and args.ack_sdk_retries):
            raise ExperimentError("live_training_requires_synthetic_and_retry_acknowledgement")
        corpus = verify_frozen_corpus(args.corpus)
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env", override=False)
        receipt = train(corpus, tokenizer, ExperimentBudget(REPORT_ROOT), args.run_id, args.output)
        print(
            json.dumps(
                {
                    "status": receipt["status"],
                    "completed_updates": receipt["completed_updates"],
                    "checkpoint_saved": True,
                    "automatically_activated": False,
                }
            )
        )
        return 0
    except Exception as error:
        code = str(error) if isinstance(error, ExperimentError) else "training_failed_no_retry"
        print(json.dumps({"error": code}), flush=True)
        return 2
