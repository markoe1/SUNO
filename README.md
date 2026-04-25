# SUNO Clips

Automated Whop clip submission SaaS. Submit clip URLs to Whop campaigns from a clean dashboard.

## Architecture

```
SUNO-repo/
├── api/                  FastAPI app
│   ├── app.py            App factory, middleware, route mounting
│   ├── deps.py           FastAPI dependencies (get_db, get_current_user)
│   ├── middleware.py     Request ID, structured logging, auth wall
│   └── routes/
│       ├── auth.py       register/login/logout/refresh
│       ├── campaigns.py  list, sync trigger
│       ├── jobs.py       list, cancel, kill switch
│       ├── submissions.py list, submit, retry
│       ├── settings.py   Whop cookie import, user prefs
│       ├── users.py      /api/me
│       └── health.py     /health /ready
├── workers/
│   ├── queue.py          RQ queue setup
│   └── tasks/
│       ├── sync_campaigns.py
│       ├── submit_clip.py
│       └── monitor_submissions.py
├── db/
│   ├── engine.py         Async engine + session factory
│   ├── models.py         All SQLAlchemy models
│   └── seed.py           Dev fixtures
├── services/
│   ├── auth.py           JWT encode/decode, password hashing
│   ├── secrets.py        Fernet encrypt/decrypt for user secrets
│   ├── whop_client.py    WhopClient, DryRunWhopClient
│   └── logger.py         structlog JSON logger
├── web/
│   ├── static/app.css
│   └── templates/        Jinja2 templates (dark theme)
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_secrets.py
│   └── test_jobs.py
├── alembic/              Database migrations
├── docker-compose.yml    Dev (postgres + redis + api + worker)
├── docker-compose.prod.yml
├── Dockerfile
├── Makefile
├── .env.example
└── requirements-saas.txt
```

## Stack

- **Backend**: FastAPI (Python 3.12)
- **Database**: PostgreSQL + SQLAlchemy 2.0 (async) + Alembic
- **Task queue**: RQ + Redis
- **Auth**: python-jose + passlib (bcrypt)
- **Encryption**: cryptography (Fernet) for Whop cookie storage
- **Templates**: Jinja2 via FastAPI

## Whop Session Approach

We do NOT automate Whop login (Cloudflare + possible 2FA makes pure headless login unreliable).

Instead:
1. User logs in to Whop in their browser
2. Opens DevTools → Application → Cookies → whop.com
3. Copies all cookies as JSON or cookie string
4. Pastes into Settings → "Connect Whop Account"
5. We validate the cookies by making a test Whop API call
6. We encrypt and store the cookie blob in `user_secrets` table
7. All Whop automation uses these stored cookies

## Quick Start

### 1. Generate keys

```bash
make generate-keys
```

Copy the output values into your `.env` file.

### 2. Set up environment

```bash
cp .env.example .env
# Edit .env and fill in the generated keys
```

### 3. Start services and run migrations

```bash
docker-compose up -d db redis
make migrate
make seed
```

### 4. Run the API

```bash
make dev
```

Open http://localhost:8000

Dev login: `dev@sunoclips.io` / `devpassword123`

### 5. Run the worker (separate terminal)

```bash
make worker
```

### Docker (full stack)

```bash
docker-compose up --build
```

## Verify Commands

```bash
# Phase 0 — Generate keys
make generate-keys && cp .env.example .env

# Phase 1 — Database
docker-compose up -d db redis && make migrate && make seed

# Phase 2 — Auth
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"test1234"}'

# Phase 3 — Settings
curl -X GET http://localhost:8000/api/settings \
  -H "Authorization: Bearer <token>"

# Phase 4 — Worker
make worker  # in second terminal, then submit a test job via API

# Phase 5 — Dashboard
open http://localhost:8000

# Phase 6 — Tests + Health
make test && curl http://localhost:8000/health

# Phase 7 — Production
docker-compose -f docker-compose.prod.yml up --build
```

## Development

```bash
make test        # Run test suite
make migrate     # Apply DB migrations
make seed        # Create dev fixtures
make worker      # Start RQ worker
```

## Environment Variables

See `.env.example` for all variables. Required:
- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection string
- `ENCRYPTION_KEY` — Fernet key (generate with `make generate-keys`)
- `JWT_SECRET_KEY` — JWT signing key
- `JWT_REFRESH_SECRET_KEY` — JWT refresh signing key
- `SESSION_COOKIE_SECRET` — Session cookie signing key
