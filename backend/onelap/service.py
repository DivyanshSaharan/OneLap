from uuid import uuid4

from .models import GenerationIdentity, MissionRequest, MissionResponse
from .policy import validate_plan
from .prompts import build_messages
from .provider import TinkerProvider


class MissionService:
    def __init__(self, provider: TinkerProvider):
        self.provider = provider

    def generate(self, request: MissionRequest) -> MissionResponse:
        plan = self.provider.generate(build_messages(request))
        validate_plan(plan, request)
        return MissionResponse(id=uuid4(), mission=plan, generation=GenerationIdentity())
