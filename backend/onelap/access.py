from ipaddress import ip_address
from urllib.parse import urlsplit

from fastapi import Request

LOCAL_PORTS = {4174, 5174, 8770}


def loopback(value: str) -> bool:
    try:
        return ip_address(value).is_loopback
    except ValueError:
        return False


def local_authority(value: str) -> bool:
    try:
        parsed = urlsplit("//" + value)
        return (
            parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            and parsed.port in LOCAL_PORTS
            and parsed.username is None
            and parsed.password is None
            and not parsed.path
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        return False


def local_request(request: Request) -> bool:
    client = request.client
    server = request.scope.get("server")
    if not client or not loopback(client.host) or not server or not loopback(server[0]):
        return False
    if not local_authority(request.headers.get("host", "")):
        return False
    if any(
        key in request.headers
        for key in ("forwarded", "x-forwarded-for", "x-forwarded-host", "x-forwarded-proto")
    ):
        return False
    if request.headers.get("sec-fetch-site") == "cross-site":
        return False
    origin = request.headers.get("origin")
    if origin is not None:
        try:
            parsed = urlsplit(origin)
            if parsed.scheme != "http" or not local_authority(parsed.netloc):
                return False
            if parsed.path or parsed.query or parsed.fragment:
                return False
        except ValueError:
            return False
    return True
