"""POST /api/approvals/<id>/reassign (admin only, reason required, audited)."""

from datetime import timedelta

import pytest

from app.extensions import db as _db
from app.models import Approval
from app.models.mixins import utcnow
from tests.helpers import auth, make_app

JUSTIFICATION = "Needed for the data migration project."


@pytest.fixture()
def approval(client, org):
    application = make_app(org.owner)
    body = {
        "application_id": application.id,
        "access_level_id": application.access_levels[0].id,
        "justification": JUSTIFICATION,
    }
    created = client.post("/api/requests", json=body, headers=auth(org.employee)).get_json()
    row = _db.session.get(Approval, created["approvals"][0]["id"])
    row.due_at = utcnow() - timedelta(hours=5)  # overdue
    _db.session.commit()
    return row


def reassign(client, admin, approval, approver, reason="Manager is on leave"):
    return client.post(
        f"/api/approvals/{approval.id}/reassign",
        json={"approver_id": approver.id, "reason": reason},
        headers=auth(admin),
    )


def test_reassign_moves_approval_and_resets_sla(client, org, approval):
    resp = reassign(client, org.admin, approval, org.colleague)
    assert resp.status_code == 200, resp.get_json()
    timeline = resp.get_json()["approvals"]
    assert timeline[0]["approver"]["id"] == org.colleague.id
    assert timeline[0]["is_overdue"] is False

    inbox = client.get("/api/approvals/inbox", headers=auth(org.colleague)).get_json()
    assert [i["id"] for i in inbox["items"]] == [approval.id]
    assert client.get("/api/approvals/inbox", headers=auth(org.manager)).get_json()["total"] == 0

    row = _db.session.execute(
        _db.text("SELECT actor_id, old_value, new_value FROM audit_logs WHERE action = 'APPROVAL_REASSIGNED'")
    ).one()
    assert row.actor_id == org.admin.id
    assert row.old_value["approver_id"] == org.manager.id
    assert row.new_value["approver_id"] == org.colleague.id
    assert row.new_value["reason"] == "Manager is on leave"

    # the new approver can now decide it
    assert (
        client.post(f"/api/approvals/{approval.id}/approve", headers=auth(org.colleague)).status_code == 200
    )


@pytest.mark.parametrize(
    "who, reason, status",
    [
        ("employee", "x", 422),  # the requester
        ("manager", "x", 422),  # already the approver
        ("colleague", "   ", 422),  # blank reason
        ("colleague", "", 422),
    ],
)
def test_validation(client, org, approval, who, reason, status):
    resp = reassign(client, org.admin, approval, getattr(org, who), reason)
    assert resp.status_code == status


def test_inactive_target(client, org, approval, db):
    org.colleague.is_active = False
    db.session.commit()
    assert reassign(client, org.admin, approval, org.colleague).status_code == 422


def test_decided_approval_cannot_be_reassigned(client, org, approval):
    client.post(f"/api/approvals/{approval.id}/approve", headers=auth(org.manager))
    resp = reassign(client, org.admin, approval, org.colleague)
    assert resp.status_code == 409


def test_unknown_approval(client, org):
    resp = client.post(
        "/api/approvals/999999/reassign",
        json={"approver_id": org.colleague.id, "reason": "x"},
        headers=auth(org.admin),
    )
    assert resp.status_code == 404
