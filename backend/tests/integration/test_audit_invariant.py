"""Invariant: every state change writes an audit row.

* Every POST/PUT/DELETE route in the app must have a case here (or be EXEMPT with a reason).
  The list of routes is read from Flask itself, so adding an endpoint without a case fails.
* Each case performs a successful call that must add at least one audit_logs row.
* The background jobs (escalation, expiry, reminders) are covered the same way, as "system".
"""

from collections.abc import Callable
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.extensions import db as _db
from app.models import AuditLog, RequestStatus
from app.models.mixins import utcnow
from app.services import escalation
from tests.factories import TEST_PASSWORD, AccessRequestFactory, ApprovalFactory, UserFactory
from tests.helpers import auth, make_app

JUSTIFICATION = "Needed for the quarterly security review work."

# (method, rule) -> setup(client, org) returning a zero-argument callable that makes the call.
CASES: dict[tuple[str, str], Callable] = {}

# Mutating routes that change no stored business state, with the reason.
EXEMPT = {
    ("POST", "/api/auth/refresh"): "only issues a new access token; nothing is stored",
}


def case(method: str, rule: str):
    def register(setup: Callable) -> Callable:
        CASES[(method, rule)] = setup
        return setup

    return register


def _submit(client, org) -> dict:
    application = make_app(org.owner)
    body = {
        "application_id": application.id,
        "access_level_id": application.access_levels[0].id,
        "justification": JUSTIFICATION,
    }
    return client.post("/api/requests", json=body, headers=auth(org.employee)).get_json()


# --- auth -----------------------------------------------------------------------------------


@case("POST", "/api/auth/login")
def _login(client, org):
    return lambda: client.post(
        "/api/auth/login", json={"email": org.employee.email, "password": TEST_PASSWORD}
    )


@case("POST", "/api/auth/logout")
def _logout(client, org):
    return lambda: client.post("/api/auth/logout", headers=auth(org.employee))


# --- requests and approvals -------------------------------------------------------------


@case("POST", "/api/requests")
def _create_request(client, org):
    application = make_app(org.owner)
    body = {
        "application_id": application.id,
        "access_level_id": application.access_levels[0].id,
        "justification": JUSTIFICATION,
    }
    return lambda: client.post("/api/requests", json=body, headers=auth(org.employee))


@case("POST", "/api/requests/<int:request_id>/cancel")
def _cancel(client, org):
    request_id = _submit(client, org)["id"]
    return lambda: client.post(f"/api/requests/{request_id}/cancel", headers=auth(org.employee))


@case("POST", "/api/approvals/<int:approval_id>/approve")
def _approve(client, org):
    approval_id = _submit(client, org)["approvals"][0]["id"]
    return lambda: client.post(f"/api/approvals/{approval_id}/approve", headers=auth(org.manager))


@case("POST", "/api/approvals/<int:approval_id>/reject")
def _reject(client, org):
    approval_id = _submit(client, org)["approvals"][0]["id"]
    return lambda: client.post(
        f"/api/approvals/{approval_id}/reject", json={"comment": "No"}, headers=auth(org.manager)
    )


@case("POST", "/api/approvals/<int:approval_id>/reassign")
def _reassign(client, org):
    approval_id = _submit(client, org)["approvals"][0]["id"]
    body = {"approver_id": org.colleague.id, "reason": "On leave"}
    return lambda: client.post(f"/api/approvals/{approval_id}/reassign", json=body, headers=auth(org.admin))


# --- applications -----------------------------------------------------------------------


@case("POST", "/api/applications")
def _create_app(client, org):
    body = {"name": "Audited App", "owner_id": org.owner.id}
    return lambda: client.post("/api/applications", json=body, headers=auth(org.admin))


@case("PUT", "/api/applications/<int:app_id>")
def _update_app(client, org):
    application = make_app(org.owner)
    return lambda: client.put(
        f"/api/applications/{application.id}", json={"description": "changed"}, headers=auth(org.owner)
    )


@case("DELETE", "/api/applications/<int:app_id>")
def _deactivate_app(client, org):
    application = make_app(org.owner)
    return lambda: client.delete(f"/api/applications/{application.id}", headers=auth(org.admin))


@case("POST", "/api/applications/<int:app_id>/access-levels")
def _add_level(client, org):
    application = make_app(org.owner)
    return lambda: client.post(
        f"/api/applications/{application.id}/access-levels", json={"name": "Auditor"}, headers=auth(org.owner)
    )


@case("PUT", "/api/applications/<int:app_id>/access-levels/<int:level_id>")
def _rename_level(client, org):
    application = make_app(org.owner)
    url = f"/api/applications/{application.id}/access-levels/{application.access_levels[0].id}"
    return lambda: client.put(url, json={"name": "Renamed"}, headers=auth(org.owner))


@case("DELETE", "/api/applications/<int:app_id>/access-levels/<int:level_id>")
def _delete_level(client, org):
    application = make_app(org.owner)
    url = f"/api/applications/{application.id}/access-levels/{application.access_levels[0].id}"
    return lambda: client.delete(url, headers=auth(org.owner))


@case("PUT", "/api/applications/<int:app_id>/workflow")
def _replace_workflow(client, org):
    application = make_app(org.owner)
    body = {"steps": [{"step_order": 1, "approver_type": "APP_OWNER", "sla_hours": 12}]}
    return lambda: client.put(
        f"/api/applications/{application.id}/workflow", json=body, headers=auth(org.owner)
    )


# --- users ------------------------------------------------------------------------------


@case("POST", "/api/users")
def _create_user(client, org):
    body = {"name": "Audit Person", "email": "audit.person@example.com", "password": "Correct-Horse-42"}
    return lambda: client.post("/api/users", json=body, headers=auth(org.admin))


@case("PUT", "/api/users/<int:user_id>")
def _update_user(client, org):
    return lambda: client.put(
        f"/api/users/{org.colleague.id}", json={"department": "Ops"}, headers=auth(org.admin)
    )


@case("PUT", "/api/users/<int:user_id>/roles")
def _set_roles(client, org):
    body = {"roles": ["employee", "manager"]}
    return lambda: client.put(f"/api/users/{org.colleague.id}/roles", json=body, headers=auth(org.admin))


# --- tests ------------------------------------------------------------------------------


def audit_count() -> int:
    _db.session.expire_all()
    return _db.session.scalar(select(func.count(AuditLog.id)))


def test_every_mutating_route_is_covered(app):
    mutating = {
        (method, rule.rule)
        for rule in app.url_map.iter_rules()
        for method in rule.methods & {"POST", "PUT", "PATCH", "DELETE"}
    }
    missing = mutating - set(CASES) - set(EXEMPT)
    stale = (set(CASES) | set(EXEMPT)) - mutating
    assert not missing, f"Add an audit case for: {sorted(missing)}"
    assert not stale, f"Cases for routes that no longer exist: {sorted(stale)}"


@pytest.mark.parametrize("route", sorted(CASES), ids=lambda r: f"{r[0]} {r[1]}")
def test_state_change_writes_audit_row(client, org, route):
    act = CASES[route](client, org)
    before = audit_count()
    resp = act()
    assert 200 <= resp.status_code < 300, (route, resp.status_code, resp.get_json())
    assert audit_count() > before, f"{route} changed state without an audit row"


def _overdue_approval(org):
    application = make_app(org.owner)
    req = AccessRequestFactory(
        requester=org.employee, application=application, access_level=application.access_levels[0]
    )
    ApprovalFactory(request=req, approver=org.manager, due_at=utcnow() - timedelta(hours=1))


def _approved_request(org, expires_in):
    application = make_app(org.owner)
    AccessRequestFactory(
        requester=org.employee,
        application=application,
        access_level=application.access_levels[0],
        status=RequestStatus.APPROVED,
        duration_days=30,
        expires_at=utcnow() + expires_in,
    )


JOBS = {
    "escalate_overdue": (_overdue_approval, escalation.escalate_overdue),
    "expire_access": (lambda org: _approved_request(org, timedelta(hours=-1)), escalation.expire_access),
    "send_expiry_reminders": (
        lambda org: _approved_request(org, timedelta(days=3)),
        escalation.send_expiry_reminders,
    ),
}


@pytest.mark.parametrize("job", sorted(JOBS))
def test_background_job_changes_are_audited_as_system(org, job):
    prepare, run = JOBS[job]
    prepare(org)
    before = audit_count()
    assert run() == 1
    added = audit_count() - before
    assert added >= 1
    rows = _db.session.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(added)).all()
    assert all(row.actor_id is None for row in rows)


def test_fixture_builders_write_no_audit_rows(org):
    """Sanity check: the counts above measure the call, not the test setup."""
    before = audit_count()
    UserFactory()
    make_app(org.owner)
    assert audit_count() == before
