from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

PUBLIC_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".svg": "image/svg+xml",
    ".webmanifest": "application/manifest+json",
}


class FrontendFiles(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if isinstance(response, FileResponse):
            # Windows registry MIME mappings must not break module scripts or the worker.
            media_type = PUBLIC_TYPES.get(Path(response.path).suffix.lower())
            if media_type:
                response.headers["content-type"] = media_type
        return response
