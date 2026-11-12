# AccessHub – Build Plan & Claude Code Prompts

## How to use
1. Create an empty folder `accesshub/`, `git init`, and put `CLAUDE.md` in the root.
2. Open Claude Code in that folder. Run **one phase at a time**, in order.
3. After each phase: run the tests/app yourself, read the code, then commit
   (`git commit -m "phase N: ..."`). Don't move on until the phase's checklist passes.
4. Start each phase with **plan mode** (Shift+Tab) so Claude shows its plan before writing code.
5. If something breaks, paste the exact error and say "fix this, don't change unrelated code".

| Phase | Goal | Time |
|---|---|---|
| 0 | Scaffold + Docker + health check | 0.5 day |
| 1 | Models, migrations, seed, JWT auth, RBAC | 2–3 days |
| 2 | Workflow engine + requests/approvals APIs + audit | 3–4 days |
| 3 | Applications, users, audit APIs | 2 days |
| 4 | Emails + escalation + expiry | 2 days |
| 5 | React foundation: auth, layout, routing | 2 days |
| 6 | React: requests + approval inbox | 3 days |
| 7 | React: admin + audit reports + dashboard | 3 days |
| 8 | Production Docker, Nginx, Gunicorn, CI/CD | 2 days |
| 9 | Hardening, README, demo polish | 2 days |

---

## Phase 0 — Scaffold

```
Read CLAUDE.md carefully; it is the source of truth for this project.

Phase 0: scaffold the repository exactly as described in "Repository layout".
- backend: Flask app factory with config classes (Development, Testing, Production) loaded from env vars,
  extensions.py, an empty blueprint registered at /api with GET /api/health returning {"status":"ok","db":"ok"}
  (actually ping the DB), requirements.txt with pinned versions, a .env.example.
- frontend: Vite + React 18 + Tailwind + React Router + Redux Toolkit + Axios, a placeholder home page that
  calls /api/health and shows the result. Configure the Vite dev proxy for /api -> http://localhost:5000.
- docker-compose.yml for local dev: postgres:16 (named volume + healthcheck), backend (flask run with reload,
  depends_on postgres healthy), frontend (vite dev), mailhog.
- A root .gitignore and a short README with how to run.
- backend/tests with conftest.py providing app, client and db fixtures against a separate Postgres test database,
  plus one test for /api/health.

Do not build any features yet. When done, list the commands to verify everything works.
```

**Check:** `docker compose up` works, http://localhost:5173 shows "ok", `pytest` passes.

---

## Phase 1 — Data model, auth, RBAC

```
Phase 1 per CLAUDE.md.
1. Create all SQLAlchemy models from the "Data model" section (SQLAlchemy 2.x Mapped[] style), with enums,
   constraints, indexes, relationships and created_at/updated_at timestamps. Generate the initial
   Flask-Migrate migration and review it for correctness.
2. Create services/audit.py with log_action(actor, action, entity_type, entity_id, old=None, new=None)
   that captures IP and user agent from the request context when present (works outside requests too).
3. Auth blueprint: login, refresh, logout (token blocklist table or in-DB revocation), /me.
   Put user id and role names in JWT claims. Uniform error JSON as defined in CLAUDE.md, including
   handlers for JWT errors, 404, 405, 422 validation errors and 500.
4. utils/decorators.py: @role_required(*roles) and a current_user helper.
5. `flask seed` CLI command creating the demo data from CLAUDE.md (idempotent — safe to run twice).
6. Tests: model constraints, login success/failure, refresh, role_required allow/deny, seed idempotency.
Audit LOGIN_SUCCESS and LOGIN_FAILED events.
```

**Check:** login via curl/Postman returns tokens; tests green.

---

## Phase 2 — Workflow engine (the most important phase)

```
Phase 2 per CLAUDE.md: implement services/workflow.py exactly following "Workflow engine rules",
then the requests and approvals blueprints.

Requirements:
- Pure service functions that raise domain exceptions (e.g. DuplicateRequestError, NotAuthorizedError,
  InvalidStateError) mapped to HTTP errors in one place.
- Row-level locking with SELECT ... FOR UPDATE when approving/rejecting/cancelling.
- No self-approval; resolve_approver fallbacks as specified.
- Every transition writes an audit log in the same transaction.
- Marshmallow schemas for input validation and output (request detail includes an ordered approval timeline
  with approver names, decisions, comments and timestamps).
- GET /api/requests: employees see their own; auditors/admins can see all with filters
  (status, application_id, requester_id, date range), paginated.
- GET /api/approvals/inbox: the current user's PENDING approvals, oldest due first, with an is_overdue flag.
- Leave a notifications.notify(event, request, recipients) stub that just logs for now (wired in Phase 4).

Tests (be thorough, this is the core):
unit — 1-step and 3-step workflows end to end; reject mid-chain stops it; cancel skips pending approvals;
duplicate pending request rejected; self-approval fallback; MANAGER fallback to admin when there is no manager;
a non-assigned user cannot approve; approving an already-decided approval fails; audit rows created for each step.
integration — the same flows through the HTTP API with real JWTs.
Run pytest and fix failures before finishing. Report the coverage.
```

**Check:** you can explain the engine line by line — interviewers will ask.

---

## Phase 3 — Applications, users, audit APIs

```
Phase 3 per CLAUDE.md.
- Applications blueprint: CRUD (soft delete via is_active), nested access levels,
  GET/PUT /applications/<id>/workflow which replaces the full ordered step list atomically and validates it
  (contiguous step_order starting at 1, SPECIFIC_USER requires approver_user_id, sla_hours 1–168).
  Admins can edit any app; app_owners only their own. Changing a workflow must not affect in-flight requests
  (they already have their approvals; document this behaviour in a docstring).
- Users blueprint (admin only): list with search + pagination, create, update (incl. manager_id, preventing
  manager cycles), deactivate, PUT /users/<id>/roles.
- Audit blueprint (auditor + admin): filtered, paginated GET /api/audit and a streaming CSV export
  /api/audit/export.csv; GET /api/reports/summary returning counts by status, by application, average approval
  time in hours, and the number of escalations in the last 30 days.
- POST /api/approvals/<id>/reassign (admin) with a required reason, audited.
- Tests for permissions (each role allowed/denied), workflow validation, manager-cycle prevention, CSV output.
```

---

## Phase 4 — Email notifications, escalation, expiry

```
Phase 4 per CLAUDE.md.
- services/notifications.py with Flask-Mail and Jinja2 HTML + plain-text templates for: approval_needed,
  request_approved, request_rejected, approval_escalated, access_expiring, access_expired.
  Approval emails include a deep link to the frontend (FRONTEND_URL env var). Sending errors must be logged
  and must NOT roll back the business transaction; send after commit.
- services/escalation.py implementing "Escalation & expiry" from CLAUDE.md, plus `flask escalate` and
  `flask expire` CLI commands.
- Register APScheduler jobs in create_app only when RUN_SCHEDULER=1 and not in Testing.
- Point dev mail at MailHog.
- Tests: use mail.record_messages() to assert recipients/subjects; use freezegun (or time injection) to test
  escalation picks only overdue, unescalated approvals, falls back to admin, and is idempotent; test expiry.
```

**Check:** submit a request and see the email in MailHog (http://localhost:8025).

---

## Phase 5 — React foundation

```
Phase 5 per CLAUDE.md (frontend).
- src/api/client.js: axios instance with baseURL /api, request interceptor attaching the access token,
  response interceptor that on 401 refreshes once (queueing concurrent requests) and otherwise logs out.
- authSlice (login, logout, fetchMe; tokens persisted in localStorage), useAuth() hook exposing user,
  roles and hasRole().
- Layout with a sidebar whose items depend on roles, a top bar showing the user and an inbox count badge.
- routes.jsx with React Router v6 and <ProtectedRoute roles={[...]}> ; a 403 page and a 404 page.
- Login page with validation, error display and five "Demo login as <role>" buttons using the seed accounts.
- Shared components: DataTable (sorting, pagination), StatusBadge, ConfirmModal, Toast notifications,
  EmptyState, Spinner.
- Clean, professional Tailwind design (enterprise-dashboard style), responsive.
- Vitest + RTL tests for authSlice, ProtectedRoute and the Login page.
```

---

## Phase 6 — Requests & approval inbox

```
Phase 6 per CLAUDE.md (frontend).
- requestsSlice and approvalsSlice using createAsyncThunk.
- "New Request" page: searchable application picker -> access level select -> justification (min 20 chars) ->
  optional duration -> shows the approval chain preview for the chosen app before submitting.
- "My Requests" page: filterable, paginated table; clicking a row opens a detail page with a vertical
  timeline of approval steps (pending/approved/rejected/escalated, approver, comment, time); a cancel button
  while PENDING.
- "Approval Inbox": list of pending approvals with requester, app, level, justification, due time and an
  overdue highlight; approve/reject modal (comment required for reject); optimistic removal from the list;
  bulk-select approve.
- Show API validation errors inline. Tests for the inbox approve/reject flow with mocked API.
```

---

## Phase 7 — Admin, audit reports, dashboard

```
Phase 7 per CLAUDE.md (frontend).
- Applications admin: list/create/edit apps and access levels; a workflow builder to add, remove and
  drag-or-arrow reorder steps, choose approver type, pick a specific user and set SLA hours; saves via
  PUT /workflow.
- User management: searchable table, edit modal (department, manager, active), role checkboxes.
- Audit reports (auditor/admin): filters (actor, action, entity type, date range), paginated table with an
  expandable row showing an old/new JSON diff, an "Export CSV" button.
- Dashboard: role-aware cards (my pending requests, my inbox count, overdue approvals) and, for
  admin/auditor, charts from /api/reports/summary (Recharts): requests by status, by application, and
  average approval time.
```

---

## Phase 8 — Production deployment & CI/CD

```
Phase 8 per CLAUDE.md.
- backend/Dockerfile: multi-stage, non-root user, runs `gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app`,
  an entrypoint that runs `flask db upgrade` before starting.
- frontend/Dockerfile: multi-stage node build -> nginx:alpine; nginx.conf serving the SPA with
  try_files fallback, proxying /api to backend:8000, gzip, sensible security headers and caching for assets.
- docker-compose.prod.yml: postgres, backend (RUN_SCHEDULER=0, scaled-ready), a separate "scheduler"
  service from the same image with RUN_SCHEDULER=1, frontend/nginx on port 80. Env from a .env file.
- .github/workflows/ci.yml: on push/PR — backend job (Postgres service container, ruff lint, pytest with
  coverage, fail under 85%), frontend job (npm ci, lint, vitest, build), and on main: build and push both
  images to GHCR tagged with the commit SHA and latest. Add an optional deploy job (SSH to a server and
  `docker compose pull && up -d`) that is skipped unless the deploy secrets exist.
- Document deployment steps in the README.
```

---

## Phase 9 — Hardening & polish

```
Phase 9: review the whole codebase against CLAUDE.md and fix gaps.
- Security pass: rate-limit login (Flask-Limiter), CORS restricted to FRONTEND_URL, password policy,
  no secrets in the repo, SQL injection/IDOR review of every endpoint (list any you find and fix them).
- Performance: check for N+1 queries in list endpoints (use selectinload/joinedload).
- Ensure every state change produces an audit row — write a test that asserts this across all services.
- README: project overview, architecture diagram (Mermaid), ER diagram (Mermaid), feature list with
  screenshots placeholders, tech stack, local setup, running tests, deployment, demo credentials.
- Give me a list of 10 likely interview questions about this codebase with short answers referencing the code.
```

---

## Tips
- If Claude drifts from the spec, say: "Re-read CLAUDE.md and align with it."
- Ask "explain this file to me like I'm preparing for an interview" after each phase — you need to own this code.
- Keep commits per phase; a clean git history looks great on GitHub.
