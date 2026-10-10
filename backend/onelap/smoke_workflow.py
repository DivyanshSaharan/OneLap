"""Exercise the API with one isolated, explicitly fictional journal entry."""

import re
from time import perf_counter
from uuid import uuid4

from .journal_models import (
    FollowUpResponse,
    JournalAck,
    JournalPage,
    MissionSnapshot,
    OutingInput,
)
from .journal_repository import now
from .models import MissionRequest, MissionResponse

REQUEST = MissionRequest(
    minutes=15,
    setting="courtyard",
    conditions="evening",
    focus="textures",
)
OBSERVATION = (
    "Fictional integration-test observation, not a real outing: "
    "I noticed a rough surface next to a smooth one. "
    "Comparing the two was easy, but I would prefer a gentler task next time."
)


class SmokeFailure(Exception):
    def __init__(self, code: str):
        self.code = code if re.fullmatch(r"[a-z0-9_]{1,80}", code) else "invalid_response"
        super().__init__(self.code)


def response_json(response, expected_status=200):
    if response.status_code != expected_status:
        try:
            code = response.json().get("error", "unexpected_status")
        except (ValueError, AttributeError):
            code = "invalid_response"
        raise SmokeFailure(code if isinstance(code, str) else "invalid_response")
    return response.json()


def run_workflow(
    client, owner: str, *, mode="live", source_mission: MissionResponse | None = None
) -> dict:
    """The client targets the real ASGI app; only tests replace its dependencies."""
    entry_id = str(uuid4())
    report = {
        "version": 1,
        "mode": mode,
        "synthetic": True,
        "status": "running",
        "started_at": now(),
        "test_owner_id": owner,
        "test_entry_id": entry_id,
        "request": REQUEST.model_dump(),
        "observation": OBSERVATION,
        "steps": [],
        "cleanup": "not_needed",
        "semantic_review": "pending_human_review",
    }
    owner_headers = {"X-OneLap-Journal-Owner": owner}
    upload_attempted = False

    def step(name, operation):
        started = perf_counter()
        result = {"name": name, "status": "failed"}
        report["steps"].append(result)
        try:
            value = operation()
            result["status"] = "passed"
            return value
        finally:
            result["elapsed_ms"] = round((perf_counter() - started) * 1000, 2)

    def check_ack(response, status):
        ack = JournalAck.model_validate(response_json(response))
        if ack.owner_id != owner or ack.id != entry_id or ack.status != status:
            raise SmokeFailure("journal_ack_mismatch")

    def load_entries():
        page = JournalPage.model_validate(
            response_json(client.get("/api/journal/entries", headers=owner_headers))
        )
        if page.owner_id != owner or page.next_after is not None:
            raise SmokeFailure("journal_page_mismatch")
        return page.entries

    try:

        def generate_mission():
            response = client.post("/api/missions", json=REQUEST.model_dump())
            response_json(response, 201)
            return MissionResponse.model_validate_json(response.text)

        mission = (
            step("reuse_validated_mission", lambda: source_mission)
            if source_mission is not None
            else step("generate_mission", generate_mission)
        )
        report["mission"] = mission.model_dump(mode="json")
        entry = OutingInput(
            id=entry_id,
            mission=MissionSnapshot(
                id=str(mission.id),
                mission=mission.mission,
                generation=mission.generation,
                safety_note=mission.safety_note,
            ),
            outcome="completed",
            observation=OBSERVATION,
            feedback="too_difficult",
            recorded_at=now(),
        )
        upload = {"owner_id": owner, "entry": entry.model_dump()}

        def upload_once():
            check_ack(client.post("/api/journal/entries", json=upload), "stored")

        # A failed reply might still mean Atlas stored the entry; clean up that ID too.
        upload_attempted = True
        step("store_observation", upload_once)
        step("repeat_identical_upload", upload_once)

        def verify_readback():
            rows = load_entries()
            if len(rows) != 1 or rows[0].entry != entry:
                raise SmokeFailure("journal_readback_mismatch")

        step("read_back_exact_observation", verify_readback)

        def verify_owner_boundary():
            response = client.get(
                "/api/journal/entries",
                headers={"X-OneLap-Journal-Owner": str(uuid4())},
            )
            if response.status_code != 409 or response.json() != {
                "error": "journal_owner_mismatch"
            }:
                raise SmokeFailure("journal_owner_boundary_failed")

        step("reject_other_owner", verify_owner_boundary)

        def generate_followup():
            response = client.post(
                "/api/followups",
                headers=owner_headers,
                json={"source_id": entry_id, "context_ids": []},
            )
            response_json(response)
            followup = FollowUpResponse.model_validate_json(response.text)
            if followup.source_ids != [entry_id]:
                raise SmokeFailure("followup_source_mismatch")
            report["followup"] = followup.model_dump(mode="json")

        step("reflect_and_adapt", generate_followup)
        report["status"] = "passed"
    except Exception as error:
        report["status"] = "failed"
        report["error"] = error.code if isinstance(error, SmokeFailure) else "smoke_failed"
    finally:
        if upload_attempted:
            report["cleanup"] = "failed"
            try:

                def verify_cleanup():
                    check_ack(
                        client.delete(f"/api/journal/entries/{entry_id}", headers=owner_headers),
                        "deleted",
                    )
                    if load_entries():
                        raise SmokeFailure("journal_cleanup_not_verified")
                    replay = client.post("/api/journal/entries", json=upload)
                    if replay.status_code != 410 or replay.json() != {
                        "error": "journal_entry_deleted"
                    }:
                        raise SmokeFailure("deleted_entry_replayed")

                step("delete_verify_and_reject_replay", verify_cleanup)
                report["cleanup"] = "verified"
            except Exception as error:
                report["status"] = "failed"
                report["cleanup_error"] = (
                    error.code if isinstance(error, SmokeFailure) else "journal_cleanup_failed"
                )
        report["finished_at"] = now()
    return report
