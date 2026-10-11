from concurrent.futures import ThreadPoolExecutor

import pytest
from onelap.experiment_budget import MAX_MICRODOLLARS, ExperimentBudget, ExperimentError


def test_reservations_persist_and_terminal_runs_cannot_spend(tmp_path):
    budget = ExperimentBudget(tmp_path)
    budget.claim("pilot", "fixed-inputs")
    budget.reserve("pilot", "first", 12)
    assert ExperimentBudget(tmp_path).snapshot() == {
        "reserved_microdollars": 12,
        "reserved_operations": 1,
    }
    budget.finish("pilot", "failed")
    with pytest.raises(ExperimentError, match="run_not_running"):
        budget.reserve("pilot", "second", 2)
    assert budget.snapshot()["reserved_microdollars"] == 12


def test_no_run_or_operation_replay_and_no_refunds(tmp_path):
    budget = ExperimentBudget(tmp_path)
    budget.claim("pilot", "fingerprint")
    with pytest.raises(ExperimentError, match="already_admitted"):
        budget.claim("different", "fingerprint")
    budget.reserve("pilot", "operation", 4)
    with pytest.raises(ExperimentError, match="already_admitted"):
        budget.reserve("pilot", "operation", 4)
    assert budget.snapshot()["reserved_microdollars"] == 4


@pytest.mark.parametrize("amount", [0, -1, True, 1.5])
def test_invalid_amount(tmp_path, amount):
    budget = ExperimentBudget(tmp_path)
    budget.claim("pilot", "fingerprint")
    with pytest.raises(ExperimentError, match="invalid_reservation"):
        budget.reserve("pilot", "operation", amount)


def test_global_cap_is_atomic_across_instances(tmp_path):
    budget = ExperimentBudget(tmp_path)
    budget.claim("pilot", "fingerprint")

    def reserve(index):
        try:
            ExperimentBudget(tmp_path).reserve("pilot", str(index), MAX_MICRODOLLARS // 2)
            return True
        except ExperimentError:
            return False

    with ThreadPoolExecutor(max_workers=4) as executor:
        assert sum(executor.map(reserve, range(4))) == 2
    assert budget.snapshot() == {
        "reserved_microdollars": MAX_MICRODOLLARS,
        "reserved_operations": 2,
    }


def test_operation_limit(tmp_path):
    budget = ExperimentBudget(tmp_path)
    budget.claim("pilot", "fingerprint")
    for index in range(150):
        budget.reserve("pilot", str(index), 1)
    with pytest.raises(ExperimentError, match="budget_exhausted"):
        budget.reserve("pilot", "excess", 1)
