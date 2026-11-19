# Interview questions about this codebase

Ten questions an interviewer is likely to ask, with short answers that point at the code.
Function and file names are given rather than line numbers, so they stay accurate as the code
changes.

---

### 1. Walk me through what happens when an approver clicks "Approve".

`POST /api/approvals/<id>/approve` (`blueprints/approvals.py`) parses the body, then calls
`requests.get_approval_for_user`, which returns 404 if you can't even see the request. Then
`workflow.approve` (`services/workflow.py`) runs inside `transaction()`:

1. `lock_request()` runs `SELECT … FOR UPDATE` on the request row and re-reads the approval.
2. `_locked_pending_approval()` checks that you are the assignee, not the requester, and that
   the approval is still PENDING.
3. It marks the approval APPROVED and writes `APPROVAL_APPROVED` to the audit log.
4. It looks up the next step in the request's **snapshot** (`request_steps`). If there is one,
   it advances `current_step`, calls `_open_approval()` (which runs `resolve_approver` and audits
   `APPROVAL_ASSIGNED`), and queues an "approval needed" email. If not, the request becomes
   APPROVED, `expires_at` is set, and the requester is notified.
5. Commit, **then** `dispatch_notifications()`. The route serializes the updated request.

### 2. How do you stop two approvers (or an approve and a cancel) racing each other?

Every state-changing function locks the **request row** with `SELECT … FOR UPDATE` before it
reads anything. The second transaction waits, then re-reads (`populate_existing` and
`db.session.refresh`), sees that the approval is already decided, and raises
`InvalidStateError` (409). As a database backstop, the partial unique index
`uq_approvals_one_pending_per_request` allows only one open approval per request.
`test_concurrent_decisions_are_serialised_by_row_lock` (`tests/unit/test_workflow.py`) proves
it: one connection holds the lock while `approve()` runs in a thread, which blocks and then
loses cleanly.

### 3. Why does each request store a copy of its workflow?

Approvals are created one step at a time, so step 2 is read when step 1 is approved. If an admin
edited the workflow in between, an in-flight request would silently change its chain. So
`submit_request` copies the steps into `access_requests.workflow_snapshot` (JSONB), and the
engine reads only that snapshot (migration `1dbe57d2dccd`, with a backfill).
`replace_workflow`'s docstring (`services/applications.py`) documents the behaviour, and a test
edits a workflow mid-flight and checks the old request still finishes on its original chain.

### 4. How is authorisation enforced, and why do you load roles from the database rather than trusting the JWT?

There are two layers:
- `@role_required(...)` (`utils/decorators.py`) is the coarse gate.
- Object-level checks live in the services: `ensure_can_manage` (owners can touch only their
  apps), the assignee check in the workflow, and `can_view` (404 for people who can't see a
  request).

The JWT carries role names for the UI. But `jwt_callbacks.load_user` loads the user on every
request, and `role_required` checks those database roles. So removing a role or deactivating
someone takes effect immediately, not when their 15-minute token expires.

Approve/reject deliberately have **no** role gate: a named-approver step can name a plain
employee, so the real rule is "you are the assignee". `tests/integration/test_permissions.py`
runs every role against every protected endpoint.

### 5. How do you know the audit log is complete, and that nobody can tamper with it?

- **Atomic:** `audit.log_action` only adds a row to the current session; the caller commits it
  together with the business change, so the two succeed or fail together. The rollback test in
  `test_workflow.py` checks that a failed approve leaves no audit rows behind.
- **Append-only:** a Postgres trigger in the initial migration rejects UPDATE and DELETE, an ORM
  guard in `models/audit_log.py` fails fast in Python, and there are no update or delete
  endpoints.
- **Complete:** `tests/integration/test_audit_invariant.py` reads every POST/PUT/DELETE route
  from Flask's URL map and fails if one has no test case proving it writes an audit row. It also
  covers the background jobs, which are audited with `actor_id = NULL`.
- **Extras:** exports are themselves audited, CSV cells are protected against formula injection,
  and ProxyFix makes the stored IP the real client's.

### 6. An email server outage happens. What breaks?

Nothing that matters. Notifications are sent only **after** the transaction commits.
`dispatch_notifications` catches every exception, and `notify()` logs a failure and moves on, so
a decision is never rolled back because of email.
`test_send_failure_is_logged_and_does_not_roll_back` simulates SMTP being down. The trade-off is
that email is sent inside the request (adding latency) and a lost email isn't retried. The next
step would be an outbox table processed by a worker, and the call sites wouldn't change.

### 7. How do the background jobs avoid double-processing, especially with several containers?

- **One scheduler:** only one process runs the scheduler: the `scheduler` container with
  `RUN_SCHEDULER=1` (`flask run-scheduler`). Web containers keep it off, and it never starts
  under tests.
- **Idempotent jobs anyway** (`services/escalation.py`):
  - They select candidate ids, then handle each in its own transaction after `lock_request()`.
  - They **re-check the condition under the lock**, so a decision made in between wins.
  - "Already done" is stored in the row: `escalated`, status EXPIRED, `expiry_reminder_sent_at`.
    A second run therefore finds nothing.
- **Failure isolation:** one failing item is logged without stopping the rest.
- **Tests:** they inject `now=` or use freezegun, for example a 30-day grant gets its reminder on
  day 24 and expires on day 31.

### 8. How does the frontend handle an expired access token?

`src/api/client.js` has a response interceptor. On a 401 (except from `/auth/login`,
`/auth/refresh` and `/auth/logout`) it refreshes **once** and retries. Concurrent 401s share one
in-flight `refreshPromise`, so a burst of requests causes exactly one refresh call
(`client.test.js` checks this). If the refresh fails, or the retry is still 401, it clears the
tokens and dispatches `sessionExpired`.

`authSlice` records *why* a session ended (`endedBy`). After a deliberate sign-out,
`ProtectedRoute` doesn't remember the page, so the next person to sign in isn't sent to the
previous user's page. That was a real bug found while testing in the browser.

### 9. How do your tests hit a real Postgres without being slow or dangerous?

`tests/conftest.py`:
- builds the schema by running the **real migrations**, and `test_migrations.py` fails if the
  models and migrations drift apart;
- refuses any database whose name doesn't end in `_test`;
- cleans up with `DELETE` in dependency order rather than a rolled-back transaction, because the
  engine really commits and locks. `TRUNCATE` is used only for `audit_logs`, whose trigger blocks
  DELETE. DELETE was about 10× faster than TRUNCATE on Docker Desktop.

Tests also hash passwords with fast PBKDF2 (`PASSWORD_HASH_METHOD`) instead of scrypt, which
took about 2 seconds per hash on that VM.

### 10. How did you make sure list pages don't have N+1 query problems?

Each read query declares the relationships its serializer uses: for example
`_request_summary_options()` (`joinedload` for requester, application and level),
`selectinload(AccessRequest.approvals)` for the timeline, and `applications._options()`.
`User.roles` is `lazy="selectin"`.

`tests/integration/test_query_counts.py` counts SQL statements with a SQLAlchemy event listener.
It calls each list endpoint with 2 rows and then with 8, and fails if the count grows. The
indexes match the hot queries: `approvals(approver_id, decision)` for the inbox, and a partial
index `approvals(due_at) WHERE decision='PENDING'` for the escalation scan.
