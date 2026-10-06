import json
from dataclasses import replace

import pytest
from onelap.budget import BudgetLedger
from onelap.config import Settings
from onelap.models import MissionRequest
from onelap.provider import TinkerProvider

ACCESS_TOKEN = "fictional-test-access-token-00000000000000"


def plan_for(request: MissionRequest) -> dict:
    return {
        "title": "Notice a small contrast",
        "instruction": (
            "Within your familiar area, notice two contrasting surfaces if you find them."
        ),
        "remember": "What difference stood out? You can skip this task if it does not fit.",
        **request.model_dump(),
        "requires_camera": False,
        "phone_use": "none_during_outing",
    }


class FakeRuntime:
    """Offline test double only; never configured as an application fallback."""

    def __init__(self, text: str):
        self.text = text
        self.tokens = [1] * 100
        self.encodings = []
        self.samples = []
        self.failure = None

    def encode(self, messages):
        self.encodings.append(messages)
        return self.tokens

    def sample(self, tokens):
        self.samples.append(tokens)
        if self.failure:
            raise self.failure
        return self.text


@pytest.fixture
def request_data():
    return {"minutes": 15, "setting": "courtyard", "conditions": "evening", "focus": "textures"}


@pytest.fixture
def mission_request(request_data):
    return MissionRequest(**request_data)


@pytest.fixture
def settings(tmp_path):
    return Settings(
        access_token=ACCESS_TOKEN,
        api_key="fictional-test-key",
        hosted_enabled=True,
        data_sharing_approved=True,
        budget_microdollars=100_000,
        data_dir=tmp_path,
    )


@pytest.fixture
def provider_factory(settings, mission_request):
    def build(*, text=None, changes=None, available=True):
        configured = replace(settings, **(changes or {}))
        runtime = FakeRuntime(text if text is not None else json.dumps(plan_for(mission_request)))
        creations = []

        def factory(key):
            creations.append(key)
            return runtime

        provider = TinkerProvider(
            configured, BudgetLedger(configured.data_dir), factory, lambda: available
        )
        return provider, runtime, creations

    return build
