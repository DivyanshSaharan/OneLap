"""Isolated production-browser workflow; remote services require explicit opt-in."""

import argparse
import hashlib
import json
import os
import secrets
import shutil
import socket
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from threading import Lock, Thread
from time import monotonic, sleep
from uuid import uuid4

from dotenv import load_dotenv

from .budget import BudgetLedger
from .config import ROOT, Settings
from .errors import MissionError
from .journal_config import JournalSettings
from .journal_repository import AtlasJournal, now
from .models import MissionRequest
from .provider import TinkerProvider, TinkerRuntime
from .smoke import CapturedRuntime, preflight

REQUEST = MissionRequest(minutes=15, setting="courtyard", conditions="daylight", focus="textures")
OBSERVATION = (
    "Fictional browser-test observation, not a real outing: "
    "I noticed a rough surface beside a smooth one. "
    "Comparing both felt too difficult; next time I would prefer to notice only one texture."
)
ORIGIN = "http://127.0.0.1:8770"


class SyntheticJournal:
    """Track attempted writes before storage; restrict cleanup to one synthetic entry."""

    def __init__(self, repository):
        self.repository = repository
        self.settings = repository.settings
        self.entry = None
        self.lock = Lock()

    def owner(self, owner):
        if owner != self.settings.owner_id:
            raise MissionError("journal_owner_mismatch", 409)

    def save(self, owner, entry):
        self.owner(owner)
        plan = entry.mission.mission
        if (
            entry.observation != OBSERVATION
            or entry.outcome != "completed"
            or entry.feedback != "too_difficult"
            or {key: getattr(plan, key) for key in MissionRequest.model_fields}
            != REQUEST.model_dump()
            or entry.mission.generation.prompt_version != "mission-v1"
        ):
            raise MissionError("synthetic_test_boundary", 422)
        with self.lock:
            if self.entry is not None and self.entry != entry:
                raise MissionError("synthetic_test_boundary", 422)
            self.entry = entry
        self.repository.save(owner, entry)

    def page(self, owner, after):
        self.owner(owner)
        if after is not None:
            raise MissionError("synthetic_test_boundary", 422)
        return self.repository.page(owner, after)

    def selected(self, owner, ids):
        self.owner(owner)
        if self.entry is None or ids != [self.entry.id]:
            raise MissionError("synthetic_test_boundary", 422)
        return self.repository.selected(owner, ids)

    def delete(self, owner, entry_id):
        self.owner(owner)
        if self.entry is None or entry_id != self.entry.id:
            raise MissionError("synthetic_test_boundary", 422)
        self.repository.delete(owner, entry_id)

    def cleanup(self):
        if self.entry is None:
            return "not_needed"
        owner = self.settings.owner_id
        self.delete(owner, self.entry.id)
        page = self.page(owner, None)
        if page.owner_id != owner or page.entries or page.next_after is not None:
            raise MissionError("journal_cleanup_not_verified")
        try:
            self.save(owner, self.entry)
        except MissionError as error:
            if error.code == "journal_entry_deleted" and error.status_code == 410:
                return "verified"
            raise
        raise MissionError("deleted_entry_replayed")

    def close(self):
        self.repository.close()


@contextmanager
def local_server(app):
    import uvicorn

    # Own the bound socket before starting; never attach to or kill an existing server.
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server = None
    thread = None
    try:
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        listener.bind(("127.0.0.1", 8770))
        listener.listen(128)
        server = uvicorn.Server(
            uvicorn.Config(app, log_level="critical", access_log=False, lifespan="on")
        )
        thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        deadline = monotonic() + 10
        while not server.started:
            if not thread.is_alive() or monotonic() >= deadline:
                raise RuntimeError("browser_server_not_ready")
            sleep(0.05)
        yield
    finally:
        if server is not None:
            server.should_exit = True
        if thread is not None:
            thread.join(timeout=10)
        listener.close()


def browser_environment():
    """The browser child receives OS runtime paths, not API keys/URIs/telemetry settings."""
    allowed = {
        "systemroot",
        "windir",
        "path",
        "pathext",
        "temp",
        "tmp",
        "userprofile",
        "localappdata",
        "appdata",
        "programfiles",
        "programfiles(x86)",
        "comspec",
    }
    result = {key: value for key, value in os.environ.items() if key.lower() in allowed}
    channel = os.environ.get("ONELAP_TEST_BROWSER", "")
    if channel and channel != "msedge":
        raise ValueError("Unsupported test browser")
    result["ONELAP_TEST_BROWSER"] = channel
    result["PLAYWRIGHT_BROWSERS_PATH"] = str(ROOT / ".data" / "playwright-browsers")
    return result


def run_browser(payload):
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("browser_node_missing")
    result = subprocess.run(
        [node, str(ROOT / "scripts" / "browser-workflow.mjs")],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=240,
        cwd=ROOT,
        env=browser_environment(),
        check=False,
    )
    return result.returncode


def run(settings, journal_settings, *, fixture=False, browser=run_browser):
    from .main import create_app

    directory = settings.data_dir / "browser-smoke"
    directory.mkdir(parents=True, exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="run-", dir=directory))
    token = secrets.token_urlsafe(32)
    owner = str(uuid4())
    isolated = replace(journal_settings, owner_id=owner)
    ledger_dir = output / "fixture-ledger" if fixture else settings.data_dir
    ledger = BudgetLedger(ledger_dir)
    before = ledger.snapshot()
    configured = replace(
        settings,
        access_token=token,
        serve_frontend=True,
        data_dir=ledger_dir,
        max_model_requests=min(settings.max_model_requests, before["reserved_requests"] + 2),
    )
    outputs = []
    if fixture:
        from .browser_fixtures import FixtureJournal, FixtureRuntime

        runtime = FixtureRuntime(REQUEST)
        provider = TinkerProvider(
            configured,
            ledger,
            lambda _key: CapturedRuntime(runtime, outputs),
            lambda: True,
        )
        repository = FixtureJournal(isolated)
    else:
        provider = TinkerProvider(
            configured,
            ledger,
            lambda key: CapturedRuntime(TinkerRuntime(key), outputs),
        )
        repository = AtlasJournal(isolated)
    journal = SyntheticJournal(repository)
    report = {
        "version": 1,
        "mode": "fixture" if fixture else "live",
        "synthetic": True,
        "status": "failed",
        "started_at": now(),
        "test_owner_id": owner,
        "request": REQUEST.model_dump(),
        "observation": OBSERVATION,
        "transport": "production_browser_over_loopback_http",
        "semantic_review": "pending_human_review",
        "physical_phone_test": False,
        "real_outing": False,
        "sentry_export": False,
        "cleanup": "not_needed",
    }
    payload = {
        "origin": ORIGIN,
        "token": token,
        "owner": owner,
        "fixture": fixture,
        "output": str(output),
        "request": REQUEST.model_dump(),
        "observation": OBSERVATION,
    }
    try:
        app = create_app(configured, provider, isolated, journal)
        with local_server(app):
            try:
                code = browser(payload)
                path = output / "browser.json"
                if path.stat().st_size > 65_536:
                    raise ValueError("Oversized browser report")
                result = json.loads(path.read_text(encoding="utf-8"))
                report["browser"] = result
                if (
                    code == 0
                    and result.get("status") == "passed"
                    and result.get("model_request_attempts") == 2
                    and result.get("blocked_requests") == 0
                    and result.get("page_errors") == 0
                ):
                    report["status"] = "passed"
                else:
                    report["error"] = "browser_workflow_failed"
            finally:
                report["test_entry_id"] = journal.entry.id if journal.entry else None
                report["cleanup"] = "failed" if journal.entry else "not_needed"
                try:
                    report["cleanup"] = journal.cleanup()
                except Exception:
                    report["status"] = "failed"
                    report["cleanup_error"] = "journal_cleanup_failed"
    except Exception:
        report["status"] = "failed"
        report.setdefault("error", "browser_runner_failed")
    finally:
        journal.close()
        after = ledger.snapshot()
        count = after["reserved_requests"] - before["reserved_requests"]
        report["reserved_model_requests_in_run"] = count
        report["estimated_reserved_usd_in_run"] = (
            after["reserved_microdollars"] - before["reserved_microdollars"]
        ) / 1_000_000
        if report["status"] == "passed" and (count != 2 or report["cleanup"] != "verified"):
            report["status"] = "failed"
            report["error"] = "browser_evidence_incomplete"
        report["raw_synthetic_model_outputs"] = outputs
        report["finished_at"] = now()
        report["frontend_index_sha256"] = hashlib.sha256(
            (settings.frontend_directory / "index.html").read_bytes()
        ).hexdigest()
        path = output / "report.json"
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report, path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--fixture", action="store_true", help="No .env or remote clients.")
    mode.add_argument("--live", action="store_true", help="Use already approved server gates.")
    parser.add_argument("--approve-synthetic-sharing", action="store_true")
    options = parser.parse_args(argv)
    try:
        if options.fixture:
            settings = Settings(
                api_key="fixture-only",
                hosted_enabled=True,
                data_sharing_approved=True,
                reflection_sharing_approved=True,
                budget_microdollars=50_000,
            )
            journal = JournalSettings(
                enabled=True,
                sharing_approved=True,
                uri="mongodb+srv://fixture:fixture@fixture.mongodb.net/",
            )
        else:
            load_dotenv(ROOT / ".env", override=False)
            settings = Settings.from_environment()
            journal = JournalSettings.from_environment()
        readiness = preflight(settings, journal)
        readiness["request"] = REQUEST.model_dump()
        readiness["fictional_observation"] = OBSERVATION
        readiness["transport"] = "production_browser_over_loopback_http"
        if not (ROOT / "dist" / "index.html").is_file():
            readiness["ready"] = False
            readiness["blockers"].append("frontend_build_missing")
        if options.live and not options.approve_synthetic_sharing:
            readiness["ready"] = False
            readiness["blockers"].append("browser_synthetic_sharing_not_approved")
        if not options.fixture and (not options.live or not readiness["ready"]):
            print(json.dumps(readiness, indent=2))
            return 0 if readiness["ready"] else 2
        if options.fixture and not (ROOT / "dist" / "index.html").is_file():
            print(json.dumps({"mode": "fixture", "error": "frontend_build_missing"}))
            return 2
        report, path = run(settings, journal, fixture=options.fixture)
        print(
            json.dumps(
                {
                    "mode": report["mode"],
                    "status": report["status"],
                    "report": str(path),
                    "cleanup": report["cleanup"],
                    "reserved_model_requests_in_run": report["reserved_model_requests_in_run"],
                }
            )
        )
        return 0 if report["status"] == "passed" else 1
    except Exception:
        print(json.dumps({"status": "failed", "error": "browser_runner_failed"}))
        return 1
