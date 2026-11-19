"""N+1 guard: list endpoints must run the same number of SQL queries for 2 rows as for 8.

If a serializer touches a relationship that the query didn't eager-load, the count grows with
the number of rows and these tests fail.
"""

from contextlib import contextmanager

import pytest
from sqlalchemy import event

from app.extensions import db as _db
from app.models import ApproverType, Decision
from app.services.audit import log_action
from tests.factories import AccessRequestFactory, ApprovalFactory, UserFactory
from tests.helpers import auth, make_app


@contextmanager
def count_queries():
    statements: list[str] = []

    def record(_conn, _cursor, statement, *_args):
        statements.append(statement)

    event.listen(_db.engine, "before_cursor_execute", record)
    try:
        yield statements
    finally:
        event.remove(_db.engine, "before_cursor_execute", record)


def queries_for(client, url, user) -> int:
    headers = auth(user)
    _db.session.expire_all()
    with count_queries() as statements:
        resp = client.get(url, headers=headers)
    assert resp.status_code == 200, resp.get_json()
    return len(statements)


def add_requests(org, n):
    for _ in range(n):
        requester = UserFactory(manager=org.manager)
        application = make_app(UserFactory(roles=["app_owner"]))
        req = AccessRequestFactory(
            requester=requester, application=application, access_level=application.access_levels[0]
        )
        ApprovalFactory(request=req, approver=org.manager)


def add_applications(org, n):
    for _ in range(n):
        make_app(
            UserFactory(roles=["app_owner"]),
            steps=[(ApproverType.MANAGER, None, 24), (ApproverType.SPECIFIC_USER, UserFactory(), 8)],
        )


def add_users(org, n):
    for _ in range(n):
        UserFactory(manager=UserFactory(roles=["manager"]), roles=["employee", "auditor"])


def add_audit_rows(org, n):
    for _ in range(n):
        log_action(UserFactory(), "SOMETHING", "thing", 1, new={"x": 1})
    _db.session.commit()


CASES = [
    ("requests list", "/api/requests?per_page=50", "auditor", add_requests),
    ("approval inbox", "/api/approvals/inbox?per_page=50", "manager", add_requests),
    ("applications", "/api/applications?per_page=100", "employee", add_applications),
    ("users", "/api/users?per_page=100", "admin", add_users),
    ("audit log", "/api/audit?per_page=100", "auditor", add_audit_rows),
]


@pytest.mark.parametrize("name, url, role, add_rows", CASES, ids=[c[0] for c in CASES])
def test_list_endpoints_have_no_n_plus_one(client, org, name, url, role, add_rows):
    user = getattr(org, role)
    add_rows(org, 2)
    few = queries_for(client, url, user)
    add_rows(org, 6)
    many = queries_for(client, url, user)
    assert many == few, f"{name}: {few} queries for a few rows but {many} for more (N+1)"


def test_request_detail_query_count_does_not_grow_with_steps(client, org):
    def request_with_steps(n):
        application = make_app(org.owner, steps=[(ApproverType.MANAGER, None, 24)] * n)
        req = AccessRequestFactory(
            requester=org.employee, application=application, access_level=application.access_levels[0]
        )
        for step in range(1, n + 1):
            ApprovalFactory(
                request=req,
                step_order=step,
                approver=UserFactory(),
                escalated_from=UserFactory(),
                decision=Decision.APPROVED if step < n else Decision.PENDING,
            )
        return req.id

    small = queries_for(client, f"/api/requests/{request_with_steps(1)}", org.auditor)
    large = queries_for(client, f"/api/requests/{request_with_steps(3)}", org.auditor)
    assert large == small
