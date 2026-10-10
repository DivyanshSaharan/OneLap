"""Default to a local preflight; --live uses the configured services exactly once."""

import argparse
import hashlib
import json
from dataclasses import replace
from importlib.util import find_spec
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

from .budget import BudgetLedger, reservation
from .config import ROOT, Settings
from .errors import MissionError
from .journal_config import JournalSettings
from .models import MissionResponse
from .policy import validate_plan
from .provider import MAX_INPUT_TOKENS, MAX_OUTPUT_TOKENS, Runtime, parse_plan
from .provider_json import unique_keys
from .smoke_workflow import OBSERVATION, REQUEST, run_workflow

MODEL_REQUESTS = 2


class CapturedRuntime:
    """Capture synthetic-test replies before parsing, without adding model requests."""

    def __init__(self, runtime: Runtime, outputs: list[dict]):
        self.runtime = runtime
        self.outputs = outputs

    def encode(self, messages: list[dict[str, str]]) -> list[int]:
        return self.runtime.encode(messages)

    def sample(self, tokens: list[int]) -> str:
        text = self.runtime.sample(tokens)
        self.outputs.append(
            {
                "sample_index": len(self.outputs) + 1,
                "text": text[:8192],
                "truncated_in_report": len(text) > 8192,
            }
        )
        return text


def preflight(
    settings: Settings,
    journal: JournalSettings,
    *,
    available=find_spec,
    model_requests=MODEL_REQUESTS,
) -> dict:
    """Read configuration/ledger only; never initialize a model or Atlas client."""
    blockers = []
    gates = {
        "hosted_requests_disabled": settings.hosted_enabled,
        "data_sharing_not_approved": settings.data_sharing_approved,
        "reflection_sharing_not_approved": settings.reflection_sharing_approved,
        "budget_not_approved": settings.budget_microdollars > 0,
        "provider_not_configured": bool(settings.api_key),
        "journal_disabled": journal.enabled,
        "atlas_sharing_not_approved": journal.sharing_approved,
        "journal_not_configured": bool(journal.uri and journal.owner_id),
    }
    blockers.extend(code for code, enabled in gates.items() if not enabled)
    dependencies = {
        name: available(name) is not None
        for name in ("tinker", "transformers", "jinja2", "pymongo", "httpx")
    }
    if not all(dependencies.values()):
        blockers.append("smoke_dependencies_missing")
    worst_reservation = model_requests * reservation(MAX_INPUT_TOKENS, MAX_OUTPUT_TOKENS)
    budget = {"approved_usd": settings.budget_microdollars / 1_000_000}
    try:
        ledger = BudgetLedger(settings.data_dir).snapshot()
        budget.update(
            reserved_usd=ledger["reserved_microdollars"] / 1_000_000,
            reserved_requests=ledger["reserved_requests"],
            required_worst_case_estimated_usd=worst_reservation / 1_000_000,
        )
        if settings.budget_microdollars and (
            ledger["reserved_microdollars"] + worst_reservation > settings.budget_microdollars
        ):
            blockers.append("insufficient_smoke_budget")
        if ledger["reserved_requests"] + model_requests > settings.max_model_requests:
            blockers.append("insufficient_smoke_request_allowance")
    except MissionError as error:
        blockers.append(error.code)
    return {
        "mode": "preflight",
        "ready": not blockers,
        "blockers": blockers,
        "dependencies": dependencies,
        "credentials_present": {
            "tinker": bool(settings.api_key),
            "atlas": bool(journal.uri),
        },
        "budget": budget,
        "maximum_model_requests_in_run": model_requests,
        "request": REQUEST.model_dump(),
        "fictional_observation": OBSERVATION,
        "data_boundary": (
            "The fictional mission and observation are stored under a fresh test owner in Atlas. "
            "Mission inputs and that selected fictional record go to hosted Qwen through Tinker. "
            "The workflow deletes the test record and checks that replay is rejected. "
            "A content-free deletion tombstone remains. Personal journal records are not read."
        ),
        "limitations": (
            "Preflight does not verify remote credentials, model availability or database access. "
            "Budget figures are local reservations, not provider bills."
        ),
    }


def resume_mission(path: Path) -> tuple[MissionResponse, str]:
    """Reuse only a validated synthetic mission with its original captured reply."""
    if path.stat().st_size > 65_536:
        raise ValueError("Invalid resume report")
    raw = path.read_bytes()
    report = json.loads(raw, object_pairs_hook=unique_keys)
    if (
        report.get("version") != 1
        or report.get("mode") != "live"
        or report.get("synthetic") is not True
        or report.get("request") != REQUEST.model_dump()
        or report.get("observation") != OBSERVATION
    ):
        raise ValueError("Invalid resume report")
    mission = MissionResponse.model_validate_json(json.dumps(report["mission"]))
    validate_plan(mission.mission, REQUEST)
    if mission.generation.prompt_version != "mission-v1":
        raise ValueError("Resume requires a first mission")
    outputs = report.get("raw_synthetic_model_outputs", [])
    if not outputs or parse_plan(outputs[0]["text"]) != mission.mission:
        raise ValueError("Captured reply does not match the mission")
    return mission, hashlib.sha256(raw).hexdigest()


def live_run(
    settings: Settings,
    journal_settings: JournalSettings,
    *,
    source_mission: MissionResponse | None = None,
    source_hash: str | None = None,
) -> dict:
    from fastapi.testclient import TestClient

    from .journal_repository import AtlasJournal
    from .main import create_app
    from .provider import TinkerProvider, TinkerRuntime

    # A fresh test journal never fetches or deletes the resident's existing entries.
    isolated_journal = replace(journal_settings, owner_id=str(uuid4()))
    local_settings = replace(settings, serve_frontend=False)
    ledger = BudgetLedger(settings.data_dir)
    before = ledger.snapshot()
    outputs: list[dict] = []
    provider = TinkerProvider(
        local_settings,
        ledger,
        runtime_factory=lambda key: CapturedRuntime(TinkerRuntime(key), outputs),
    )
    journal = AtlasJournal(isolated_journal)
    app = create_app(local_settings, provider, isolated_journal, journal)
    headers = {"Authorization": f"Bearer {settings.access_token}"} if settings.access_token else {}
    with TestClient(
        app,
        base_url="http://127.0.0.1:8770",
        client=("127.0.0.1", 50000),
        headers=headers,
    ) as client:
        report = run_workflow(client, isolated_journal.owner_id, source_mission=source_mission)
    after = ledger.snapshot()
    report["reserved_model_requests_in_run"] = (
        after["reserved_requests"] - before["reserved_requests"]
    )
    report["estimated_reserved_usd_in_run"] = (
        after["reserved_microdollars"] - before["reserved_microdollars"]
    ) / 1_000_000
    report["raw_synthetic_model_outputs"] = outputs
    if source_mission is not None:
        report["mission_reused_from"] = {
            "mission_id": str(source_mission.id),
            "report_sha256": source_hash,
        }
    report["transport"] = "in_process_asgi_with_real_configured_services"
    return report


def save_report(report: dict, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{uuid4()}.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live",
        action="store_true",
        help="Exercise real Tinker/Atlas using the already approved server configuration.",
    )
    parser.add_argument(
        "--resume",
        type=Path,
        help="Reuse a previously validated synthetic mission; needs only one follow-up request.",
    )
    options = parser.parse_args(argv)
    load_dotenv(ROOT / ".env", override=False)
    source_mission, source_hash = None, None
    if options.resume is not None:
        try:
            source_mission, source_hash = resume_mission(options.resume)
        except Exception:
            print(json.dumps({"mode": "preflight", "error": "invalid_resume_report"}))
            return 2
    try:
        settings = Settings.from_environment()
        journal = JournalSettings.from_environment()
        readiness = preflight(
            settings, journal, model_requests=1 if source_mission else MODEL_REQUESTS
        )
    except (ValueError, OSError):
        print(json.dumps({"mode": "preflight", "ready": False, "error": "invalid_configuration"}))
        return 2
    if not options.live or not readiness["ready"]:
        print(json.dumps(readiness, indent=2))
        return 0 if readiness["ready"] else 2
    try:
        report = live_run(settings, journal, source_mission=source_mission, source_hash=source_hash)
        path = save_report(report, settings.data_dir / "smoke")
        print(json.dumps({"report": str(path), **report}, indent=2))
        return 0 if report["status"] == "passed" else 1
    except Exception:
        # Provider/database exceptions can contain credentials; never print them.
        print(json.dumps({"mode": "live", "status": "failed", "error": "smoke_runner_failed"}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
