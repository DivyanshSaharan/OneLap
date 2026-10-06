import os
import re
from dataclasses import dataclass, field
from importlib.util import find_spec
from urllib.parse import parse_qsl, urlsplit
from uuid import NAMESPACE_URL, uuid5

from .config import boolean
from .journal_models import JournalStatus, identifier

PERSONAL_OWNER = str(
    uuid5(NAMESPACE_URL, "https://github.com/DivyanshSaharan/OneLap#personal-journal")
)


@dataclass(frozen=True, slots=True)
class JournalSettings:
    enabled: bool = False
    sharing_approved: bool = False
    owner_id: str = PERSONAL_OWNER
    uri: str = field(default="", repr=False)
    database: str = "onelap"

    def __post_init__(self):
        if self.owner_id:
            identifier(self.owner_id)
        if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,47}", self.database):
            raise ValueError("Invalid journal database name")
        if self.uri:
            try:
                parsed = urlsplit(self.uri)
                if (
                    parsed.scheme != "mongodb+srv"
                    or not parsed.hostname
                    or not parsed.hostname.endswith(".mongodb.net")
                    or not parsed.username
                    or not parsed.password
                    or parsed.fragment
                    or parsed.port is not None
                ):
                    raise ValueError
                options = [
                    (key.lower(), value.lower())
                    for key, value in parse_qsl(parsed.query, keep_blank_values=True)
                ]
                insecure = {
                    "tlsinsecure",
                    "tlsallowinvalidcertificates",
                    "tlsallowinvalidhostnames",
                }
                if any(
                    (key in insecure and value != "false")
                    or (key in {"tls", "ssl"} and value != "true")
                    for key, value in options
                ):
                    raise ValueError
            except ValueError:
                raise ValueError("Atlas URI must use authenticated SRV with verified TLS") from None

    @classmethod
    def from_environment(cls):
        return cls(
            enabled=boolean("ONELAP_JOURNAL_ENABLED"),
            sharing_approved=boolean("ONELAP_ATLAS_SHARING_APPROVED"),
            owner_id=os.environ.get("ONELAP_OWNER_ID") or PERSONAL_OWNER,
            uri=os.environ.get("MONGODB_URI", ""),
            database=os.environ.get("ONELAP_MONGODB_DATABASE", "onelap"),
        )

    def disabled_reason(self):
        if not self.enabled:
            return "journal_disabled"
        if not self.sharing_approved:
            return "atlas_sharing_not_approved"
        if not self.owner_id or not self.uri:
            return "journal_not_configured"
        if find_spec("pymongo") is None:
            return "journal_dependencies_missing"
        return None

    def status(self):
        reason = self.disabled_reason()
        return JournalStatus(
            enabled=reason is None,
            disabled_reason=reason,
            owner_id=self.owner_id if reason is None else None,
        )
