"""Explicit browser-test doubles; never an application or live-test fallback."""

import json
from threading import Lock

from .errors import MissionError
from .journal_models import JournalPage, JournalRecord
from .journal_repository import now


class FixtureRuntime:
    def __init__(self, request):
        plan = {
            **request.model_dump(),
            "title": "FIXTURE — notice a texture",
            "instruction": (
                "If a texture catches your attention, notice it from a comfortable spot."
            ),
            "remember": "Remember one texture; skip the task if it does not fit.",
            "requires_camera": False,
            "phone_use": "none_during_outing",
        }
        self.outputs = iter(
            [
                json.dumps(plan),
                json.dumps(
                    {
                        "reflection": "FIXTURE — you wanted a gentler texture task.",
                        "mission": {
                            **plan,
                            "title": "FIXTURE — a gentler texture task",
                            "instruction": (
                                "If it suits you, notice just one texture from where you are."
                            ),
                        },
                    }
                ),
            ]
        )

    def encode(self, _messages):
        return [1] * 100

    def sample(self, _tokens):
        return next(self.outputs)


class FixtureJournal:
    def __init__(self, settings):
        self.settings = settings
        self.records = {}
        self.deleted = set()
        self.lock = Lock()

    def save(self, owner, entry):
        with self.lock:
            if entry.id in self.deleted:
                raise MissionError("journal_entry_deleted", 410)
            existing = self.records.get(entry.id)
            if existing and existing.entry != entry:
                raise MissionError("journal_entry_conflict", 409)
            self.records.setdefault(entry.id, JournalRecord(entry=entry, received_at=now()))

    def page(self, owner, after):
        return JournalPage(owner_id=owner, entries=list(self.records.values()), next_after=None)

    def selected(self, owner, ids):
        try:
            return [self.records[key] for key in ids]
        except KeyError:
            raise MissionError("journal_source_not_found", 404) from None

    def delete(self, owner, entry_id):
        with self.lock:
            self.records.pop(entry_id, None)
            self.deleted.add(entry_id)

    def close(self):
        pass
