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
| `POST /api/approvals/<id>/reassign` | admin | `{approver_id, reason}`; resets the step's SLA |

### Emails and background jobs

Emails (HTML + plain text, templates in `backend/app/templates/email/`) are sent after each
decision commits: approval needed, approved, rejected, escalated, access expiring (7 days
before) and access expired. Each links into the frontend via `FRONTEND_URL`. In development
they go to MailHog: open http://localhost:8025.

| Job | Schedule | Run it now |
|---|---|---|
| Escalate overdue approvals to the approver's manager (fallback: admin) | every 15 min | `docker compose exec backend flask escalate` |
| Expire ended access, then send expiry reminders | daily, 02:00 UTC | `docker compose exec backend flask expire` |

The scheduler only starts when `RUN_SCHEDULER=1` (never under tests). It is off in the dev
compose file; use the commands above. Jobs are idempotent, so running them twice is harmless.

### Administration and compliance

| Endpoint | Who | Notes |
|---|---|---|
| `GET /api/applications` | any | active apps (admins: `?include_inactive=true`), `q` search |
| `POST /api/applications` | admin | `{name, owner_id, description?, access_levels?: [names]}` |
| `GET/PUT/DELETE /api/applications/<id>` | read: any · edit: admin or that app's owner · delete: admin | DELETE is a soft delete (`is_active=false`) |
| `GET/POST /api/applications/<id>/access-levels`, `PUT/DELETE .../<level_id>` | admin or owner | levels already used by requests can't be deleted |
| `GET/PUT /api/applications/<id>/workflow` | read: any · write: admin or owner | PUT replaces the whole list atomically; in-flight requests keep their snapshot |
| `GET/POST /api/users`, `GET/PUT /api/users/<id>`, `PUT /api/users/<id>/roles` | admin | search `q`, `role`, `is_active`; deactivate with `{"is_active": false}`; manager cycles rejected |
| `GET /api/users/lookup?q=` | admin, app_owner | brief active users for pickers |
| `GET /api/audit` | auditor, admin | filters `actor` (id or `system`), `action`, `entity_type`, `entity_id`, `from`, `to` |
| `GET /api/audit/export.csv` | auditor, admin | streamed CSV, same filters; the export itself is audited |
| `GET /api/reports/summary` | auditor, admin | counts by status/app, avg approval hours, escalations (30 days), overdue approvals |

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

## Frontend

```bash
cd frontend
npm install
npm test          # Vitest + React Testing Library
npm run lint      # ESLint (zero warnings allowed)
npm run dev       # http://localhost:5173 (proxies /api to the backend)
```

- `src/api/client.js` — axios instance; attaches the access token and, on a 401, refreshes
  once (concurrent requests share one refresh) and retries; signs out if that fails.
- `src/features/auth/authSlice.js` + `src/hooks/useAuth.js` — session state; tokens live in
  localStorage; `hasRole(...roles)` is any-of.
- `src/components/ProtectedRoute.jsx` — `<ProtectedRoute roles={[...]}>` guard (UX only; the
  API enforces every permission). Unknown paths show a 404 page, missing roles a 403 page.
- Shared UI in `src/components/`: `DataTable` (sorting, pagination), `StatusBadge`,
  `ConfirmModal`, `ToastProvider`/`useToast`, `EmptyState`, `Spinner`, `Button`.
- The login page has one-click demo logins for the five seeded roles.
- Requests: **New request** (searchable app picker, access level, justification, duration and a
  preview of the approval chain), **My requests** (filters kept in the URL, paginated) and a
  **request detail** page with the step-by-step approval timeline and a cancel button.
- **Approval inbox**: soonest-due first with overdue highlighting, approve/reject dialogs
  (rejecting needs a comment), bulk approve, and optimistic updates that roll back on error.
- **Admin** (`/admin/applications`, `/admin/users`): application details, access levels and a
  workflow builder (add/remove, drag or arrow reorder, approver type, named approver picker,
  SLA hours; saved with one `PUT /workflow`). App owners see and edit only their own apps.
  User table with search/filters and an edit modal (department, manager, active, roles).
- **Audit log** (`/audit`): filter by actor (person or system), action, entity type and dates;
  expand a row to see an old/new field diff; **Export CSV** downloads the same filtered set.
- **Dashboard**: personal tiles for everyone; for admins/auditors, organisation tiles plus
  Recharts charts (requests by status, by application stacked by status), each with a table
  view. Charts and admin screens are code-split, so employees never download them.

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
