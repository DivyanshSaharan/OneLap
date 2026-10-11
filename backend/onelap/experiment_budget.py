"""Local admission accounting shared by one bounded training/evaluation pilot."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

MAX_MICRODOLLARS = 750_000
MAX_OPERATIONS = 150


class ExperimentError(RuntimeError):
    pass


class ExperimentBudget:
    """Never refunds reservations or retries an operation, including uncertain failures."""

    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / "experiment-budget.sqlite3"
        with self.connection() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS runs ("
                "id TEXT PRIMARY KEY, fingerprint TEXT UNIQUE NOT NULL, "
                "status TEXT NOT NULL CHECK(status IN ('running','completed','failed')))"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS reservations ("
                "operation TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), "
                "microdollars INTEGER NOT NULL CHECK(microdollars > 0))"
            )

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.execute("PRAGMA foreign_keys=ON")
            db.execute("BEGIN IMMEDIATE")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def claim(self, run_id: str, fingerprint: str):
        try:
            with self.connection() as db:
                db.execute("INSERT INTO runs VALUES (?, ?, 'running')", (run_id, fingerprint))
        except sqlite3.IntegrityError:
            raise ExperimentError("run_already_admitted_do_not_replay") from None

    def snapshot(self):
        with self.connection() as db:
            cost, count = db.execute(
                "SELECT COALESCE(SUM(microdollars),0), COUNT(*) FROM reservations"
            ).fetchone()
        return {"reserved_microdollars": cost, "reserved_operations": count}

    def reserve(self, run_id: str, operation: str, amount: int):
        if type(amount) is not int or amount <= 0:
            raise ExperimentError("invalid_reservation")
        with self.connection() as db:
            run = db.execute("SELECT status FROM runs WHERE id=?", (run_id,)).fetchone()
            if run is None or run[0] != "running":
                raise ExperimentError("run_not_running")
            if db.execute("SELECT 1 FROM reservations WHERE operation=?", (operation,)).fetchone():
                raise ExperimentError("operation_already_admitted_do_not_retry")
            cost, count = db.execute(
                "SELECT COALESCE(SUM(microdollars),0), COUNT(*) FROM reservations"
            ).fetchone()
            if cost + amount > MAX_MICRODOLLARS or count >= MAX_OPERATIONS:
                raise ExperimentError("experiment_budget_exhausted")
            db.execute("INSERT INTO reservations VALUES (?,?,?)", (operation, run_id, amount))

    def finish(self, run_id: str, status: str):
        if status not in {"completed", "failed"}:
            raise ExperimentError("invalid_terminal_status")
        with self.connection() as db:
            changed = db.execute(
                "UPDATE runs SET status=? WHERE id=? AND status='running'", (status, run_id)
            ).rowcount
            if not changed:
                raise ExperimentError("run_not_running")
