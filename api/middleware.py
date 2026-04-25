"""Custom middleware: request ID injection, auth wall for web routes."""

import uuid
from typing import Callable

import structlog
from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from services.auth import decode_access_token

logger = structlog.get_logger(__name__)

# Web routes that require authentication (redirect to /login if missing)
_PROTECTED_WEB_ROUTES = {
    "/dashboard",
    "/campaigns",
    "/submit",
    "/submissions",
    "/jobs",
    "/settings",
    "/editor",
}

# Route prefixes that are fully protected (all sub-paths require auth)
_PROTECTED_WEB_PREFIXES = ("/operator",)

# Routes that are public
_PUBLIC_ROUTES = {"/login", "/register", "/health", "/ready"}


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique X-Request-ID to every request and bind it to structlog context."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class AuthWallMiddleware(BaseHTTPMiddleware):
    """Redirect unauthenticated users away from protected web pages."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Only apply to protected web routes (not /api/*)
        protected = path in _PROTECTED_WEB_ROUTES or any(
            path.startswith(prefix) for prefix in _PROTECTED_WEB_PREFIXES
        )
        if protected:
            token = request.cookies.get("access_token")
            if not token or decode_access_token(token) is None:
                return RedirectResponse(url="/login", status_code=302)

        return await call_next(request)
