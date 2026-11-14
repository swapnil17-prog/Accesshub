"""Emails sent by the workflow (captured with Flask-Mail's record_messages)."""

import logging

from app.extensions import mail
from app.models import AccessRequest, RequestStatus
from app.services import notifications
from tests.helpers import auth, make_app

JUSTIFICATION = "Need it for <script>alert('x')</script> the audit project."


def submit(client, user, application):
    body = {
        "application_id": application.id,
        "access_level_id": application.access_levels[0].id,
        "justification": JUSTIFICATION,
        "duration_days": 30,
    }
    resp = client.post("/api/requests", json=body, headers=auth(user))
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


def test_approval_needed_email_with_deep_link(app, client, org):
    application = make_app(org.owner, name="Jira")
    with mail.record_messages() as outbox:
        req = submit(client, org.employee, application)

    [msg] = outbox
    assert msg.recipients == [org.manager.email]
    assert msg.subject == f"[AccessHub] Approval needed: Jira - Read for {org.employee.name}"
    link = f"{app.config['FRONTEND_URL']}/requests/{req['id']}"
    assert link in msg.body and link in msg.html
    assert f"{app.config['FRONTEND_URL']}/approvals" in msg.body
    # user input is escaped in HTML, shown as-is in plain text
    assert "<script>" not in msg.html and "&lt;script&gt;" in msg.html
    assert "<script>" in msg.body


def test_approved_and_rejected_emails_go_to_requester(client, org):
    application = make_app(org.owner)
    first = submit(client, org.employee, application)
    with mail.record_messages() as outbox:
        client.post(f"/api/approvals/{first['approvals'][0]['id']}/approve", headers=auth(org.manager))
    [approved] = outbox
    assert approved.recipients == [org.employee.email]
    assert approved.subject.startswith("[AccessHub] Approved:")
    assert "expires on" in approved.body

    second = submit(client, org.colleague, application)
    with mail.record_messages() as outbox:
        client.post(
            f"/api/approvals/{second['approvals'][0]['id']}/reject",
            json={"comment": "Use the shared account"},
            headers=auth(org.manager),
        )
    [rejected] = outbox
    assert rejected.recipients == [org.colleague.email]
    assert rejected.subject.startswith("[AccessHub] Rejected:")
    assert "Use the shared account" in rejected.body and org.manager.name in rejected.body


def test_send_failure_is_logged_and_does_not_roll_back(client, org, monkeypatch, caplog, db):
    application = make_app(org.owner)
    req = submit(client, org.employee, application)

    def smtp_down(_message):
        raise ConnectionRefusedError("SMTP down")

    monkeypatch.setattr(mail, "send", smtp_down)
    with caplog.at_level(logging.ERROR, logger="app.services.notifications"):
        resp = client.post(f"/api/approvals/{req['approvals'][0]['id']}/approve", headers=auth(org.manager))

    assert resp.status_code == 200
    db.session.expire_all()
    assert db.session.get(AccessRequest, req["id"]).status == RequestStatus.APPROVED
    assert "Failed to send request_approved" in caplog.text


def test_inactive_and_duplicate_recipients_are_skipped(app, org, db):
    application = make_app(org.owner)
    req = submit(app.test_client(), org.employee, application)
    org.colleague.is_active = False
    db.session.commit()
    request = db.session.get(AccessRequest, req["id"])
    with mail.record_messages() as outbox:
        notifications.notify(
            notifications.REQUEST_APPROVED, request, [org.employee, org.employee, org.colleague]
        )
    assert [m.recipients for m in outbox] == [[org.employee.email]]


def test_unknown_event_is_ignored(app, org, caplog):
    application = make_app(org.owner)
    req = submit(app.test_client(), org.employee, application)
    from app.extensions import db

    with mail.record_messages() as outbox, caplog.at_level(logging.ERROR):
        notifications.notify("nope", db.session.get(AccessRequest, req["id"]), [org.employee])
    assert outbox == [] and "Unknown notification event" in caplog.text
