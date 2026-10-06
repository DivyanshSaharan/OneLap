import json

import pytest
from onelap.budget import BudgetLedger, reservation
from onelap.config import Settings
from onelap.errors import MissionError


def test_defaults_are_disabled_and_do_not_create_ledger(tmp_path):
    settings = Settings(data_dir=tmp_path)
    assert settings.disabled_reason() == "hosted_requests_disabled"
    assert BudgetLedger(tmp_path).snapshot()["reserved_requests"] == 0
    assert list(tmp_path.iterdir()) == []


def test_reservation_uses_worst_case_output():
    assert reservation(100, 512) == 548


def test_budget_survives_restart_and_cap_decrease(tmp_path):
    ledger = BudgetLedger(tmp_path)
    ledger.reserve(500, 1000, 2)
    restored = BudgetLedger(tmp_path)
    assert restored.snapshot()["reserved_microdollars"] == 500
    with pytest.raises(MissionError, match="budget_exhausted"):
        restored.reserve(1, 499, 2)
    assert restored.snapshot()["reserved_requests"] == 1


@pytest.mark.parametrize(
    "value",
    [
        "not JSON",
        "[]",
        "null",
        "{}",
        '{"version":true}',
        json.dumps({"version": 2, "reserved_microdollars": 0, "reserved_requests": 0}),
        json.dumps({"version": 1, "reserved_microdollars": -1, "reserved_requests": 0}),
        json.dumps({"version": 1, "reserved_microdollars": 0, "reserved_requests": False}),
        "x" * 4097,
    ],
)
def test_corrupt_ledger_fails_closed(tmp_path, value):
    path = tmp_path / "inference-budget.json"
    path.write_text(value, encoding="utf-8")
    ledger = BudgetLedger(tmp_path)
    with pytest.raises(MissionError, match="budget_ledger_unavailable"):
        ledger.reserve(1, 1000, 20)
    assert path.read_text(encoding="utf-8") == value


def test_ledger_atomic_replace_failure_does_not_admit(tmp_path, monkeypatch):
    def fail(*_args):
        raise OSError("private-path")

    monkeypatch.setattr("onelap.budget.os.replace", fail)
    ledger = BudgetLedger(tmp_path)
    with pytest.raises(MissionError, match="budget_ledger_unavailable"):
        ledger.reserve(1, 1000, 20)
    assert not ledger.path.exists()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "0.0000001", "not-money", "11"])
def test_invalid_budget_environment_rejected(monkeypatch, value):
    monkeypatch.setenv("ONELAP_APPROVED_BUDGET_USD", value)
    with pytest.raises(ValueError):
        Settings.from_environment()


@pytest.mark.parametrize(
    "field,value",
    [
        ("access_token", "short"),
        ("access_token", "x" * 257),
        ("access_token", "a" * 31 + " "),
        ("access_token", "a" * 31 + "é"),
        ("budget_microdollars", True),
        ("budget_microdollars", -1),
        ("max_model_requests", 0),
        ("max_model_requests", 101),
    ],
)
def test_invalid_settings_rejected(field, value):
    with pytest.raises(ValueError):
        Settings(**{field: value})


def test_environment_budget_exact_microdollars(monkeypatch):
    monkeypatch.setenv("ONELAP_APPROVED_BUDGET_USD", "0.123456")
    assert Settings.from_environment().budget_microdollars == 123456


def test_secrets_not_in_settings_repr(settings):
    assert settings.api_key not in repr(settings)
    assert settings.access_token not in repr(settings)


def test_existing_budget_lease_fails_closed(tmp_path):
    ledger = BudgetLedger(tmp_path)
    lease = ledger.path.with_suffix(".lock")
    lease.write_text("existing process or interrupted reservation", encoding="ascii")
    with pytest.raises(MissionError, match="budget_ledger_busy"):
        ledger.reserve(1, 1000, 20)
    assert lease.exists()
    assert not ledger.path.exists()


def test_duplicate_ledger_keys_rejected(tmp_path):
    ledger = BudgetLedger(tmp_path)
    ledger.path.write_text(
        '{"version":1,"reserved_microdollars":500,"reserved_microdollars":0,"reserved_requests":1}',
        encoding="utf-8",
    )
    with pytest.raises(MissionError, match="budget_ledger_unavailable"):
        ledger.reserve(1, 1000, 20)


def test_independent_ledgers_serialize_reservations(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    def attempt():
        try:
            BudgetLedger(tmp_path).reserve(600, 1000, 20)
            return "accepted"
        except MissionError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: attempt(), range(8)))
    assert results.count("accepted") == 1
    assert BudgetLedger(tmp_path).snapshot()["reserved_microdollars"] == 600
