"""FastAPI application factory."""

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from api.middleware import AuthWallMiddleware, RequestIDMiddleware
from api.routes import auth, campaigns, client_clips, clients, debug, editors, health, hooks, invoices, jobs, reports, settings, submissions, templates as clip_templates, users
from services.logger import configure_logging

APP_ENV = os.getenv("APP_ENV", "development")
configure_logging(APP_ENV)

BASE_DIR = Path(__file__).parent.parent
TEMPLATES_DIR = BASE_DIR / "web" / "templates"
STATIC_DIR = BASE_DIR / "web" / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

limiter = Limiter(key_func=get_remote_address)


def create_app() -> FastAPI:
    app = FastAPI(
        title="SUNO Clips",
        description="Automated Whop clip submission SaaS",
        version="1.0.0",
        docs_url="/api/docs" if APP_ENV != "production" else None,
        redoc_url="/api/redoc" if APP_ENV != "production" else None,
    )

    # Rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Middleware (order matters — outermost added last)
    app.add_middleware(AuthWallMiddleware)
    app.add_middleware(RequestIDMiddleware)

    if APP_ENV == "production":
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])
        app.add_middleware(
            CORSMiddleware,
            allow_origins=os.getenv("ALLOWED_ORIGINS", "").split(","),
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["*"],
        )
    else:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Static files
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # API routers
    app.include_router(auth.router)
    app.include_router(users.router)
    app.include_router(campaigns.router)
    app.include_router(jobs.router)
    app.include_router(submissions.router)
    app.include_router(settings.router)
    app.include_router(health.router)
    app.include_router(clients.router)
    app.include_router(editors.router)
    app.include_router(client_clips.router)
    app.include_router(invoices.router)
    app.include_router(reports.router)
    app.include_router(clip_templates.router)
    app.include_router(hooks.router)
    if APP_ENV != "production":
        app.include_router(debug.router)

    # --- Web page routes ---

    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse(url="/dashboard")

    @app.get("/login", include_in_schema=False)
    async def login_page(request: Request):
        return templates.TemplateResponse("login.html", {"request": request})

    @app.get("/register", include_in_schema=False)
    async def register_page(request: Request):
        return templates.TemplateResponse("register.html", {"request": request})

    @app.get("/dashboard", include_in_schema=False)
    async def dashboard_page(request: Request):
        return templates.TemplateResponse("dashboard.html", {"request": request})

    @app.get("/campaigns", include_in_schema=False)
    async def campaigns_page(request: Request):
        return templates.TemplateResponse("campaigns.html", {"request": request})

    @app.get("/submit", include_in_schema=False)
    async def submit_page(request: Request):
        return templates.TemplateResponse("submit.html", {"request": request})

    @app.get("/submissions", include_in_schema=False)
    async def submissions_page(request: Request):
        return templates.TemplateResponse("submissions.html", {"request": request})

    @app.get("/jobs", include_in_schema=False)
    async def jobs_page(request: Request):
        return templates.TemplateResponse("jobs.html", {"request": request})

    @app.get("/settings", include_in_schema=False)
    async def settings_page(request: Request):
        return templates.TemplateResponse("settings.html", {"request": request})

    @app.get("/operator", include_in_schema=False)
    async def operator_dashboard(request: Request):
        return templates.TemplateResponse("operator_dashboard.html", {"request": request})

    @app.get("/operator/clients", include_in_schema=False)
    async def operator_clients(request: Request):
        return templates.TemplateResponse("client_list.html", {"request": request})

    @app.get("/operator/clients/{client_id}", include_in_schema=False)
    async def operator_client_detail(request: Request, client_id: str):
        return templates.TemplateResponse("client_detail.html", {"request": request, "client_id": client_id})

    @app.get("/operator/hooks", include_in_schema=False)
    async def hooks_page(request: Request):
        return templates.TemplateResponse("hooks_library.html", {"request": request})

    @app.get("/operator/reports", include_in_schema=False)
    async def reports_page(request: Request):
        return templates.TemplateResponse("reports.html", {"request": request})

    @app.get("/editor", include_in_schema=False)
    async def editor_portal(request: Request):
        return templates.TemplateResponse("editor_portal.html", {"request": request})

    return app


app = create_app()
