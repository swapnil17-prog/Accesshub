# AccessHub – Access Request & Approval Portal

Self-service portal that replaces email-based access requests. Employees request access to business
applications, managers and application owners approve through configurable multi-level workflows,
and auditors review the full access history for compliance.

## Tech stack (do not substitute)
- **Frontend:** React 18 + Vite, React Router v6, Redux Toolkit (+ RTK slices / createAsyncThunk), Axios, hooks only (no class components). Styling: Tailwind CSS.
- **Backend:** Python 3.12, Flask 3 (app factory + Blueprints), Flask-SQLAlchemy 3 (SQLAlchemy 2.x style), Flask-Migrate, Flask-JWT-Extended, Flask-Mail, Flask-CORS, marshmallow for validation/serialization, APScheduler for background jobs.
- **Database:** PostgreSQL 16.
- **Testing:** pytest, pytest-cov, factory-boy; frontend: Vitest + React Testing Library.
- **Deployment:** Docker, docker-compose, Gunicorn, Nginx, GitHub Actions. MailHog for local email.

## Repository layout
```
accesshub/
├── CLAUDE.md
├── docker-compose.yml
├── .github/workflows/ci.yml
├── backend/
│   ├── app/
│   │   ├── __init__.py            # create_app(config_name)
│   │   ├── config.py              # Dev / Test / Prod configs from env vars
│   │   ├── extensions.py          # db, migrate, jwt, mail, scheduler
│   │   ├── models/                # one module per model
│   │   ├── schemas/               # marshmallow schemas
│   │   ├── blueprints/            # auth, requests, approvals, applications, users, audit
│   │   ├── services/              # workflow.py, notifications.py, escalation.py, audit.py
│   │   ├── utils/decorators.py    # @role_required(...)
│   │   └── cli.py                 # flask seed, flask escalate
│   ├── migrations/
│   ├── tests/{unit,integration}/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── wsgi.py
└── frontend/
    ├── src/
    │   ├── api/                   # axios instance + per-resource modules
    │   ├── app/store.js
    │   ├── features/{auth,requests,approvals,applications,users,audit}/  # slice + pages + components
    │   ├── components/            # shared UI (Table, StatusBadge, Modal, ProtectedRoute, Layout)
    │   ├── hooks/                 # useAuth, useDebounce, ...
    │   └── routes.jsx
    ├── Dockerfile                 # multi-stage: build -> nginx
    └── nginx.conf
```

## Roles (RBAC)
| Role | Permissions |
|---|---|
| employee | create/view/cancel own requests |
| manager | approve/reject steps assigned to them (normally their direct reports' requests) |
| app_owner | approve steps for apps they own; configure workflow for their apps |
| admin | manage users, roles, applications, workflows; reassign any pending approval |
| auditor | read-only access to all requests and audit logs; CSV export |

A user may hold multiple roles. Roles are included in JWT claims. Enforce with `@role_required(...)`
**plus** object-level checks (an approver can only act on approvals where `approver_id == current_user`).

## Data model
- `users(id, name, email UNIQUE, password_hash, department, manager_id FK users NULL, is_active, created_at)`
- `roles(id, name UNIQUE)` ; `user_roles(user_id, role_id)` PK(user_id, role_id)
- `applications(id, name UNIQUE, description, owner_id FK users, is_active, created_at)`
- `app_access_levels(id, application_id FK, name)` UNIQUE(application_id, name)
- `workflow_steps(id, application_id FK, step_order, approver_type ENUM[MANAGER, APP_OWNER, SPECIFIC_USER], approver_user_id FK users NULL, sla_hours INT default 24)` UNIQUE(application_id, step_order)
- `access_requests(id, requester_id FK, application_id FK, access_level_id FK, justification TEXT, status ENUM[PENDING, APPROVED, REJECTED, CANCELLED, EXPIRED], current_step INT, duration_days INT NULL, expires_at NULL, created_at, updated_at)`
- `approvals(id, request_id FK, step_order, approver_id FK, decision ENUM[PENDING, APPROVED, REJECTED, SKIPPED] default PENDING, comment, due_at, decided_at NULL, escalated BOOL default false, escalated_from_id FK users NULL)`
- `audit_logs(id, actor_id FK NULL (NULL = system), action VARCHAR, entity_type, entity_id, old_value JSONB, new_value JSONB, ip_address, user_agent, created_at)` — **append-only**: no update/delete endpoints, ever.

Index: `approvals(approver_id, decision)`, `approvals(due_at) WHERE decision='PENDING'`, `audit_logs(entity_type, entity_id)`, `audit_logs(created_at)`.

## Workflow engine rules (`services/workflow.py`)
- `submit_request(user, app_id, level_id, justification, duration_days)`: reject if the user already has a PENDING request for the same app+level. Create request at step 1, create the step-1 approval, notify approver, audit `REQUEST_CREATED`.
- `resolve_approver(step, request)`: MANAGER → requester.manager (fallback: any admin); APP_OWNER → application.owner; SPECIFIC_USER → step.approver_user_id. If the resolved approver is the requester, fall back to their manager, then admin (no self-approval).
- `approve(approval, user, comment)`: mark APPROVED; if more steps → advance `current_step`, create the next approval, notify; else request APPROVED, set `expires_at` if duration_days, notify requester. Audit every transition.
- `reject(approval, user, comment)`: comment required; request REJECTED; remaining steps not created; notify requester.
- `cancel(request, user)`: only requester, only while PENDING; pending approvals → SKIPPED.
- All state changes run in a single DB transaction; use `SELECT ... FOR UPDATE` on the request row to prevent double-approval races.

## Escalation & expiry (`services/escalation.py`)
- APScheduler job every 15 min (also exposed as `flask escalate`): for approvals with `decision=PENDING AND due_at < now() AND escalated=false`, reassign to the approver's manager (fallback admin), set `escalated=true`, `escalated_from_id`, new `due_at`, email both, audit `APPROVAL_ESCALATED` with actor NULL.
- Daily job: requests APPROVED with `expires_at < now()` → EXPIRED; email requester 7 days before expiry.
- Scheduler must not start under the test config, and in production only one worker should run it (env flag `RUN_SCHEDULER=1` on a single container).

## API conventions
- Prefix `/api`. JSON only. Errors: `{"error": {"code": "...", "message": "...", "details": {...}}}` with proper HTTP status.
- Pagination: `?page=&per_page=` → `{"items": [], "page", "per_page", "total"}`.
- Auth: access token 15 min, refresh token 7 days; `/api/auth/login`, `/refresh`, `/logout`, `/me`.
- Endpoints:
  - `POST/GET /api/requests`, `GET /api/requests/<id>` (with approval timeline), `POST /api/requests/<id>/cancel`
  - `GET /api/approvals/inbox`, `POST /api/approvals/<id>/approve`, `POST /api/approvals/<id>/reject`, `POST /api/approvals/<id>/reassign` (admin)
  - `GET/POST/PUT/DELETE(soft) /api/applications`, `GET/PUT /api/applications/<id>/workflow`, access levels nested
  - `GET/POST/PUT /api/users`, `PUT /api/users/<id>/roles`
  - `GET /api/audit?actor=&entity_type=&action=&from=&to=`, `GET /api/audit/export.csv`, `GET /api/reports/summary`
  - `GET /api/health`

## Coding standards
- Business logic lives in `services/`, never in route functions. Routes: parse → call service → serialize.
- Every state-changing service function writes an audit log via `audit.log_action(...)` in the same transaction.
- Never return `password_hash`. Hash with werkzeug `generate_password_hash`.
- Secrets only from env vars; provide `.env.example`.
- Type hints on Python functions; docstrings on services.
- Write tests alongside each feature. Target ≥ 85% backend coverage. Tests use a real Postgres (docker) test database, not SQLite.
- Frontend: feature-folder structure, RTK slices for server state, a `ProtectedRoute` that accepts `roles`, an axios interceptor that attaches the token and transparently refreshes on 401.

## Commands
- `docker compose up --build` — full stack (frontend http://localhost, MailHog http://localhost:8025)
- `cd backend && flask db upgrade && flask seed` — migrate + demo data
- `cd backend && pytest --cov=app` — backend tests
- `cd frontend && npm run dev` / `npm test`

## Demo seed data
Users (password `Password@123`): admin@accesshub.dev, auditor@accesshub.dev, manager@accesshub.dev,
owner@accesshub.dev, employee@accesshub.dev (+ 10 more employees). Apps: Jira, Salesforce, GitHub,
AWS Console, Workday — each with 2–3 access levels and 1–3 workflow steps. ~40 historical requests in mixed states.
