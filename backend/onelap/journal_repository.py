import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from threading import Lock

from .errors import MissionError
from .journal_config import JournalSettings
from .journal_models import JournalPage, JournalRecord, OutingInput


def content_hash(entry: OutingInput) -> str:
    data = json.dumps(entry.model_dump(), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def now():
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class AtlasJournal:
    def __init__(self, settings: JournalSettings, *, client_factory: Callable | None = None):
        self.settings = settings
        self._factory = client_factory
        self._client = None
        self._lock = Lock()

    def _collection(self):
        reason = self.settings.disabled_reason()
        if reason:
            raise MissionError(reason)
        with self._lock:
            if self._client is None:
                factory = self._factory
                if factory is None:
                    from pymongo import MongoClient

                    factory = MongoClient
                self._client = factory(
                    self.settings.uri,
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
                    appname="OneLap",
                )
            from pymongo import ReadPreference

            return self._client[self.settings.database].get_collection(
                "outings",
                read_preference=ReadPreference.PRIMARY,
            )

    @staticmethod
    def _record(document, owner):
        if document["owner_id"] != owner or document["deleted"]:
            raise ValueError("Invalid journal record")
        record = JournalRecord.model_validate(document["record"])
        if document["_id"] != f"{owner}:{record.entry.id}" or document[
            "content_hash"
        ] != content_hash(record.entry):
            raise ValueError("Invalid journal record")
        return record

    def save(self, owner: str, entry: OutingInput):
        try:
            key = f"{owner}:{entry.id}"
            digest = content_hash(entry)
            record = JournalRecord(entry=entry, received_at=now())
            document = self._collection().find_one_and_update(
                {"_id": key, "owner_id": owner},
                {
                    "$setOnInsert": {
                        "owner_id": owner,
                        "deleted": False,
                        "content_hash": digest,
                        "record": record.model_dump(),
                    }
                },
                upsert=True,
                return_document=True,
            )
            if document.get("deleted"):
                raise MissionError("journal_entry_deleted", 410)
            if document.get("content_hash") != digest:
                raise MissionError("journal_entry_conflict", 409)
            self._record(document, owner)
        except MissionError:
            raise
        except Exception:
            raise MissionError("journal_unavailable") from None

    def page(self, owner: str, after: str | None):
        try:
            query: dict = {"owner_id": owner, "deleted": False}
            if after:
                query["_id"] = {"$gt": f"{owner}:{after}"}
            documents = list(self._collection().find(query).sort("_id", 1).limit(21))
            records = [self._record(document, owner) for document in documents[:20]]
            return JournalPage(
                owner_id=owner,
                entries=records,
                next_after=records[-1].entry.id if len(documents) > 20 else None,
            )
        except MissionError:
            raise
        except Exception:
            raise MissionError("journal_unavailable") from None

    def selected(self, owner: str, entry_ids: list[str]) -> list[JournalRecord]:
        try:
            if not entry_ids or len(entry_ids) > 3 or len(set(entry_ids)) != len(entry_ids):
                raise MissionError("invalid_request", 422)
            keys = [f"{owner}:{entry_id}" for entry_id in entry_ids]
            documents = list(
                self._collection().find({"_id": {"$in": keys}, "owner_id": owner, "deleted": False})
            )
            records = {
                record.entry.id: record
                for record in (self._record(row, owner) for row in documents)
            }
            if set(records) != set(entry_ids):
                raise MissionError("journal_source_not_found", 404)
            return [records[entry_id] for entry_id in entry_ids]
        except MissionError:
            raise
        except Exception:
            raise MissionError("journal_unavailable") from None

    def delete(self, owner: str, entry_id: str):
        try:
            result = self._collection().replace_one(
                {"_id": f"{owner}:{entry_id}", "owner_id": owner},
                {"_id": f"{owner}:{entry_id}", "owner_id": owner, "deleted": True},
                upsert=True,
            )
            if not result.acknowledged:
                raise MissionError("journal_unavailable")
        except MissionError:
            raise
        except Exception:
            raise MissionError("journal_unavailable") from None

    def close(self):
        with self._lock:
            if self._client is not None:
                self._client.close()
                self._client = None
