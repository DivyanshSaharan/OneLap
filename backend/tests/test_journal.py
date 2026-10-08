from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import replace
from threading import Lock
from types import SimpleNamespace
from uuid import UUID

import pytest
from conftest import ACCESS_TOKEN, plan_for
from fastapi.testclient import TestClient
from onelap.config import Settings
from onelap.errors import MissionError
from onelap.journal_config import JournalSettings
from onelap.journal_models import MissionSnapshot, OutingInput
from onelap.journal_repository import AtlasJournal
from onelap.main import create_app
from onelap.models import GenerationIdentity, MissionPlan
from pydantic import ValidationError

OWNER = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
HEADERS = {"Authorization": f"Bearer {ACCESS_TOKEN}", "X-OneLap-Journal-Owner": OWNER}
CONFIG = JournalSettings(
    enabled=True,
    sharing_approved=True,
    owner_id=OWNER,
    uri="mongodb+srv://fictional:private-test-password@fictional.mongodb.net/",
)


class Cursor(list):
    def sort(self, key, order):
        return Cursor(sorted(self, key=lambda item: item[key], reverse=order < 0))

    def limit(self, maximum):
        return Cursor(self[:maximum])


class Collection:
    """Thread-safe offline SDK double. Never an application fallback."""

    def __init__(self):
        self.documents = {}
        self.lock = Lock()
        self.failure = False

    def find_one_and_update(self, query, update, **options):
        assert options == {"upsert": True, "return_document": True}
        if self.failure:
            raise RuntimeError("PRIVATE URI AND OBSERVATION")
        with self.lock:
            key = query["_id"]
            self.documents.setdefault(key, {"_id": key, **deepcopy(update["$setOnInsert"])})
            assert self.documents[key]["owner_id"] == query["owner_id"]
            return deepcopy(self.documents[key])

    def replace_one(self, query, document, **options):
        assert options == {"upsert": True}
        if self.failure:
            raise RuntimeError("PRIVATE DATABASE PASSWORD")
        with self.lock:
            assert query["owner_id"] == document["owner_id"]
            self.documents[query["_id"]] = deepcopy(document)
        return SimpleNamespace(acknowledged=True)

    def find(self, query):
        if self.failure:
            raise RuntimeError("PRIVATE DATABASE PASSWORD")
        identifier = query.get("_id")

        def matches_id(row):
            if identifier is None:
                return True
            if "$gt" in identifier:
                return row["_id"] > identifier["$gt"]
            return row["_id"] in identifier["$in"]

        return Cursor(
            [
                deepcopy(row)
                for row in self.documents.values()
                if row["owner_id"] == query["owner_id"]
                and row["deleted"] is False
                and matches_id(row)
            ]
        )


@pytest.fixture
def entry(mission_request):
    return OutingInput(
        id=str(UUID(int=100)),
        mission=MissionSnapshot(
            id=str(UUID(int=1)),
            mission=MissionPlan(**plan_for(mission_request)),
            generation=GenerationIdentity(),
            safety_note="Skip if unsuitable.",
        ),
        outcome="completed",
        observation="I noticed a soft shadow on a rough surface.",
        feedback="useful",
        recorded_at="2026-10-06T14:00:00.000Z",
    )


@pytest.fixture
def store():
    collection = Collection()
    creations = []
    client = SimpleNamespace(close=lambda: None)

    # Magic indexing lives on types, not individual instances.
    class Client:
        def __getitem__(self, _name):
            return self

        def close(self):
            client.close()

    class Database(Client):
        def get_collection(self, name, **options):
            from pymongo import ReadPreference

            assert name == "outings" and options["read_preference"] == ReadPreference.PRIMARY
            return collection

        def __getitem__(self, name):
            return collection if name == "outings" else self

    def factory(uri, **options):
        creations.append((uri, options))
        return Database()

    return AtlasJournal(CONFIG, client_factory=factory), collection, creations


def client_for(tmp_path, repository, config=CONFIG):
    return TestClient(
        create_app(
            Settings(access_token=ACCESS_TOKEN, data_dir=tmp_path),
            journal_settings=config,
            journal=repository,
        )
    )


def test_status_is_private_and_does_not_connect_to_atlas(tmp_path, store):
    repository, _, creations = store
    with client_for(tmp_path, repository) as client:
        assert client.get("/api/journal/status").status_code == 401
        result = client.get("/api/journal/status", headers=HEADERS)
        assert result.json()["owner_id"] == OWNER
        assert result.headers["cache-control"] == "no-store"
        assert "private-test-password" not in result.text
    assert creations == []


def test_defaults_do_not_connect_even_with_environment_uri(tmp_path, monkeypatch):
    monkeypatch.setenv("MONGODB_URI", CONFIG.uri)
    with TestClient(create_app(Settings(access_token=ACCESS_TOKEN, data_dir=tmp_path))) as client:
        response = client.get("/api/journal/status", headers=HEADERS).json()
        assert response["disabled_reason"] == "journal_disabled"
        assert response["owner_id"] is None


@pytest.mark.parametrize(
    "path,method",
    [
        ("/api/journal/entries", "get"),
        ("/api/journal/entries", "post"),
        (f"/api/journal/entries/{OWNER}", "delete"),
    ],
)
def test_unauthorized_journal_requests_never_connect(tmp_path, store, path, method):
    repository, _, creations = store
    with client_for(tmp_path, repository) as client:
        response = getattr(client, method)(path)
        assert response.status_code == 401
        assert response.headers["cache-control"] == "no-store"
    assert creations == []


def test_retry_is_idempotent_and_content_conflicts_are_not_overwritten(tmp_path, store, entry):
    repository, collection, creations = store
    with client_for(tmp_path, repository) as client:
        body = {"owner_id": OWNER, "entry": entry.model_dump()}
        first = client.post("/api/journal/entries", headers=HEADERS, json=body)
        assert first.status_code == 200
        assert (
            client.post("/api/journal/entries", headers=HEADERS, json=body).json() == first.json()
        )
        body["entry"]["observation"] = "A different observation"
        assert client.post("/api/journal/entries", headers=HEADERS, json=body).status_code == 409
        page = client.get("/api/journal/entries", headers=HEADERS).json()
        assert page["entries"][0]["entry"]["observation"] == entry.observation
        assert page["entries"][0]["mission_source"] == "client_submitted"
    assert len(collection.documents) == len(creations) == 1
    assert creations[0][1]["retryWrites"] is False
    assert creations[0][1]["tls"] is True
    assert creations[0][1]["w"] == "majority"


def test_other_owner_cannot_read_save_or_delete(tmp_path, store, entry):
    repository, _, creations = store
    with client_for(tmp_path, repository) as client:
        headers = {**HEADERS, "X-OneLap-Journal-Owner": OTHER}
        assert client.get("/api/journal/entries", headers=headers).status_code == 409
        assert client.delete(f"/api/journal/entries/{entry.id}", headers=headers).status_code == 409
        assert (
            client.post(
                "/api/journal/entries",
                headers=HEADERS,
                json={"owner_id": OTHER, "entry": entry.model_dump()},
            ).status_code
            == 409
        )
    assert creations == []


def test_deletion_removes_text_and_retries_cannot_resurrect_it(tmp_path, store, entry):
    repository, collection, _ = store
    with client_for(tmp_path, repository) as client:
        body = {"owner_id": OWNER, "entry": entry.model_dump()}
        client.post("/api/journal/entries", headers=HEADERS, json=body)
        for _ in range(2):
            assert (
                client.delete(f"/api/journal/entries/{entry.id}", headers=HEADERS).json()["status"]
                == "deleted"
            )
        assert client.get("/api/journal/entries", headers=HEADERS).json()["entries"] == []
        assert client.post("/api/journal/entries", headers=HEADERS, json=body).status_code == 410
    assert list(collection.documents.values()) == [
        {"_id": f"{OWNER}:{entry.id}", "owner_id": OWNER, "deleted": True}
    ]


def test_deletion_before_a_delayed_first_upload_still_blocks_it(store, entry):
    repository, _, _ = store
    repository.delete(OWNER, entry.id)
    with pytest.raises(MissionError, match="journal_entry_deleted"):
        repository.save(OWNER, entry)


def test_concurrent_replays_create_only_one_record(store, entry):
    repository, collection, _ = store
    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(lambda _: repository.save(OWNER, entry), range(12)))
    assert len(collection.documents) == 1


def test_owner_scoped_stable_pagination(store, entry):
    repository, _, _ = store
    for index in range(25):
        repository.save(OWNER, entry.model_copy(update={"id": str(UUID(int=100 + index))}))
    repository.save(OTHER, entry)
    page = repository.page(OWNER, None)
    assert len(page.entries) == 20
    second = repository.page(OWNER, page.next_after)
    assert len(second.entries) == 5 and second.next_after is None
    assert len({row.entry.id for row in [*page.entries, *second.entries]}) == 25
    assert len(repository.page(OTHER, None).entries) == 1


def test_selected_records_are_owner_scoped_and_keep_requested_order(store, entry):
    repository, _, _ = store
    previous = entry.model_copy(
        update={
            "id": str(UUID(int=101)),
            "recorded_at": "2026-10-05T14:00:00.000Z",
        }
    )
    repository.save(OWNER, entry)
    repository.save(OWNER, previous)

    selected = repository.selected(OWNER, [entry.id, previous.id])
    assert [record.entry.id for record in selected] == [entry.id, previous.id]
    with pytest.raises(MissionError, match="journal_source_not_found"):
        repository.selected(OTHER, [entry.id])

    repository.delete(OWNER, previous.id)
    with pytest.raises(MissionError, match="journal_source_not_found"):
        repository.selected(OWNER, [previous.id])


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"enabled": False}, "journal_disabled"),
        ({"sharing_approved": False}, "atlas_sharing_not_approved"),
        ({"owner_id": ""}, "journal_not_configured"),
        ({"uri": ""}, "journal_not_configured"),
    ],
)
def test_approval_gates_block_client_initialization(entry, changes, reason):
    creations = []
    repository = AtlasJournal(
        replace(CONFIG, **changes), client_factory=lambda *args, **kwargs: creations.append(args)
    )
    with pytest.raises(MissionError, match=reason):
        repository.save(OWNER, entry)
    assert creations == []


def test_provider_exceptions_do_not_echo_notes_or_uri(tmp_path, store, entry):
    repository, collection, _ = store
    collection.failure = True
    with client_for(tmp_path, repository) as client:
        response = client.post(
            "/api/journal/entries",
            headers=HEADERS,
            json={"owner_id": OWNER, "entry": entry.model_dump()},
        )
        assert response.status_code == 503
        assert response.json() == {"error": "journal_unavailable"}
        assert "PRIVATE" not in response.text


@pytest.mark.parametrize(
    "change",
    [
        {"id": {"$ne": None}},
        {"outcome": "tracked"},
        {"observation": " padded "},
        {"observation": ""},
        {"observation": "x" * 1001},
        {"observation": "private\u200btext"},
        {"recorded_at": "2026-10-06"},
        {"feedback": 5},
        {"location": "PRIVATE LOCATION"},
    ],
)
def test_journal_validation_does_not_echo_freeform_values(tmp_path, store, entry, change):
    repository, _, creations = store
    body = {"owner_id": OWNER, "entry": {**entry.model_dump(), **change}}
    with client_for(tmp_path, repository) as client:
        response = client.post("/api/journal/entries", headers=HEADERS, json=body)
        assert response.status_code == 422
        assert response.json() == {"error": "invalid_request"}
    assert creations == []


def test_stopped_and_skipped_accept_empty_observations(entry):
    for outcome in ("stopped", "skipped"):
        OutingInput.model_validate({**entry.model_dump(), "outcome": outcome, "observation": ""})
    with pytest.raises(ValidationError):
        OutingInput.model_validate(
            {**entry.model_dump(), "recorded_at": "2026-02-30T00:00:00.000Z"}
        )


@pytest.mark.parametrize(
    "uri",
    [
        "mongodb://localhost/",
        "mongodb+srv://user:SECRET@host.example/",
        "mongodb+srv://user:SECRET@host.mongodb.net/?tls=false",
        "mongodb+srv://user:SECRET@host.mongodb.net/?tlsAllowInvalidCertificates=true",
    ],
)
def test_insecure_or_non_atlas_uris_are_redacted(uri):
    with pytest.raises(ValueError) as error:
        JournalSettings(uri=uri)
    assert "SECRET" not in str(error.value)
    assert "private-test-password" not in repr(CONFIG)


def test_actual_driver_accepts_options_without_connecting(store, entry):
    from pymongo import MongoClient

    repository, _, creations = store
    repository.save(OWNER, entry)
    # connect=False prevents background connection; this verifies SDK options only.
    client = MongoClient("mongodb://127.0.0.1:1", **creations[0][1])
    try:
        database = client.get_database("onelap")
        assert database.write_concern.document["w"] == "majority"
        assert database.read_concern.level == "majority"
    finally:
        client.close()
