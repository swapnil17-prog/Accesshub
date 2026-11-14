"""/api/audit (filters, CSV export) and /api/reports/summary."""

import csv
import io
from datetime import timedelta

import pytest

from app.extensions import db as _db
from app.models import Approval, AuditLog, Decision, RequestStatus
from app.models.mixins import utcnow
from app.services.audit import log_action
from tests.factories import AccessRequestFactory, ApprovalFactory, UserFactory
from tests.helpers import auth, make_app


def add_log(actor, action, entity_type="thing", entity_id=1, days_ago=0, **values):
    entry = log_action(actor, action, entity_type, entity_id, **values)
    entry.created_at = utcnow() - timedelta(days=days_ago)
    return entry


@pytest.fixture()
def logs(org):
    add_log(org.employee, "REQUEST_CREATED", "access_request", 10, days_ago=5)
    add_log(org.manager, "APPROVAL_APPROVED", "approval", 20, days_ago=3)
    add_log(None, "APPROVAL_ESCALATED", "approval", 20, days_ago=1)
    add_log(org.employee, "REQUEST_CREATED", "access_request", 11, days_ago=0)
    _db.session.commit()


class TestList:
    def ids(self, client, user, query=""):
        body = client.get(f"/api/audit{query}", headers=auth(user)).get_json()
        return [(i["action"], i["entity_id"]) for i in body["items"]]

    def test_newest_first_with_actor(self, client, org, logs):
        body = client.get("/api/audit", headers=auth(org.auditor)).get_json()
        assert body["total"] == 4
        assert [i["entity_id"] for i in body["items"]] == [11, 20, 20, 10]
        assert body["items"][0]["actor"]["name"] == org.employee.name
        assert body["items"][1]["actor"] is None  # system

    def test_filters(self, client, org, logs):
        a = org.auditor
        assert self.ids(client, a, f"?actor={org.manager.id}") == [("APPROVAL_APPROVED", 20)]
        assert self.ids(client, a, "?actor=system") == [("APPROVAL_ESCALATED", 20)]
        assert self.ids(client, a, "?action=REQUEST_CREATED") == [
            ("REQUEST_CREATED", 11),
            ("REQUEST_CREATED", 10),
        ]
        assert self.ids(client, a, "?entity_type=approval&entity_id=20") == [
            ("APPROVAL_ESCALATED", 20),
            ("APPROVAL_APPROVED", 20),
        ]
        today = utcnow().date()
        window = f"?from={today - timedelta(days=4)}&to={today - timedelta(days=2)}"
        assert self.ids(client, a, window) == [("APPROVAL_APPROVED", 20)]

    @pytest.mark.parametrize("query", ["?actor=bob", "?from=nope", "?per_page=500"])
    def test_bad_filters(self, client, org, query):
        assert client.get(f"/api/audit{query}", headers=auth(org.admin)).status_code == 422


class TestCsvExport:
    def parse(self, resp):
        return list(csv.DictReader(io.StringIO(resp.get_data(as_text=True))))

    def test_streams_csv_with_filters(self, client, org, logs):
        resp = client.get("/api/audit/export.csv?action=REQUEST_CREATED", headers=auth(org.auditor))
        assert resp.status_code == 200
        assert resp.is_streamed
        assert resp.mimetype == "text/csv"
        assert resp.headers["Content-Disposition"].startswith('attachment; filename="audit-')
        rows = self.parse(resp)
        assert [r["entity_id"] for r in rows] == ["11", "10"]
        assert rows[0]["actor_email"] == org.employee.email
        assert list(rows[0]) == [
            "id", "created_at", "actor_id", "actor_name", "actor_email", "action",
            "entity_type", "entity_id", "old_value", "new_value", "ip_address", "user_agent",
        ]  # fmt: skip

    def test_system_actor_and_json_values(self, client, org, logs):
        add_log(None, "REQUEST_EXPIRED", "access_request", 12, new={"status": "EXPIRED"})
        _db.session.commit()
        rows = self.parse(
            client.get("/api/audit/export.csv?actor=system&action=REQUEST_EXPIRED", headers=auth(org.admin))
        )
        assert rows[0]["actor_id"] == "system"
        assert rows[0]["new_value"] == '{"status": "EXPIRED"}'

    def test_formula_injection_is_neutralised(self, client, org):
        attacker = UserFactory(name='=HYPERLINK("http://evil")', roles=["employee"])
        add_log(attacker, "LOGIN_SUCCESS", "user", attacker.id)
        _db.session.commit()
        rows = self.parse(client.get("/api/audit/export.csv?action=LOGIN_SUCCESS", headers=auth(org.auditor)))
        assert rows[0]["actor_name"].startswith("'=")

    def test_export_is_itself_audited(self, client, org):
        client.get("/api/audit/export.csv?action=X", headers=auth(org.auditor)).get_data()
        entry = _db.session.query(AuditLog).filter_by(action="AUDIT_EXPORTED").one()
        assert entry.actor_id == org.auditor.id
        assert entry.new_value == {"action": "X"}


class TestSummary:
    def test_numbers(self, client, org):
        jira = make_app(org.owner, name="Jira")
        aws = make_app(org.owner, name="AWS")
        make_app(org.owner, name="Unused")
        now = utcnow()

        # Two approved requests, decided 10h and 30h after submission -> average 20h.
        for hours, application in ((10, jira), (30, aws)):
            req = AccessRequestFactory(
                requester=org.employee,
                application=application,
                access_level=application.access_levels[0],
                status=RequestStatus.APPROVED,
                created_at=now - timedelta(days=2),
            )
            ApprovalFactory(
                request=req,
                approver=org.manager,
                decision=Decision.APPROVED,
                decided_at=req.created_at + timedelta(hours=hours),
            )
        AccessRequestFactory(
            requester=org.colleague,
            application=jira,
            access_level=jira.access_levels[0],
            status=RequestStatus.REJECTED,
        )
        pending = AccessRequestFactory(
            requester=org.colleague, application=jira, access_level=jira.access_levels[1]
        )
        ApprovalFactory(request=pending, approver=org.manager, due_at=now - timedelta(hours=1))  # overdue

        add_log(None, "APPROVAL_ESCALATED", days_ago=2)
        add_log(None, "APPROVAL_ESCALATED", days_ago=45)  # outside the 30-day window
        _db.session.commit()

        body = client.get("/api/reports/summary", headers=auth(org.auditor)).get_json()
        assert body["total_requests"] == 4
        assert body["by_status"] == {"PENDING": 1, "APPROVED": 2, "REJECTED": 1, "CANCELLED": 0, "EXPIRED": 0}
        assert [(a["name"], a["total"]) for a in body["by_application"]] == [
            ("Jira", 3),
            ("AWS", 1),
            ("Unused", 0),
        ]
        assert body["by_application"][0]["by_status"]["PENDING"] == 1
        assert body["avg_approval_hours"] == 20.0
        assert body["escalations_last_30_days"] == 1
        assert body["overdue_approvals"] == 1

    def test_empty_database(self, client, org):
        body = client.get("/api/reports/summary", headers=auth(org.admin)).get_json()
        assert body["total_requests"] == 0
        assert body["avg_approval_hours"] is None
        assert _db.session.query(Approval).count() == 0
