import importlib.util
import json
from collections.abc import Callable
from threading import Lock
from typing import Protocol

from pydantic import ValidationError

from .budget import BudgetLedger, reservation
from .config import MODEL, Settings
from .errors import MissionError
from .models import MissionPlan, ProviderStatus
from .provider_json import unique_keys
from .tracing import Tracer

MAX_INPUT_TOKENS = 4096
MAX_OUTPUT_TOKENS = 512


class Runtime(Protocol):
    def encode(self, messages: list[dict[str, str]]) -> list[int]: ...

    def sample(self, tokens: list[int]) -> str: ...


def parse_plan(text: str) -> MissionPlan:
    try:
        if not isinstance(text, str) or len(text.encode("utf-8")) > 8192:
            raise ValueError
        data = json.loads(text, object_pairs_hook=unique_keys)
        return MissionPlan.model_validate(data)
    except (ValueError, TypeError, RecursionError, ValidationError):
        raise MissionError("invalid_model_output", 502) from None


class TinkerRuntime:
    def __init__(self, api_key: str):
        import tinker
        from tinker.lib.retry_handler import RetryConfig

        service = tinker.ServiceClient(api_key=api_key)
        self.client = service.create_sampling_client(
            base_model=MODEL,
            retry_config=RetryConfig(enable_retry_logic=False, progress_timeout=45),
        )
        if self.client.get_base_model() != MODEL:
            raise MissionError("provider_model_mismatch")
        self.tokenizer = self.client.get_tokenizer()
        self.output_token_count: int | None = None

    def encode(self, messages: list[dict[str, str]]) -> list[int]:
        return self.tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            return_dict=False,
            add_generation_prompt=True,
            enable_thinking=False,
        )

    def sample(self, tokens: list[int]) -> str:
        from tinker import types

        self.output_token_count = None
        result = self.client.sample(
            prompt=types.ModelInput.from_ints(tokens),
            num_samples=1,
            sampling_params=types.SamplingParams(
                max_tokens=MAX_OUTPUT_TOKENS,
                temperature=0.2,
                stop=["<|im_end|>"],
            ),
        ).result(timeout=45)
        output_tokens = result.sequences[0].tokens
        self.output_token_count = len(output_tokens)
        return self.tokenizer.decode(output_tokens, skip_special_tokens=True)


class TinkerProvider:
    def __init__(
        self,
        settings: Settings,
        ledger: BudgetLedger,
        runtime_factory: Callable[[str], Runtime] = TinkerRuntime,
        sdk_available: Callable[[], bool] | None = None,
    ):
        self.settings = settings
        self.ledger = ledger
        self._factory = runtime_factory
        self._available = sdk_available or (
            lambda: all(
                importlib.util.find_spec(name) for name in ("tinker", "transformers", "jinja2")
            )
        )
        self._runtime: Runtime | None = None
        self._lock = Lock()
        self._failed = False
        self.tracer = Tracer()

    def status(self) -> ProviderStatus:
        reason = self.settings.disabled_reason()
        if reason is None and not self._available():
            reason = "provider_dependencies_missing"
        if reason is None and self._failed:
            reason = "provider_restart_required"
        data = self.ledger.snapshot()
        if reason is None and data["reserved_microdollars"] >= self.settings.budget_microdollars:
            reason = "budget_exhausted"
        if reason is None and data["reserved_requests"] >= self.settings.max_model_requests:
            reason = "model_request_limit_reached"
        return ProviderStatus(
            model=MODEL,
            enabled=reason is None,
            disabled_reason=reason,
            estimated_reserved_usd=data["reserved_microdollars"] / 1_000_000,
            approved_budget_usd=self.settings.budget_microdollars / 1_000_000,
            reserved_requests=data["reserved_requests"],
            maximum_requests=self.settings.max_model_requests,
        )

    def sample_text(self, messages: list[dict[str, str]]) -> str:
        if not self._lock.acquire(blocking=False):
            raise MissionError("generation_in_progress", 429)
        try:
            status = self.status()
            if not status.enabled:
                raise MissionError(status.disabled_reason or "provider_unavailable")
            try:
                if self._runtime is None:
                    with self.tracer.span("runtime"):
                        self._runtime = self._factory(self.settings.api_key)
                with self.tracer.span("encode"):
                    tokens = self._runtime.encode(messages)
                if not tokens or len(tokens) > MAX_INPUT_TOKENS:
                    raise MissionError("input_token_limit", 422)
                estimated = reservation(len(tokens), MAX_OUTPUT_TOKENS)
                with self.tracer.span("reserve") as budget_span:
                    self.ledger.reserve(
                        estimated,
                        self.settings.budget_microdollars,
                        self.settings.max_model_requests,
                    )
                    budget_span.set(**{"onelap.estimated_reserved_usd": estimated / 1_000_000})
                with self.tracer.span(
                    "sample",
                    **{
                        "gen_ai.operation.name": "chat",
                        "gen_ai.agent.name": "OneLap",
                        "gen_ai.provider.name": "tinker",
                        "gen_ai.request.model": MODEL,
                        "gen_ai.request.max_tokens": MAX_OUTPUT_TOKENS,
                        "gen_ai.usage.input_tokens": len(tokens),
                    },
                ) as model_span:
                    text = self._runtime.sample(tokens)
                    model_span.set(
                        **{
                            "gen_ai.response.model": MODEL,
                            "gen_ai.usage.output_tokens": getattr(
                                self._runtime, "output_token_count", None
                            ),
                        }
                    )
            except MissionError:
                raise
            except Exception:
                self._failed = True
                raise MissionError("provider_failed_restart_required") from None
            return text
        finally:
            self._lock.release()

    def generate(self, messages: list[dict[str, str]]) -> MissionPlan:
        text = self.sample_text(messages)
        with self.tracer.span("mission_parsing"):
            return parse_plan(text)
