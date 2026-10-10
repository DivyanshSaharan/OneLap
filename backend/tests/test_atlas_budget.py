from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from threading import Lock
from uuid import uuid4

import pytest
from onelap.atlas_budget import COLLECTION, AtlasBudgetLedger, inference_ledger
from onelap.budget import BudgetLedger
from onelap.config import Settings
from onelap.errors import MissionError
from onelap.journal_config import JournalSettings
from onelap.provider import TinkerProvider


class Collection:
    def __init__(self):
        self.document = None
        self.calls = []
        self.lock = Lock()
        self.failure = None
        self.fail_after_write = False

    def find_one_and_update(self, query, update, **kwargs):
        with self.lock:
            self.calls.append((deepcopy(query), deepcopy(update), kwargs))
            if self.failure:
                raise self.failure
            if "$setOnInsert" in update:
                if self.document is None:
                    self.document = {"_id": query["_id"], **deepcopy(update["$setOnInsert"])}
                return deepcopy(self.document)
            document = self.document
            if document is None:
                return None
            for key, value in query.items():
                if key == "reservations.id":
                    if any(row["id"] == value["$ne"] for row in document["reservations"]):
                        return None
                elif isinstance(value, dict):
                    if "$lte" in value and document[key] > value["$lte"]:
                        return None
                    if "$lt" in value and document[key] >= value["$lt"]:
                        return None
                elif document.get(key) != value:
                    return None
            for key, amount in update["$inc"].items():
                document[key] += amount
            document["reservations"].append(deepcopy(update["$push"]["reservations"]))
            if self.fail_after_write:
                raise TimeoutError("PRIVATE_URI")
            return deepcopy(document)


class Client:
    def __init__(self, collection):
        self.collection = collection
        self.closed = False
        self.collection_args = []

    def __getitem__(self, database):
        assert database == "onelap"
        return self

    def get_collection(self, name, **kwargs):
        self.collection_args.append((name, kwargs))
        return self.collection

    def close(self):
        self.closed = True


@pytest.fixture
def atlas(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        budget_storage="atlas",
        atlas_budget_approved=True,
        budget_import_microdollars=4665,
        budget_import_requests=6,
    )
    journal = JournalSettings(uri="mongodb+srv://fictional:fictional@sample.mongodb.net/")
    collection = Collection()
    clients = []
    calls = []

    def factory(uri, **kwargs):
        calls.append((uri, kwargs))
        client = Client(collection)
        clients.append(client)
        return client

    def ledger(**changes):
        return AtlasBudgetLedger(replace(settings, **changes), journal, client_factory=factory)

    return ledger, collection, clients, calls


def test_default_file_does_not_create_atlas_client(tmp_path):
    ledger = inference_ledger(Settings(data_dir=tmp_path), JournalSettings())
    assert isinstance(ledger, BudgetLedger)
    assert ledger.snapshot()["reserved_requests"] == 0
    assert list(tmp_path.iterdir()) == []


def test_explicit_floor_survives_restart_without_double_import(atlas):
    build, collection, _, _ = atlas
    first = build()
    assert first.snapshot() == {
        "version": 1,
        "reserved_microdollars": 4665,
        "reserved_requests": 6,
    }
    first.reserve(500, 10_000, 10)
    second = build()
    assert second.snapshot()["reserved_microdollars"] == 5165
    assert second.snapshot()["reserved_requests"] == 7
    assert collection.document["import_requests"] == 6
    assert len(collection.document["reservations"]) == 1


def test_counter_uses_separate_primary_majority_collection(atlas):
    build, _, clients, calls = atlas
    ledger = build()
    ledger.snapshot()
    options = calls[0][1]
    assert options["w"] == "majority"
    assert options["readConcernLevel"] == "majority"
    assert options["retryWrites"] is options["retryReads"] is False
    assert options["tls"] is True
    assert options["tlsAllowInvalidCertificates"] is False
    assert clients[0].collection_args[0][0] == COLLECTION
    ledger.close()
    assert clients[0].closed


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"atlas_budget_approved": False}, "atlas_budget_not_approved"),
        (
            {"budget_import_microdollars": None, "budget_import_requests": None},
            "budget_import_required",
        ),
    ],
)
def test_disabled_or_unimported_never_connects(atlas, changes, code):
    build, _, _, calls = atlas
    with pytest.raises(MissionError, match=code):
        build(**changes).snapshot()
    assert calls == []


def test_import_preserves_file_and_refuses_lower_floor(atlas):
    build, _, _, calls = atlas
    ledger = build()
    local = BudgetLedger(ledger.settings.data_dir)
    local.reserve(6000, 10_000, 10)
    previous = local.path.read_bytes()
    with pytest.raises(MissionError, match="budget_import_below_local_ledger"):
        ledger.snapshot()
    assert calls == []
    assert local.path.read_bytes() == previous
    imported = build(budget_import_microdollars=6000, budget_import_requests=6)
    assert imported.snapshot()["reserved_microdollars"] == 6000
    assert local.path.read_bytes() == previous


def test_changed_import_does_not_merge_or_overwrite(atlas):
    build, collection, _, _ = atlas
    build().snapshot()
    original = deepcopy(collection.document)
    with pytest.raises(MissionError, match="budget_import_mismatch"):
        build(budget_import_microdollars=5000).snapshot()
    assert collection.document == original


def test_missing_local_file_does_not_allow_zero_import(atlas):
    build, _, _, calls = atlas
    with pytest.raises(MissionError, match="budget_import_below_known_usage"):
        build(budget_import_microdollars=0, budget_import_requests=0).snapshot()
    assert calls == []


def test_same_reservation_is_idempotent_and_changed_amount_conflicts(atlas):
    build, collection, _, _ = atlas
    identifier = str(uuid4())
    build().reserve(500, 10_000, 10, reservation_id=identifier)
    build().reserve(500, 10_000, 10, reservation_id=identifier)
    assert collection.document["reserved_requests"] == 7
    with pytest.raises(MissionError, match="budget_reservation_conflict"):
        build().reserve(600, 10_000, 10, reservation_id=identifier)
    assert collection.document["reserved_microdollars"] == 5165


def test_concurrent_independent_workers_cannot_exceed_money_cap(atlas):
    build, collection, _, _ = atlas

    def attempt(_):
        try:
            build().reserve(600, 5265, 100)
            return "accepted"
        except MissionError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(attempt, range(30)))
    assert results.count("accepted") == 1
    assert results.count("budget_exhausted") == 29
    assert collection.document["reserved_microdollars"] == 5265


def test_concurrent_same_receipt_cannot_increment_twice(atlas):
    build, collection, _, _ = atlas
    identifier = str(uuid4())
    with ThreadPoolExecutor(max_workers=12) as executor:
        list(
            executor.map(
                lambda _: build().reserve(600, 5265, 100, reservation_id=identifier), range(30)
            )
        )
    assert collection.document["reserved_requests"] == 7
    assert len(collection.document["reservations"]) == 1


def test_concurrent_workers_cannot_exceed_request_cap(atlas):
    build, collection, _, _ = atlas

    def attempt(_):
        try:
            build().reserve(1, 100_000, 7)
            return "accepted"
        except MissionError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(attempt, range(30)))
    assert results.count("accepted") == 1
    assert results.count("model_request_limit_reached") == 29
    assert collection.document["reserved_requests"] == 7


def test_decreased_cap_does_not_reset_counter(atlas):
    build, _, _, _ = atlas
    ledger = build()
    ledger.reserve(500, 10_000, 10)
    with pytest.raises(MissionError, match="budget_exhausted"):
        ledger.reserve(1, 5000, 10)
    assert ledger.snapshot()["reserved_microdollars"] == 5165


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("scope", "other-project", "budget_ledger_scope_mismatch"),
        ("version", 2, "budget_ledger_unavailable"),
        ("reserved_requests", True, "budget_ledger_unavailable"),
        ("reserved_microdollars", 0, "budget_ledger_unavailable"),
        ("reservations", [{"id": "invalid", "amount": 1}], "budget_ledger_unavailable"),
        ("import_requests", 0, "budget_import_mismatch"),
    ],
)
def test_corrupt_or_different_scope_counter_fails_closed(atlas, field, value, code):
    build, collection, _, _ = atlas
    ledger = build()
    ledger.snapshot()
    collection.document[field] = value
    with pytest.raises(MissionError, match=code):
        ledger.reserve(500, 10_000, 10)


def test_failed_write_never_admits_and_redacts(atlas):
    build, collection, _, _ = atlas
    ledger = build()
    ledger.snapshot()
    collection.failure = OSError("PRIVATE_CREDENTIAL")
    with pytest.raises(MissionError, match="^budget_ledger_unavailable$"):
        ledger.reserve(500, 10_000, 10)
    assert collection.document["reserved_requests"] == 6


def test_unknown_write_keeps_reservation_and_does_not_retry(atlas):
    build, collection, _, _ = atlas
    ledger = build()
    ledger.snapshot()
    identifier = str(uuid4())
    collection.fail_after_write = True
    with pytest.raises(MissionError, match="budget_ledger_unavailable"):
        ledger.reserve(500, 10_000, 10, reservation_id=identifier)
    assert collection.document["reserved_requests"] == 7
    assert len([call for call in collection.calls if "$inc" in call[1]]) == 1
    collection.fail_after_write = False
    ledger.reserve(500, 10_000, 10, reservation_id=identifier)
    assert ledger.snapshot()["reserved_requests"] == 7


def test_unavailable_budget_prevents_runtime_and_sample(atlas, settings):
    build, collection, _, _ = atlas
    collection.failure = OSError("PRIVATE_URI")
    creations = []
    provider = TinkerProvider(settings, build(), lambda key: creations.append(key), lambda: True)
    with pytest.raises(MissionError, match="budget_ledger_unavailable"):
        provider.sample_text([])
    assert creations == []


def test_production_model_use_refuses_ephemeral_file_ledger(tmp_path):
    settings = Settings(data_dir=tmp_path, serve_frontend=True, hosted_enabled=True)
    with pytest.raises(ValueError, match="requires the Atlas budget ledger"):
        inference_ledger(settings, JournalSettings())


@pytest.mark.parametrize(
    "changes",
    [
        {"budget_storage": "other"},
        {"budget_import_microdollars": 1},
        {"budget_import_requests": 1},
        {"budget_import_microdollars": True, "budget_import_requests": 1},
        {"budget_import_microdollars": 1, "budget_import_requests": 0},
        {"budget_import_microdollars": 0, "budget_import_requests": 1},
        {"budget_import_microdollars": -1, "budget_import_requests": 1},
        {"budget_import_microdollars": 1, "budget_import_requests": 101},
    ],
)
def test_invalid_settings_reject_import(changes):
    with pytest.raises(ValueError):
        Settings(**changes)


def test_environment_reads_exact_immutable_import(monkeypatch):
    monkeypatch.setenv("ONELAP_BUDGET_STORAGE", "atlas")
    monkeypatch.setenv("ONELAP_ATLAS_BUDGET_APPROVED", "true")
    monkeypatch.setenv("ONELAP_BUDGET_IMPORT_USD", "0.004665")
    monkeypatch.setenv("ONELAP_BUDGET_IMPORT_REQUESTS", "6")
    settings = Settings.from_environment()
    assert settings.budget_storage == "atlas"
    assert settings.atlas_budget_approved is True
    assert settings.budget_import_microdollars == 4665
    assert settings.budget_import_requests == 6


@pytest.mark.parametrize("value", ["NaN", "Infinity", "0.0000001", "-1", "11"])
def test_invalid_import_environment_rejected(monkeypatch, value):
    monkeypatch.setenv("ONELAP_BUDGET_IMPORT_USD", value)
    monkeypatch.setenv("ONELAP_BUDGET_IMPORT_REQUESTS", "6")
    with pytest.raises(ValueError):
        Settings.from_environment()
