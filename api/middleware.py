"""Custom middleware: request ID injection, auth wall for web routes."""

import uuid
from typing import Callable

import structlog
from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from services.auth import decode_access_token, decode_client_access_token, decode_editor_access_token

logger = structlog.get_logger(__name__)

# Operator web routes that require access_token cookie
_PROTECTED_WEB_ROUTES = {
    "/dashboard",
    "/campaigns",
    "/submit",
    "/submissions",
    "/jobs",
    "/settings",
}

# Route prefixes that are fully protected (all sub-paths require operator auth)
_PROTECTED_WEB_PREFIXES = ("/operator",)

# Client portal prefixes — require client_access_token cookie
_PORTAL_WEB_PREFIXES = ("/portal/dashboard", "/portal/clips", "/portal/invoices", "/portal/reports")

# Editor portal — require editor_access_token cookie (separate from operator auth)
_EDITOR_WEB_ROUTES = {"/editor"}

# Routes that are public
_PUBLIC_ROUTES = {
    "/login", "/register", "/health", "/ready",
    "/portal/login", "/portal/access",
    "/editor/login",
    "/billing/checkout",
}


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

        # Operator web routes — require access_token cookie
        operator_protected = path in _PROTECTED_WEB_ROUTES or any(
            path.startswith(prefix) for prefix in _PROTECTED_WEB_PREFIXES
        )
        if operator_protected:
            token = request.cookies.get("access_token")
            if not token or decode_access_token(token) is None:
                return RedirectResponse(url="/login", status_code=302)

        # Client portal web routes — require client_access_token cookie
        portal_protected = any(path.startswith(prefix) for prefix in _PORTAL_WEB_PREFIXES)
        if portal_protected:
            token = request.cookies.get("client_access_token")
            if not token or decode_client_access_token(token) is None:
                return RedirectResponse(url="/portal/login", status_code=302)

        # Editor portal web routes — require editor_access_token cookie
        if path in _EDITOR_WEB_ROUTES:
            token = request.cookies.get("editor_access_token")
            if not token or decode_editor_access_token(token) is None:
                return RedirectResponse(url="/editor/login", status_code=302)

        return await call_next(request)
