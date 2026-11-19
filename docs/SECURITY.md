# Security review

Phase 9 review of the AccessHub API against the rules in `CLAUDE.md`. Each endpoint was checked
for **authentication**, **role gate**, **object-level authorisation (IDOR)**, **input
validation / mass assignment** and **SQL injection**.

## Findings and fixes

| # | Finding | Severity | Fix |
|---|---|---|---|
| 1 | `POST /api/auth/login` had no brute-force protection. | High | Per-IP rate limit (Flask-Limiter, `LOGIN_RATE_LIMIT`, default 10/min, also on `/refresh`) **and** a per-account lockout. After 5 failures in 15 minutes the account is locked for the rest of that window. Failures are counted from `LOGIN_FAILED` audit rows, so the lockout holds across every Gunicorn worker and container. Unknown emails lock the same way, so the lockout doesn't reveal which accounts exist. |
| 2 | Approve/reject/reassign returned **403** to a user unrelated to the request, which reveals that an approval id exists (enumeration). | Low | `get_approval_for_user` returns **404** unless the caller can see the request. People who can see it but aren't the assignee still get 403 (`tests/integration/test_approvals_api.py`). |
| 3 | Passwords set by admins only needed 8 characters. | Medium | `services/passwords.py`: 10–128 characters, at least 3 character classes, a common-password blocklist, and no name or email in the password. Applies to user creation and admin resets; every problem is returned in `details.password`. |
| 4 | Production started with *any* non-empty `SECRET_KEY`/`JWT_SECRET_KEY`, including the example placeholders. | Medium | `create_app("production")` refuses secrets shorter than 32 characters or containing `change-me` / `dev-only`. |
| 5 | Behind nginx every audit row would record the proxy's IP. | Medium (audit integrity) | `ProxyFix` with `PROXY_FIX_HOPS=1` in production only. With 0 (the default), `X-Forwarded-For` is ignored, so it can't be spoofed (Phase 8). |

No SQL injection issues were found: see the notes below the table.

## Endpoint review

Legend: **Auth** = valid access token required. **Object check** = what stops one user acting on
another user's data.

| Endpoint | Auth / role | Object check | Notes |
|---|---|---|---|
| `POST /api/auth/login` | public, rate-limited | n/a | Same error for unknown email / wrong password / inactive; dummy hash keeps timing similar; lockout (finding 1). |
| `POST /api/auth/refresh` | refresh token, rate-limited | token `sub` | Roles re-read from the DB; inactive users rejected by the user loader. |
| `POST /api/auth/logout` | access token | refresh token in the body must belong to the caller | Otherwise 422. |
| `GET /api/auth/me` | access token | self | |
| `POST /api/requests` | employee | requester = caller | `access_level_id` must belong to `application_id`; inactive apps → 404. |
| `GET /api/requests` | any | employees forced to their own (`requester_id` ignored) | Auditors/admins may filter by anyone. |
| `GET /api/requests/<id>` | any | requester, current or past approver, auditor, admin; **404** otherwise | |
| `POST /api/requests/<id>/cancel` | any | must be visible (404), then requester only (403) | Row locked `FOR UPDATE`. |
| `GET /api/approvals/inbox` | any | `approver_id = caller` in SQL | |
| `POST /api/approvals/<id>/approve`, `/reject` | any | visible (404, finding 2), then assignee only (403); no self-approval | Row locked; state re-checked after the lock. |
| `POST /api/approvals/<id>/reassign` | admin | n/a | Reason required; new approver active, not the requester. |
| `GET /api/applications`, `/<id>`, `/<id>/workflow`, `/<id>/access-levels` | any | inactive apps hidden (404) unless admin or owner | Approver names/emails in workflows are deliberately visible (chain preview). |
| `POST /api/applications` | admin | n/a | Owner must hold app_owner or admin. |
| `PUT /api/applications/<id>` | admin, app_owner | owner may edit only own app; `owner_id`/`is_active` admin-only | |
| `DELETE /api/applications/<id>` | admin | n/a | Soft delete. |
| `POST/PUT/DELETE …/access-levels[/<level_id>]` | admin, app_owner | own app; level must belong to that app (no cross-app ids) | Used levels can't be deleted (409). |
| `PUT /api/applications/<id>/workflow` | admin, app_owner | own app | Application row locked; full validation. |
| `GET/POST /api/users`, `GET/PUT /api/users/<id>`, `PUT …/roles` | admin | n/a | Manager-cycle check; no self-lockout; last-admin guard; password policy (finding 3). |
| `GET /api/users/lookup` | admin, app_owner | n/a | Returns only id, name, email of active users. |
| `GET /api/audit`, `/export.csv`, `GET /api/reports/summary` | auditor, admin | n/a | Read-only; no update/delete routes exist; DB trigger blocks UPDATE/DELETE; CSV formula-injection safe; exports are themselves audited. |
| `GET /api/health` | public | n/a | Returns no internals. |

### SQL injection

All queries are built with SQLAlchemy expressions and bound parameters. The only raw SQL is
`SELECT 1` in the health check and fixed statements in migrations. User text used in `LIKE`
searches is escaped (`utils/pagination.like_pattern`), so `%` and `_` match literally. Sort
orders are fixed in code, never taken from the request. Audit `actor` filters are validated
against `^(\d+|system)$`.

### Mass assignment

Every input schema sets `unknown = RAISE`, so extra keys are a 422. Roles can only be changed
through `PUT /users/<id>/roles` (admin). Workflow and request status fields can't be written
by clients at all.

## Other controls

- **CORS** is limited to `FRONTEND_URL`. In production nginx serves the SPA and API from one
  origin, so no cross-origin access is needed.
- **Tokens:** 15-minute access and 7-day refresh tokens. Logout revokes both (blocklist). Roles
  are checked against the database on every request, so removing a role or deactivating a user
  takes effect immediately.
- **XSS:** React escapes output and nginx sends a strict CSP (`script-src 'self'`). Tokens sit
  in `localStorage`, which an XSS bug could read, so the CSP is the main defence. Moving the
  refresh token to an HttpOnly cookie is the next step if the threat model requires it.
- **Secrets** come only from the environment. The repository contains example files only
  (checked with `git grep` for keys, tokens and private keys).
- **Audit integrity:** an append-only Postgres trigger, plus a test that every mutating route
  writes an audit row (`tests/integration/test_audit_invariant.py`).

## Known limitations

- The per-IP limiter uses in-memory storage by default, so each Gunicorn worker counts
  separately. Set `RATELIMIT_STORAGE_URI=redis://…` for one shared counter. The per-account
  lockout is already shared, because it lives in the database.
- An attacker could lock a *specific* account for 15 minutes by submitting wrong passwords for
  it. This is the usual lockout trade-off, and it's why the lock is temporary.
