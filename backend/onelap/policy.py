import re

from .errors import MissionError
from .models import MissionPlan, MissionRequest

PROHIBITED = re.compile(
    r"\b(?:photograph\w*|photos?|camera|selfie\w*|record\w*|screens?|gps|maps?|"
    r"touch\w*|pluck\w*|collect\w*|taste\w*|eat|feed|climb\w*|strangers?)\b|"
    r"\b(?:pick\s+up|cross\s+(?:a\s+|the\s+)?road|close\s+your\s+eyes)\b|"
    r"https?://|www\.",
    re.IGNORECASE,
)


def validate_plan(plan: MissionPlan, request: MissionRequest) -> None:
    for field in ("minutes", "setting", "conditions", "focus"):
        if getattr(plan, field) != getattr(request, field):
            raise MissionError("mission_constraint_mismatch", 502)
    text = " ".join((plan.title, plan.instruction, plan.remember))
    if PROHIBITED.search(text):
        raise MissionError("mission_policy_rejected", 502)
