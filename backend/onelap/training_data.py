"""Offline, provenance-labelled supervised corpus and frozen input manifests."""

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from .errors import MissionError
from .evaluation import (
    EvaluationError,
    digest,
    input_digest,
    load_artifact,
    messages_for,
    records_for,
)
from .evaluation_models import EvaluationCase, EvaluationDataset, Label, Note, Split, Version
from .followup import validate_output
from .journal_models import FollowUpOutput
from .models import MissionPlan, StrictModel
from .policy import validate_plan
from .provider_json import unique_keys

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = ROOT / "datasets" / "onelap-sft-v1.json"
DEFAULT_MANIFEST = ROOT / "datasets" / "onelap-sft-v1.manifest.json"


def _normalized(value: object) -> str:
    """Catch input duplication despite whitespace, case and punctuation changes."""
    if isinstance(value, str):
        return re.sub(r"\W+", " ", value.casefold()).strip()
    if isinstance(value, dict):
        return digest({key: _normalized(item) for key, item in sorted(value.items())})
    if isinstance(value, list):
        return digest([_normalized(item) for item in value])
    return digest(value)


class SupervisedExample(StrictModel):
    case: EvaluationCase
    variant: Annotated[int, Field(strict=True, ge=1, le=5)]
    assistant_target: MissionPlan | FollowUpOutput | None
    agent_review: Note

    @model_validator(mode="after")
    def valid_target(self):
        if self.assistant_target is None:
            return self
        if self.case.workflow == "mission":
            if not isinstance(self.assistant_target, MissionPlan):
                raise ValueError("Initial mission targets must be MissionPlan objects")
            try:
                validate_plan(self.assistant_target, self.case.request)
            except MissionError:
                raise ValueError("Mission target violates application constraints") from None
        else:
            if not isinstance(self.assistant_target, FollowUpOutput):
                raise ValueError("Follow-up targets must include reflection and mission")
            try:
                validate_output(target_text(self), *records_for(self.case))
            except MissionError:
                raise ValueError("Follow-up target violates application constraints") from None
        return self


class TrainingCorpus(StrictModel):
    version: Version
    name: Label
    provenance: Literal["synthetic_assistant_authored"]
    review_status: Literal["agent_reviewed"]
    reviewer: Literal["onelap-authoring-agent-v1"]
    split_method: Literal["family_before_variants"]
    limitations: list[Annotated[str, StringConstraints(min_length=1, max_length=1000)]] = Field(
        min_length=1, max_length=10
    )
    families: dict[Label, Split]
    examples: list[SupervisedExample] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def separation(self):
        cases = [example.case for example in self.examples]
        # Reuse the established strict input/family/duplicate validation. An agent review is
        # deliberately NOT promoted to the existing evaluator's human-reviewed status.
        EvaluationDataset(
            version=1,
            name=self.name,
            provenance=self.provenance,
            review_status="unreviewed",
            reviewer=None,
            split_method=self.split_method,
            families=self.families,
            cases=cases,
        )
        counts = Counter(self.families[case.family] for case in cases)
        if counts != {"train": 100, "dev": 20, "heldout": 30}:
            raise ValueError(
                "The frozen v1 corpus requires 100 train, 20 dev and 30 heldout inputs"
            )
        variants: dict[str, set[int]] = {}
        fingerprints: set[str] = set()
        observation_families: dict[str, str] = {}
        for example in self.examples:
            case = example.case
            split = self.families[case.family]
            if (example.assistant_target is not None) != (split == "train"):
                raise ValueError("Only train examples may contain assistant targets")
            values = variants.setdefault(case.family, set())
            if example.variant in values:
                raise ValueError("Family variants must be unique")
            values.add(example.variant)
            fingerprint = _normalized(
                case.model_dump(mode="json", exclude={"id", "family", "semantic_checks"})
            )
            if fingerprint in fingerprints:
                raise ValueError("Normalized duplicate inputs are not independent examples")
            fingerprints.add(fingerprint)
            if case.source:
                observation = _normalized(case.source.observation)
                previous_family = observation_families.setdefault(observation, case.family)
                if previous_family != case.family:
                    raise ValueError("The same normalized source observation cannot cross families")
        if any(values != {1, 2, 3, 4, 5} for values in variants.values()):
            raise ValueError("Each preassigned family needs exactly five variants")
        return self


def target_text(example: SupervisedExample) -> str:
    if example.assistant_target is None:
        raise ValueError("Evaluation-only inputs have no assistant target")
    return json.dumps(
        example.assistant_target.model_dump(mode="json"),
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )


def load_corpus(path: Path = DEFAULT_CORPUS) -> TrainingCorpus:
    return load_artifact(path, TrainingCorpus)


def evaluation_dataset(corpus: TrainingCorpus) -> EvaluationDataset:
    return EvaluationDataset(
        version=1,
        name=corpus.name,
        provenance=corpus.provenance,
        review_status="unreviewed",
        reviewer=None,
        split_method=corpus.split_method,
        families=corpus.families,
        cases=[example.case for example in corpus.examples],
    )


def supervised_examples(corpus: TrainingCorpus) -> list[SupervisedExample]:
    return sorted(
        (example for example in corpus.examples if corpus.families[example.case.family] == "train"),
        key=lambda example: example.case.id,
    )


def frozen_manifest(corpus: TrainingCorpus) -> dict:
    dataset = evaluation_dataset(corpus)
    training = supervised_examples(corpus)
    return {
        "version": 1,
        "corpus_sha256": digest(corpus.model_dump(mode="json")),
        "evaluation_dataset_sha256": digest(dataset.model_dump(mode="json")),
        "training_dataset_sha256": digest(
            [
                {
                    "case_id": example.case.id,
                    "messages": messages_for(example.case),
                    "assistant_target": target_text(example),
                }
                for example in training
            ]
        ),
        "provenance": corpus.provenance,
        "review_status": corpus.review_status,
        "human_reviewed": False,
        "split_method": corpus.split_method,
        "families": corpus.families,
        "counts": dict(Counter(corpus.families[item.case.family] for item in corpus.examples)),
        "inputs": [
            {
                "case_id": example.case.id,
                "family": example.case.family,
                "split": corpus.families[example.case.family],
                "input_sha256": input_digest(example.case),
                "target_sha256": digest(target_text(example))
                if example.assistant_target is not None
                else None,
            }
            for example in sorted(corpus.examples, key=lambda item: item.case.id)
        ],
        "hosted_requests": 0,
    }


def verify_frozen_corpus(
    path: Path = DEFAULT_CORPUS, manifest: Path = DEFAULT_MANIFEST
) -> TrainingCorpus:
    """Fail closed before spending if inputs, targets or application prompts changed.

    Exceptions contain only a fixed code, not validation payloads or corpus text. Hosted
    workflows should use the committed default paths; alternate paths support offline review.
    This checks integrity, not human review or proof of useful model behaviour.
    """
    try:
        corpus = load_corpus(path)
        if manifest.suffix.lower() != ".json" or manifest.stat().st_size > 4_194_304:
            raise ValueError
        stored = json.loads(manifest.read_text("utf-8"), object_pairs_hook=unique_keys)
        if stored != frozen_manifest(corpus):
            raise ValueError
        return corpus
    except (EvaluationError, OSError, ValueError, TypeError, AttributeError, RecursionError):
        raise ValueError("invalid_or_changed_frozen_corpus") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args(argv)
    try:
        corpus = verify_frozen_corpus(args.corpus, args.manifest)
        manifest = frozen_manifest(corpus)
        print(
            json.dumps({key: value for key, value in manifest.items() if key != "inputs"}, indent=2)
        )
        return 0
    except (EvaluationError, OSError, ValueError, TypeError, AttributeError, RecursionError):
        print(json.dumps({"error": "invalid_corpus_or_manifest", "hosted_requests": 0}))
        return 2
