import hashlib
from datetime import UTC, datetime
from threading import Lock
from time import time

from .errors import MissionError


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


class AtlasSessions:
    """Revocable sessions; never store raw cookies, Google tokens, names or emails."""

    def __init__(self, settings, *, client_factory=None):
        self.settings = settings
        self.factory = client_factory
        self.client = None
        self.lock = Lock()
        self.index_ready = False

    def collection(self):
        if not self.settings.uri:
            raise MissionError("auth_storage_unavailable")
        with self.lock:
            if self.client is None:
                from pymongo import MongoClient

                factory = self.factory or MongoClient
                self.client = factory(
                    self.settings.uri,
                    connect=False,
                    tls=True,
                    tlsAllowInvalidCertificates=False,
                    tlsAllowInvalidHostnames=False,
                    timeoutMS=5000,
                    serverSelectionTimeoutMS=3000,
                    connectTimeoutMS=3000,
                    retryWrites=False,
                    retryReads=False,
                    w="majority",
                    wTimeoutMS=5000,
                    readConcernLevel="majority",
                    maxPoolSize=10,
                    appname="OneLapAuth",
                )
            from pymongo import ReadPreference

            collection = self.client[self.settings.database].get_collection(
                "auth_sessions", read_preference=ReadPreference.PRIMARY
            )
            if not self.index_ready:
                collection.create_index("expires_at", expireAfterSeconds=0)
                self.index_ready = True
            return collection

    def create(self, token, owner, csrf, expires, challenge):
        try:
            from pymongo.errors import DuplicateKeyError

            collection = self.collection()
            # Unique challenge ID prevents concurrent replay across browsers and workers.
            collection.insert_one(
                {
                    "_id": "challenge:" + digest(challenge),
                    "expires_at": datetime.fromtimestamp(time() + 300, UTC),
                }
            )
            collection.insert_one(
                {
                    "_id": digest(token),
                    "owner": owner,
                    "csrf": csrf,
                    "expires_at": datetime.fromtimestamp(expires, UTC),
                }
            )
        except DuplicateKeyError:
            raise MissionError("auth_challenge_used", 401) from None
        except MissionError:
            raise
        except Exception:
            raise MissionError("auth_storage_unavailable") from None

    def get(self, token):
        try:
            return self.collection().find_one(
                {"_id": digest(token), "expires_at": {"$gt": datetime.now(UTC)}}
            )
        except MissionError:
            raise
        except Exception:
            raise MissionError("auth_storage_unavailable") from None

    def delete(self, token):
        try:
            self.collection().delete_one({"_id": digest(token)})
        except MissionError:
            raise
        except Exception:
            raise MissionError("auth_storage_unavailable") from None

    def close(self):
        with self.lock:
            if self.client is not None:
                self.client.close()
                self.client = None
                self.index_ready = False
