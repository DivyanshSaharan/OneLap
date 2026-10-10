from collections.abc import Callable
from threading import Lock
from uuid import UUID, uuid4

from .budget import BudgetLedger, InferenceLedger
from .config import Settings
from .errors import MissionError
from .journal_config import JournalSettings

SCOPE = "onelap:inference:v1"
COLLECTION = "inference_spending"
# Release floor for known OneLap usage; a newer file ledger can only increase this floor.
KNOWN_IMPORT_MICRODOLLARS = 4665
KNOWN_IMPORT_REQUESTS = 6


class AtlasBudgetLedger:
    """A global, content-free counter; admission and receipts share one atomic document."""

    def __init__(
        self,
        settings: Settings,
        journal_settings: JournalSettings,
        *,
        client_factory: Callable | None = None,
    ):
        self.settings = settings
        self.journal_settings = journal_settings
        self._factory = client_factory
        self._client = None
        self._lock = Lock()
        self._local = BudgetLedger(settings.data_dir)

    def _floor(self) -> tuple[int, int]:
        if not self.settings.atlas_budget_approved:
            raise MissionError("atlas_budget_not_approved")
        amount = self.settings.budget_import_microdollars
        requests = self.settings.budget_import_requests
        if amount is None or requests is None:
            raise MissionError("budget_import_required")
        if amount < KNOWN_IMPORT_MICRODOLLARS or requests < KNOWN_IMPORT_REQUESTS:
            raise MissionError("budget_import_below_known_usage")
        local = self._local.snapshot()
        if amount < local["reserved_microdollars"] or requests < local["reserved_requests"]:
            raise MissionError("budget_import_below_local_ledger")
        return amount, requests

    def _collection(self):
        if not self.journal_settings.uri:
            raise MissionError("budget_ledger_not_configured")
        with self._lock:
            if self._client is None:
                factory = self._factory
                if factory is None:
                    from pymongo import MongoClient

                    factory = MongoClient
                self._client = factory(
                    self.journal_settings.uri,
                    connect=False,
                    tls=True,
                    tlsAllowInvalidCertificates=False,
                    tlsAllowInvalidHostnames=False,
                    timeoutMS=5000,
                    serverSelectionTimeoutMS=3000,
                    connectTimeoutMS=3000,
                    maxPoolSize=10,
                    retryWrites=False,
                    retryReads=False,
                    w="majority",
                    wTimeoutMS=5000,
                    readConcernLevel="majority",
                    appname="OneLapBudget",
                )
            from pymongo import ReadPreference

            return self._client[self.journal_settings.database].get_collection(
                COLLECTION, read_preference=ReadPreference.PRIMARY
            )

    @staticmethod
    def _initial(amount: int, requests: int) -> dict:
        return {
            "scope": SCOPE,
            "version": 1,
            "import_microdollars": amount,
            "import_requests": requests,
            "reserved_microdollars": amount,
            "reserved_requests": requests,
            "reservations": [],
        }

    @staticmethod
    def _validate(document: object, floor: tuple[int, int]) -> dict:
        if not isinstance(document, dict) or set(document) != {
            "_id",
            "scope",
            "version",
            "import_microdollars",
            "import_requests",
            "reserved_microdollars",
            "reserved_requests",
            "reservations",
        }:
            raise MissionError("budget_ledger_unavailable")
        amount, requests = floor
        if document["_id"] != SCOPE or document["scope"] != SCOPE:
            raise MissionError("budget_ledger_scope_mismatch")
        for field in (
            "version",
            "import_microdollars",
            "import_requests",
            "reserved_microdollars",
            "reserved_requests",
        ):
            if type(document[field]) is not int or document[field] < 0:
                raise MissionError("budget_ledger_unavailable")
        if document["version"] != 1:
            raise MissionError("budget_ledger_unavailable")
        if (document["import_microdollars"], document["import_requests"]) != floor:
            raise MissionError("budget_import_mismatch")
        receipts = document["reservations"]
        if not isinstance(receipts, list) or len(receipts) > 100:
            raise MissionError("budget_ledger_unavailable")
        ids = set()
        total = amount
        for receipt in receipts:
            if not isinstance(receipt, dict) or set(receipt) != {"id", "amount"}:
                raise MissionError("budget_ledger_unavailable")
            identifier = receipt["id"]
            try:
                if not isinstance(identifier, str) or str(UUID(identifier)) != identifier:
                    raise ValueError
            except ValueError:
                raise MissionError("budget_ledger_unavailable") from None
            if identifier in ids or type(receipt["amount"]) is not int or receipt["amount"] <= 0:
                raise MissionError("budget_ledger_unavailable")
            ids.add(identifier)
            total += receipt["amount"]
        if (
            document["reserved_microdollars"] != total
            or document["reserved_requests"] != requests + len(receipts)
            or total > 10_000_000
            or document["reserved_requests"] > 100
        ):
            raise MissionError("budget_ledger_unavailable")
        return document

    def _document(self) -> dict:
        floor = self._floor()
        document = self._collection().find_one_and_update(
            {"_id": SCOPE},
            {"$setOnInsert": self._initial(*floor)},
            upsert=True,
            return_document=True,
        )
        return self._validate(document, floor)

    def snapshot(self) -> dict[str, int]:
        try:
            document = self._document()
            return {
                "version": 1,
                "reserved_microdollars": document["reserved_microdollars"],
                "reserved_requests": document["reserved_requests"],
            }
        except MissionError:
            raise
        except Exception:
            raise MissionError("budget_ledger_unavailable") from None

    def reserve(
        self, amount: int, cap: int, request_cap: int, *, reservation_id: str | None = None
    ) -> None:
        try:
            identifier = reservation_id or str(uuid4())
            if str(UUID(identifier)) != identifier:
                raise ValueError
            if type(amount) is not int or amount <= 0 or type(cap) is not int:
                raise MissionError("budget_exhausted", 429)
            if not 0 <= cap <= 10_000_000 or type(request_cap) is not int:
                raise ValueError
            if not 1 <= request_cap <= 100:
                raise ValueError
            document = self._document()
            for receipt in document["reservations"]:
                if receipt["id"] == identifier:
                    if receipt["amount"] != amount:
                        raise MissionError("budget_reservation_conflict")
                    return
            updated = self._collection().find_one_and_update(
                {
                    "_id": SCOPE,
                    "scope": SCOPE,
                    "version": 1,
                    "import_microdollars": self.settings.budget_import_microdollars,
                    "import_requests": self.settings.budget_import_requests,
                    "reserved_microdollars": {"$lte": cap - amount},
                    "reserved_requests": {"$lt": request_cap},
                    "reservations.id": {"$ne": identifier},
                },
                {
                    "$inc": {"reserved_microdollars": amount, "reserved_requests": 1},
                    "$push": {"reservations": {"id": identifier, "amount": amount}},
                },
                return_document=True,
                upsert=False,
            )
            if updated is not None:
                self._validate(updated, self._floor())
                return
            current = self._document()
            for receipt in current["reservations"]:
                if receipt["id"] == identifier:
                    if receipt["amount"] != amount:
                        raise MissionError("budget_reservation_conflict")
                    return
            if current["reserved_requests"] >= request_cap:
                raise MissionError("model_request_limit_reached", 429)
            if current["reserved_microdollars"] + amount > cap:
                raise MissionError("budget_exhausted", 429)
            raise MissionError("budget_ledger_unavailable")
        except MissionError:
            raise
        except Exception:
            raise MissionError("budget_ledger_unavailable") from None

    def close(self) -> None:
        with self._lock:
            if self._client is not None:
                self._client.close()
                self._client = None


def inference_ledger(settings: Settings, journal_settings: JournalSettings) -> InferenceLedger:
    if settings.budget_storage == "atlas":
        return AtlasBudgetLedger(settings, journal_settings)
    if settings.serve_frontend and settings.hosted_enabled:
        raise ValueError("Production hosted inference requires the Atlas budget ledger")
    return BudgetLedger(settings.data_dir)
