import json
import os
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from threading import Lock
from typing import Protocol
from uuid import uuid4

from .errors import MissionError
from .provider_json import unique_keys

# Uncached USD / million tokens; equivalently microdollars per token. Estimates, not bills.
INPUT_RATE = Decimal("0.33")
OUTPUT_RATE = Decimal("1.005")


class InferenceLedger(Protocol):
    def snapshot(self) -> dict[str, int]: ...

    def reserve(self, amount: int, cap: int, request_cap: int) -> None: ...

    def close(self) -> None: ...


def reservation(input_tokens: int, output_tokens: int) -> int:
    return int(
        (input_tokens * INPUT_RATE + output_tokens * OUTPUT_RATE).to_integral_value(
            rounding=ROUND_CEILING
        )
    )


class BudgetLedger:
    """Single-process, conservative reservations persist across restarts; never refunded."""

    def __init__(self, directory: Path):
        self.path = directory / "inference-budget.json"
        self._lock = Lock()

    def _read(self) -> dict[str, int]:
        try:
            if any(
                path.is_symlink() or path.is_junction() for path in (self.path, self.path.parent)
            ):
                raise ValueError
            if not self.path.exists():
                return {"version": 1, "reserved_microdollars": 0, "reserved_requests": 0}
            if self.path.stat().st_size > 4096:
                raise ValueError
            data = json.loads(self.path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
            if not isinstance(data, dict) or set(data) != {
                "version",
                "reserved_microdollars",
                "reserved_requests",
            }:
                raise ValueError
            if any(type(value) is not int for value in data.values()):
                raise ValueError
            if data["version"] != 1 or any(value < 0 for value in data.values()):
                raise ValueError
            return data
        except (OSError, ValueError, TypeError, RecursionError):
            raise MissionError("budget_ledger_unavailable") from None

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return self._read()

    def close(self) -> None:
        pass

    def reserve(self, amount: int, cap: int, request_cap: int) -> None:
        with self._lock:
            lease = self.path.with_suffix(".lock")
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with lease.open("x", encoding="ascii") as stream:
                    stream.write("reservation in progress")
            except FileExistsError:
                raise MissionError("budget_ledger_busy", 429) from None
            except OSError:
                raise MissionError("budget_ledger_unavailable") from None
            try:
                self._reserve_locked(amount, cap, request_cap)
            finally:
                lease.unlink()

    def _reserve_locked(self, amount: int, cap: int, request_cap: int) -> None:
        data = self._read()
        if amount <= 0 or data["reserved_microdollars"] + amount > cap:
            raise MissionError("budget_exhausted", 429)
        if data["reserved_requests"] >= request_cap:
            raise MissionError("model_request_limit_reached", 429)
        data["reserved_microdollars"] += amount
        data["reserved_requests"] += 1
        temporary = self.path.with_name(f".budget-{uuid4().hex}.tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open("x", encoding="utf-8") as stream:
                json.dump(data, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except OSError:
            raise MissionError("budget_ledger_unavailable") from None
        finally:
            if temporary.exists():
                temporary.unlink()
