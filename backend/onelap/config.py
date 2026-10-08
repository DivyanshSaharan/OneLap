import os
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

MODEL = "Qwen/Qwen3.5-4B"
ROOT = Path(__file__).resolve().parents[2]


def boolean(name: str) -> bool:
    value = os.environ.get(name, "false").lower()
    if value not in {"true", "false"}:
        raise ValueError(f"{name} must be true or false")
    return value == "true"


@dataclass(frozen=True, slots=True)
class Settings:
    access_token: str = field(default="", repr=False)
    api_key: str = field(default="", repr=False)
    hosted_enabled: bool = False
    data_sharing_approved: bool = False
    reflection_sharing_approved: bool = False
    budget_microdollars: int = 0
    max_model_requests: int = 20
    data_dir: Path = ROOT / ".data"

    def __post_init__(self):
        if self.access_token and not (32 <= len(self.access_token) <= 256):
            raise ValueError("Access token must be 32-256 characters")
        if self.access_token and not self.access_token.isascii():
            raise ValueError("Access token must be ASCII")
        if self.access_token and any(char.isspace() for char in self.access_token):
            raise ValueError("Access token must not contain whitespace")
        if (
            type(self.budget_microdollars) is not int
            or not 0 <= self.budget_microdollars <= 10_000_000
        ):
            raise ValueError("Budget must be between zero and ten USD")
        if type(self.max_model_requests) is not int or not 1 <= self.max_model_requests <= 100:
            raise ValueError("Request limit must be 1-100")

    @classmethod
    def from_environment(cls):
        try:
            dollars = Decimal(os.environ.get("ONELAP_APPROVED_BUDGET_USD", "0"))
            micros = dollars * 1_000_000
            if not dollars.is_finite() or micros != micros.to_integral_value():
                raise ValueError
            budget = int(micros)
            maximum = int(os.environ.get("ONELAP_MAX_MODEL_REQUESTS", "20"))
        except (InvalidOperation, ValueError, OverflowError):
            raise ValueError("Invalid OneLap budget or request limit") from None
        return cls(
            access_token=os.environ.get("ONELAP_ACCESS_TOKEN", ""),
            api_key=os.environ.get("TINKER_API_KEY", ""),
            hosted_enabled=boolean("ONELAP_HOSTED_REQUESTS_ENABLED"),
            data_sharing_approved=boolean("ONELAP_DATA_SHARING_APPROVED"),
            reflection_sharing_approved=boolean("ONELAP_REFLECTION_SHARING_APPROVED"),
            budget_microdollars=budget,
            max_model_requests=maximum,
        )

    def disabled_reason(self) -> str | None:
        if not self.hosted_enabled:
            return "hosted_requests_disabled"
        if not self.data_sharing_approved:
            return "data_sharing_not_approved"
        if self.budget_microdollars == 0:
            return "budget_not_approved"
        if not self.api_key:
            return "provider_not_configured"
        return None
