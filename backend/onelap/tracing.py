"""Opt-in, metadata-only tracing; no prompts, journal fields or exception text."""

import importlib
import math
import os
import re
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlsplit

from .config import MODEL, boolean
from .errors import MissionError

SPECS = {
    "mission": ("gen_ai.invoke_agent", "invoke_agent OneLap"),
    "followup": ("gen_ai.invoke_agent", "invoke_agent OneLap"),
    "journal_save": ("onelap.workflow", "OneLap journal save"),
    "journal_load": ("onelap.workflow", "OneLap journal load"),
    "journal_delete": ("onelap.workflow", "OneLap journal delete"),
    "runtime": ("onelap.model.setup", "Initialize Qwen runtime"),
    "encode": ("onelap.model.encode", "Encode bounded prompt"),
    "reserve": ("onelap.budget.reserve", "Reserve estimated spend"),
    "sample": ("gen_ai.chat", f"chat {MODEL}"),
    "mission_parsing": ("onelap.parse", "Parse mission JSON"),
    "mission_validation": ("onelap.validate", "Validate mission"),
    "followup_validation": ("onelap.validate", "Validate follow-up"),
    "retrieval": ("gen_ai.execute_tool", "execute_tool atlas_selected"),
    "persist": ("db", "Store journal entry"),
    "load": ("db", "Load journal page"),
    "delete": ("db", "Delete journal content"),
}
ROOTS = {"mission", "followup", "journal_save", "journal_load", "journal_delete"}
ERROR_CODES = frozenset(
    "internal_error generation_in_progress hosted_requests_disabled data_sharing_not_approved "
    "reflection_sharing_not_approved budget_not_approved provider_not_configured "
    "provider_dependencies_missing provider_restart_required budget_exhausted "
    "model_request_limit_reached budget_ledger_unavailable budget_ledger_busy "
    "input_token_limit provider_model_mismatch provider_failed_restart_required "
    "invalid_model_output mission_constraint_mismatch mission_policy_rejected "
    "followup_repeated_mission journal_disabled atlas_sharing_not_approved "
    "journal_not_configured journal_owner_mismatch journal_unavailable journal_entry_deleted "
    "journal_entry_conflict journal_source_not_found followup_source_needs_observation "
    "followup_context_must_precede_source invalid_request request_rate_limited".split()
)
ENUM_DATA = {
    "gen_ai.agent.name": {"OneLap"},
    "gen_ai.operation.name": {"invoke_agent", "chat", "execute_tool"},
    "gen_ai.provider.name": {"tinker"},
    "gen_ai.request.model": {MODEL},
    "gen_ai.response.model": {MODEL},
    "gen_ai.tool.name": {"atlas_selected"},
    "gen_ai.pipeline.name": ROOTS,
    "onelap.workflow": ROOTS,
    "onelap.prompt_version": {"mission-v1", "follow-up-v2"},
    "error.type": ERROR_CODES,
}
INTEGER_DATA = {
    "gen_ai.usage.input_tokens": 4096,
    "gen_ai.usage.output_tokens": 512,
    "gen_ai.request.max_tokens": 512,
    "onelap.selected_records": 3,
}
_active: ContextVar[object | None] = ContextVar("onelap_active_tracer", default=None)


@dataclass(frozen=True, slots=True)
class TracingSettings:
    enabled: bool = False
    sharing_approved: bool = False
    dsn: str = field(default="", repr=False)

    def __post_init__(self):
        if type(self.enabled) is not bool or type(self.sharing_approved) is not bool:
            raise ValueError("Tracing gates must be booleans")
        if not self.dsn:
            return
        try:
            url = urlsplit(self.dsn)
            valid = (
                url.scheme == "https"
                and url.hostname is not None
                and url.hostname.endswith(".sentry.io")
                and url.port in {None, 443}
                and url.password is None
                and re.fullmatch(r"[A-Za-z0-9]{1,128}", url.username or "")
                and re.fullmatch(r"/[0-9]{1,20}", url.path)
                and not url.query
                and not url.fragment
            )
        except (ValueError, TypeError):
            valid = False
        if not valid:
            raise ValueError("Invalid Sentry DSN")

    @classmethod
    def from_environment(cls):
        return cls(
            enabled=boolean("ONELAP_TRACING_ENABLED"),
            sharing_approved=boolean("ONELAP_TRACE_SHARING_APPROVED"),
            dsn=os.environ.get("ONELAP_SENTRY_DSN", ""),
        )

    def disabled_reason(self):
        if not self.enabled:
            return "tracing_disabled"
        if not self.sharing_approved:
            return "trace_sharing_not_approved"
        if not self.dsn:
            return "tracing_not_configured"
        return None


def safe_data(data: dict) -> dict:
    result = {}
    if not isinstance(data, dict):
        return result
    for name, value in data.items():
        if name in ENUM_DATA and type(value) is str and value in ENUM_DATA[name]:
            result[name] = value
        elif name in INTEGER_DATA and type(value) is int and 0 <= value <= INTEGER_DATA[name]:
            result[name] = value
        elif name == "onelap.estimated_reserved_usd" and type(value) in {float, int}:
            if math.isfinite(value) and 0 <= value <= 10:
                result[name] = value
    return result


def safe_timestamp(value):
    if type(value) in {float, int} and math.isfinite(value) and 0 <= value <= 4_102_444_800:
        return value
    if type(value) is str and re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,6})?Z", value
    ):
        try:
            datetime.fromisoformat(value)
            return value
        except ValueError:
            pass
    return None


def safe_span(span: dict) -> dict | None:
    if not isinstance(span, dict):
        return None
    if type(span.get("op")) is not str or type(span.get("description")) is not str:
        return None
    if (span.get("op"), span.get("description")) not in set(SPECS.values()):
        return None
    result = {}
    for name, length in (("trace_id", 32), ("span_id", 16), ("parent_span_id", 16)):
        value = span.get(name)
        if type(value) is str and re.fullmatch(rf"[0-9a-f]{{{length}}}", value):
            result[name] = value
    for name in ("start_timestamp", "timestamp"):
        value = safe_timestamp(span.get(name))
        if value is not None:
            result[name] = value
    result.update(op=span["op"], description=span["description"])
    if type(span.get("status")) is str and span["status"] in {"ok", "internal_error"}:
        result["status"] = span["status"]
    result["data"] = safe_data(span.get("data", {}))
    return result


def filter_transaction(event: dict, _hint: dict) -> dict | None:
    """Rebuild the final payload from an allowlist, rather than redact known secrets."""
    if not isinstance(event, dict) or not isinstance(event.get("contexts"), dict):
        return None
    trace = event["contexts"].get("trace")
    if not isinstance(trace, dict) or not isinstance(trace.get("data"), dict):
        return None
    workflow = trace["data"].get("onelap.workflow")
    if type(workflow) is not str or workflow not in ROOTS or event.get("type") != "transaction":
        return None
    if (trace.get("op"), event.get("transaction")) != SPECS[workflow]:
        return None
    clean_trace = safe_span({**trace, "description": event["transaction"]})
    if clean_trace is None or "trace_id" not in clean_trace or "span_id" not in clean_trace:
        return None
    clean_trace.pop("description")
    spans = event.get("spans", [])
    if not isinstance(spans, list):
        return None
    result = {
        "type": "transaction",
        "transaction": event["transaction"],
        "contexts": {"trace": clean_trace},
        "spans": [clean for span in spans if (clean := safe_span(span)) is not None],
        "platform": "python",
    }
    for name in ("start_timestamp", "timestamp"):
        value = safe_timestamp(event.get(name))
        if value is not None:
            result[name] = value
    value = event.get("event_id")
    if type(value) is str and re.fullmatch(r"[0-9a-f]{32}", value):
        result["event_id"] = value
    return result


class SafeSpan:
    def __init__(self, span=None):
        self.span = span

    def set(self, **data):
        if self.span is not None:
            for name, value in safe_data(data).items():
                try:
                    self.span.set_data(name, value)
                except Exception:
                    pass

    def failed(self, error):
        code = error.code if isinstance(error, MissionError) else "internal_error"
        self.set(
            **{
                "error.type": code
                if type(code) is str and code in ERROR_CODES
                else "internal_error"
            }
        )
        if self.span is not None:
            try:
                self.span.set_status("internal_error")
            except Exception:
                pass


class Tracer:
    def __init__(self, settings: TracingSettings | None = None, *, transport=None):
        self.settings = settings or TracingSettings()
        self.client = None
        self.sdk = None
        if self.settings.disabled_reason() is not None:
            return
        try:
            self.sdk = importlib.import_module("sentry_sdk")
        except ImportError:
            raise RuntimeError("OneLap tracing dependencies are missing") from None
        self.client = self.sdk.Client(
            dsn=self.settings.dsn,
            transport=transport,
            traces_sample_rate=1.0,
            trace_lifecycle="static",
            stream_gen_ai_spans=False,
            integrations=[],
            default_integrations=False,
            auto_enabling_integrations=False,
            send_default_pii=False,
            include_local_variables=False,
            include_source_context=False,
            max_request_body_size="never",
            max_breadcrumbs=0,
            before_breadcrumb=lambda *_args: None,
            before_send=lambda *_args: None,
            before_send_transaction=filter_transaction,
            enable_logs=False,
            enable_metrics=False,
            auto_session_tracking=False,
            send_client_reports=False,
            enable_backpressure_handling=False,
            propagate_traces=False,
            trace_propagation_targets=[],
            profiles_sample_rate=0.0,
            profile_session_sample_rate=0.0,
            server_name="onelap",
            environment="prototype",
            release="onelap@0.1.0",
            debug=False,
        )

    @contextmanager
    def _operation(self, name, *, root=False, data=None):
        span = None
        stack = ExitStack()
        active_token = None
        if self.client is not None and (root or _active.get() is self):
            try:
                if root:
                    for scope_factory in (self.sdk.isolation_scope, self.sdk.new_scope):
                        stack.enter_context(scope_factory()).set_client(self.client)
                    active_token = _active.set(self)
                op, description = SPECS[name]
                span = (
                    self.sdk.start_transaction(op=op, name=description)
                    if root
                    else self.sdk.start_span(op=op, name=description)
                )
                span.__enter__()
                span.set_status("ok")
            except Exception:
                span = None
        safe = SafeSpan(span)
        safe.set(**(data or {}))
        try:
            yield safe
        except Exception as error:
            safe.failed(error)
            raise
        finally:
            if span is not None:
                try:
                    span.__exit__(None, None, None)
                except Exception:
                    pass
            if active_token is not None:
                _active.reset(active_token)
            try:
                stack.close()
            except Exception:
                pass

    def run(self, workflow, *, prompt_version=None):
        if workflow not in ROOTS:
            raise ValueError("Unknown trace workflow")
        data = {"onelap.workflow": workflow}
        if workflow in {"mission", "followup"}:
            data.update(
                {
                    "gen_ai.agent.name": "OneLap",
                    "gen_ai.operation.name": "invoke_agent",
                    "gen_ai.pipeline.name": workflow,
                    "onelap.prompt_version": prompt_version,
                }
            )
        return self._operation(workflow, root=True, data=data)

    def span(self, name, **data):
        return self._operation(name, data=data)

    def close(self):
        if self.client is not None:
            try:
                self.client.close(timeout=2)
            except Exception:
                pass
