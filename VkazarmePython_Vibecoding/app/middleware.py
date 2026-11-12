"""ASGI middleware that connects the bundled frontend to the API.

This module deliberately contains no application/business logic: it only
implements cross-cutting HTTP concerns that are awkward to express as routes.

* ``GET /`` (and ``/index.html``) serves ``frontend/index.html`` so the
  single-page client is available from the same origin as the REST API.
* Every other file that exists under ``frontend/`` is served as a static
  asset, unless its path belongs to the API namespace.
* CORS headers are added to every HTTP response and preflight ``OPTIONS``
  requests are answered directly.  This keeps the frontend usable both when
  it is served by this app and when it is opened from another origin (for
  example with a local static server or directly from disk).

The middleware is intentionally dependency-free (only Starlette primitives,
which FastAPI already provides) and does not touch the route handlers, so the
OpenAPI contract stays exactly the same.
"""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from urllib.parse import unquote

from starlette.datastructures import MutableHeaders
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

#: Paths owned by the REST/WebSocket API. Static lookup never shadows them.
API_PREFIXES = (
    "/account",
    "/users",
    "/groups",
    "/chats",
    "/media",
    "/ws",
    "/docs",
    "/redoc",
    "/openapi.json",
)

DEFAULT_ALLOWED_METHODS = "GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS"
DEFAULT_ALLOWED_HEADERS = (
    "Authorization, Content-Type, Accept, Accept-Language, Origin, "
    "X-Requested-With, X-CSRF-Token"
)
DEFAULT_EXPOSED_HEADERS = "Content-Length, Content-Type, Content-Disposition"

#: ``app/middleware.py`` lives one level below the repository root.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _default_frontend_dir() -> Path:
    configured = os.environ.get("FRONTEND_DIR")
    return Path(configured).expanduser() if configured else _PROJECT_ROOT / "frontend"


class FrontendMiddleware:
    """Serve the frontend from ``/`` and make the API cross-origin friendly."""

    def __init__(
        self,
        app: ASGIApp,
        frontend_dir: str | os.PathLike[str] | None = None,
        index_file: str = "index.html",
        allow_origins: tuple[str, ...] | list[str] = ("*",),
        allow_methods: str = DEFAULT_ALLOWED_METHODS,
        allow_headers: str = DEFAULT_ALLOWED_HEADERS,
        expose_headers: str = DEFAULT_EXPOSED_HEADERS,
        max_age: int = 600,
    ) -> None:
        self.app = app
        self.frontend_dir = Path(frontend_dir) if frontend_dir is not None else _default_frontend_dir()
        self.index_file = index_file
        self.allow_origins = tuple(allow_origins)
        self.allow_methods = allow_methods
        self.allow_headers = allow_headers
        self.expose_headers = expose_headers
        self.max_age = max_age

    # ------------------------------------------------------------------
    # ASGI entry point
    # ------------------------------------------------------------------
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET").upper()
        path = scope.get("path", "/")
        origin = self._request_origin(scope)
        allowed_origin = self._allowed_origin(origin)

        # A preflight request must never reach the API: answer it here so
        # browsers get the complete set of CORS headers without a 405.
        if method == "OPTIONS":
            await self._preflight_response(allowed_origin, scope, send)
            return

        if method in ("GET", "HEAD"):
            file_path = self._resolve_static_file(path)
            if file_path is not None:
                await self._send_file(file_path, method, allowed_origin, send)
                return

        # All regular API traffic (successful and error responses alike)
        # gets CORS headers because the send wrapper sees every message.
        await self.app(scope, receive, self._wrap_send(send, allowed_origin))

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    @staticmethod
    def _request_origin(scope: Scope) -> str | None:
        for key, value in scope.get("headers", []):
            if key.lower() == b"origin":
                return value.decode("latin-1")
        return None

    @staticmethod
    def _requested_headers(scope: Scope) -> str | None:
        for key, value in scope.get("headers", []):
            if key.lower() == b"access-control-request-headers":
                return value.decode("latin-1")
        return None

    def _allowed_origin(self, origin: str | None) -> str | None:
        if "*" in self.allow_origins:
            return "*"
        if origin is not None and origin in self.allow_origins:
            return origin
        return None

    def _cors_headers(self, allowed_origin: str | None,
                      requested_headers: str | None = None) -> dict[str, str]:
        if allowed_origin is None:
            return {}
        # A wildcard needs no Origin echo; with an explicit allow-list the
        # caller has already resolved the matching request origin.
        headers = {
            "Access-Control-Allow-Origin": allowed_origin,
            "Access-Control-Allow-Methods": self.allow_methods,
            "Access-Control-Allow-Headers": requested_headers or self.allow_headers,
            "Access-Control-Expose-Headers": self.expose_headers,
            "Access-Control-Max-Age": str(self.max_age),
            "Vary": "Origin, Access-Control-Request-Method, Access-Control-Request-Headers",
        }
        return headers

    def _apply_cors(self, headers: MutableHeaders, allowed_origin: str | None,
                    requested_headers: str | None = None) -> None:
        for name, value in self._cors_headers(allowed_origin, requested_headers).items():
            if name.lower() == "vary":
                previous = headers.get("vary")
                headers["vary"] = f"{previous}, {value}" if previous else value
            elif name not in headers:
                headers[name] = value

    def _wrap_send(self, send: Send, allowed_origin: str | None) -> Send:
        async def wrapped(message: Message) -> None:
            if message["type"] == "http.response.start":
                self._apply_cors(MutableHeaders(scope=message), allowed_origin)
            await send(message)

        return wrapped

    async def _preflight_response(self, allowed_origin: str | None,
                                  scope: Scope, send: Send) -> None:
        requested_headers = self._requested_headers(scope)
        response = Response(
            status_code=200,
            headers=self._cors_headers(allowed_origin, requested_headers),
        )
        await response(scope, self._empty_receive, send)

    @staticmethod
    async def _empty_receive() -> Message:
        return {"type": "http.request", "body": b"", "more_body": False}

    # ------------------------------------------------------------------
    # Static frontend
    # ------------------------------------------------------------------
    def _resolve_static_file(self, path: str) -> Path | None:
        """Return a file from the frontend folder for this URL path, if any."""
        if path in ("/", ""):
            relative = self.index_file
        elif path == f"/{self.index_file}":
            relative = self.index_file
        else:
            cleaned = unquote(path).lstrip("/")
            if not cleaned or any(cleaned == p.lstrip("/") or cleaned.startswith(p.lstrip("/") + "/")
                                  for p in API_PREFIXES):
                return None
            relative = cleaned

        root = self.frontend_dir.resolve()
        candidate = (root / relative).resolve()
        try:
            candidate.relative_to(root)  # reject path traversal
        except ValueError:
            return None

        if candidate.is_file():
            return candidate
        return None

    async def _send_file(self, file_path: Path, method: str,
                         allowed_origin: str | None, send: Send) -> None:
        body = file_path.read_bytes()
        content_type, _ = mimetypes.guess_type(str(file_path))
        content_type = content_type or "application/octet-stream"
        if content_type.startswith("text/"):
            content_type += "; charset=utf-8"
        headers = MutableHeaders(headers={
            "content-type": content_type,
            "content-length": str(len(body)),
            "cache-control": "no-cache",
            "x-content-type-options": "nosniff",
        })
        self._apply_cors(headers, allowed_origin)
        await send({
            "type": "http.response.start",
            "status": 200,
            "headers": headers.raw,
        })
        await send({
            "type": "http.response.body",
            "body": b"" if method == "HEAD" else body,
            "more_body": False,
        })


# Convenient aliases: the class handles both concerns, but callers may look
# for either name when registering middleware.
CorsMiddleware = FrontendMiddleware
FrontendAndCorsMiddleware = FrontendMiddleware

__all__ = [
    "FrontendMiddleware",
    "FrontendAndCorsMiddleware",
    "CorsMiddleware",
    "API_PREFIXES",
]
