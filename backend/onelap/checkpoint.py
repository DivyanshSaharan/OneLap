"""Explicit, hash-bound sampler selection. A training receipt never activates itself."""

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .config import MODEL, ROOT, Settings
from .provider_json import unique_keys

PARAMETERS = {"rank": 16, "seed": 2026, "epochs": 3, "batch_size": 10, "learning_rate": 0.0001}
CHECKPOINT_PATTERN = r"tinker://[A-Za-z0-9._:-]+/sampler_weights/[A-Za-z0-9._-]+"


@dataclass(frozen=True)
class Checkpoint:
    path: str = field(repr=False)
    receipt_sha256: str
    training_dataset_sha256: str


def read_completed_receipt(path: Path, corpus_sha256: str, training_sha256: str):
    from .evaluation import method_digest

    if path.stat().st_size > 1_000_000:
        raise ValueError("checkpoint_receipt_too_large")
    raw = path.read_bytes()
    receipt = json.loads(raw, object_pairs_hook=unique_keys)
    if (
        not isinstance(receipt, dict)
        or type(receipt.get("version")) is not int
        or receipt.get("version") != 1
        or receipt.get("status") != "completed"
        or receipt.get("model") != MODEL
        or receipt.get("corpus_sha256") != corpus_sha256
        or receipt.get("training_dataset_sha256") != training_sha256
        or receipt.get("method_sha256") != method_digest()
        or receipt.get("parameters") != PARAMETERS
        or any(
            type(receipt.get("parameters", {}).get(key)) is not type(value)
            for key, value in PARAMETERS.items()
        )
        or type(receipt.get("completed_updates")) is not int
        or receipt.get("completed_updates") != 30
        or type(receipt.get("expected_updates")) is not int
        or receipt.get("expected_updates") != 30
        or not isinstance(receipt.get("checkpoint"), str)
        or re.fullmatch(CHECKPOINT_PATTERN, receipt["checkpoint"]) is None
    ):
        raise ValueError("checkpoint_receipt_binding_mismatch")
    return receipt, hashlib.sha256(raw).hexdigest()


def load_checkpoint(settings: Settings) -> Checkpoint | None:
    if settings.model_target == "base":
        return None
    try:
        manifest = json.loads(
            (ROOT / "datasets/onelap-sft-v1.manifest.json").read_text("utf-8"),
            object_pairs_hook=unique_keys,
        )
        receipt, receipt_hash = read_completed_receipt(
            settings.checkpoint_receipt,
            manifest["corpus_sha256"],
            manifest["training_dataset_sha256"],
        )
        if receipt_hash != settings.checkpoint_receipt_sha256:
            raise ValueError
        return Checkpoint(receipt["checkpoint"], receipt_hash, receipt["training_dataset_sha256"])
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        raise ValueError("invalid_or_unapproved_checkpoint_receipt") from None
