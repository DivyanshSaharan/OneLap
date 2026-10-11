import os
from dataclasses import dataclass, field
from urllib.parse import urlsplit


@dataclass(frozen=True, slots=True)
class AuthSettings:
    client_id: str = ""
    signing_key: str = field(default="", repr=False)
    origins: tuple[str, ...] = (
        "http://localhost:4174",
        "http://localhost:5174",
        "http://localhost:8770",
    )
    session_seconds: int = 86400

    def __post_init__(self):
        if self.client_id and (
            not self.client_id.endswith(".apps.googleusercontent.com")
            or len(self.client_id) > 256
            or not self.client_id.isascii()
            or len(self.signing_key) < 24
        ):
            raise ValueError("Google authentication requires a client ID and private signing key")
        if not self.origins or not 300 <= self.session_seconds <= 86400:
            raise ValueError("Invalid authentication settings")
        for origin in self.origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"https", "http"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
                or (parsed.scheme == "http" and parsed.hostname != "localhost")
                or "*" in origin
            ):
                raise ValueError("Auth origins must be HTTPS or localhost, without paths")
            if parsed.port == 0:
                raise ValueError("Invalid auth origin port")

    @property
    def enabled(self):
        return bool(self.client_id)

    @classmethod
    def from_environment(cls):
        return cls(
            client_id=os.environ.get("GOOGLE_CLIENT_ID", ""),
            signing_key=os.environ.get("GOOGLE_CLIENT_SECRET", ""),
            origins=tuple(
                item.strip()
                for item in os.environ.get("ONELAP_AUTH_ORIGINS", ",".join(cls().origins)).split(
                    ","
                )
            ),
        )
