# AccessHub

Self-service portal for requesting access to business applications, with configurable
multi-level approval workflows and a full audit trail. See [CLAUDE.md](CLAUDE.md) for the spec.

**Stack:** React 18 + Vite + Redux Toolkit + Tailwind · Flask 3 + SQLAlchemy 2 · PostgreSQL 16 · Docker

## Run it (Docker)

```bash
docker compose up --build
```

| Service  | URL                                  |
|----------|--------------------------------------|
| Frontend | http://localhost:5173                |
| API      | http://localhost:5000/api/health     |
| MailHog  | http://localhost:8025                |

The home page calls `/api/health` (through the Vite proxy) and should show **API ok / Database ok**.

### Database and demo data

```bash
docker compose exec backend flask db upgrade   # apply migrations
docker compose exec backend flask seed         # demo data (safe to run repeatedly)
```

Demo accounts (password `Password@123`):

| Email                    | Roles                 |
|--------------------------|-----------------------|
| admin@accesshub.dev      | admin, employee       |
| auditor@accesshub.dev    | auditor, employee     |
| manager@accesshub.dev    | manager, employee     |
| owner@accesshub.dev      | app_owner, employee   |
| employee@accesshub.dev   | employee              |

…plus 10 more employees (e.g. `priya.sharma@accesshub.dev`), 5 applications with workflows,
and 40 historical requests in mixed states.

### Try the auth API

```bash
curl -s -X POST localhost:5000/api/auth/login -H "Content-Type: application/json" \
  -d '{"email":"manager@accesshub.dev","password":"Password@123"}'
curl -s localhost:5000/api/auth/me -H "Authorization: Bearer <access_token>"
```

Endpoints: `POST /api/auth/login`, `POST /api/auth/refresh` (refresh token),
`POST /api/auth/logout` (access token; optional `{"refresh_token": "..."}` to revoke it too),
`GET /api/auth/me`.

### Requests and approvals

| Endpoint | Who | Notes |
|---|---|---|
| `POST /api/requests` | employee | `{application_id, access_level_id, justification (≥20 chars), duration_days?}` → 201 |
| `GET /api/requests` | any | own requests; auditors/admins see all. Filters: `status`, `application_id`, `requester_id`, `from`, `to`, `mine`, `page`, `per_page` |
| `GET /api/requests/<id>` | requester, its approvers, auditor, admin | includes `steps` and the `approvals` timeline; 404 for anyone else |
| `POST /api/requests/<id>/cancel` | requester | only while PENDING; open approval becomes SKIPPED |
| `GET /api/approvals/inbox` | any | my PENDING approvals, soonest due first, with `is_overdue` |
| `POST /api/approvals/<id>/approve` | assigned approver | optional `{comment}` |
| `POST /api/approvals/<id>/reject` | assigned approver | `{comment}` required |

The workflow engine lives in `backend/app/services/workflow.py`; its module docstring explains
the rules (step snapshot, row locking, audit-in-same-transaction, notify-after-commit).

## Tests

Backend tests use a real Postgres database (`accesshub_test`, created automatically the first
time the Postgres volume initialises). The schema is built by running the Alembic migrations,
and a test fails if the migrations and models ever drift apart:

```bash
docker compose exec backend pytest --cov=app
```

> If you created the Postgres volume before `docker/postgres/init` existed, recreate it with
> `docker compose down -v` (this deletes local data).

## Run the backend without Docker (optional)

Requires Python 3.12 and a reachable Postgres:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
flask run --debug
```

## Project layout

```
backend/    Flask API (app factory, blueprints, services, tests)
frontend/   React SPA (Vite, feature folders)
docker/     Container support files (Postgres init scripts)
```
