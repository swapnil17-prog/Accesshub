"""/api/approvals through HTTP with real JWTs, including full multi-step flows."""

from datetime import timedelta

from app.extensions import db as _db
from app.models import Approval, ApproverType
from app.models.mixins import utcnow
from tests.helpers import actions, auth, make_app

MGR, OWN, USR = ApproverType.MANAGER, ApproverType.APP_OWNER, ApproverType.SPECIFIC_USER
JUSTIFICATION = "Need access to work on the quarterly roadmap."


def create(client, user, application, level_index=0):
    body = {
        "application_id": application.id,
        "access_level_id": application.access_levels[level_index].id,
        "justification": JUSTIFICATION,
    }
    resp = client.post("/api/requests", json=body, headers=auth(user))
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


def inbox(client, user):
    resp = client.get("/api/approvals/inbox", headers=auth(user))
    assert resp.status_code == 200
    return resp.get_json()


def pending_id(request_body):
    return next(a["id"] for a in request_body["approvals"] if a["decision"] == "PENDING")


class TestInbox:
    def test_lists_open_approvals_oldest_due_first_with_overdue_flag(self, client, org):
        slow = make_app(org.owner, name="Slow", steps=[(MGR, None, 72)])
        fast = make_app(org.owner, name="Fast", steps=[(MGR, None, 4)])
        r_slow = create(client, org.employee, slow)
        r_fast = create(client, org.colleague, fast)
        overdue_app = make_app(org.owner, name="Late", steps=[(MGR, None, 24)])
        r_late = create(client, org.employee, overdue_app)
        late = _db.session.get(Approval, pending_id(r_late))
        late.due_at = utcnow() - timedelta(hours=1)
        _db.session.commit()

        body = inbox(client, org.manager)
        assert body["total"] == 3
        assert [i["request"]["id"] for i in body["items"]] == [r_late["id"], r_fast["id"], r_slow["id"]]
        assert [i["is_overdue"] for i in body["items"]] == [True, False, False]
        first = body["items"][0]
        assert first["request"]["requester"]["name"] == org.employee.name
        assert first["request"]["application"]["name"] == "Late"
        assert first["request"]["access_level"]["name"] == "Read"
        assert first["request"]["justification"] == JUSTIFICATION
        assert {"id", "step_order", "assigned_at", "due_at", "escalated"} <= set(first)

    def test_only_my_open_approvals(self, client, org):
        create(client, org.employee, make_app(org.owner, steps=[(MGR, None, 24)]))
        assert inbox(client, org.owner)["total"] == 0
        assert inbox(client, org.employee)["total"] == 0
        assert inbox(client, org.manager)["total"] == 1


class TestDecisions:
    def test_three_step_flow(self, client, org):
        application = make_app(org.owner, steps=[(MGR, None, 24), (OWN, None, 24), (USR, org.specialist, 8)])
        req = create(client, org.employee, application)

        for approver, expected_step in ((org.manager, 2), (org.owner, 3)):
            [item] = inbox(client, approver)["items"]
            resp = client.post(
                f"/api/approvals/{item['id']}/approve", json={"comment": "ok"}, headers=auth(approver)
            )
            assert resp.status_code == 200, resp.get_json()
            body = resp.get_json()
            assert body["status"] == "PENDING" and body["current_step"] == expected_step
            assert inbox(client, approver)["total"] == 0  # gone from my inbox

        [item] = inbox(client, org.specialist)["items"]
        resp = client.post(f"/api/approvals/{item['id']}/approve", headers=auth(org.specialist))  # no body
        body = resp.get_json()
        assert body["status"] == "APPROVED"
        assert [(a["step_order"], a["decision"], a["approver"]["name"]) for a in body["approvals"]] == [
            (1, "APPROVED", org.manager.name),
            (2, "APPROVED", org.owner.name),
            (3, "APPROVED", org.specialist.name),
        ]
        assert actions("access_request", req["id"])[-1] == "REQUEST_APPROVED"

        # the requester sees the finished timeline too
        detail = client.get(f"/api/requests/{req['id']}", headers=auth(org.employee)).get_json()
        assert all(a["decided_at"] for a in detail["approvals"])

    def test_reject_mid_chain(self, client, org):
        application = make_app(org.owner, steps=[(MGR, None, 24), (OWN, None, 24)])
        req = create(client, org.employee, application)
        client.post(f"/api/approvals/{pending_id(req)}/approve", headers=auth(org.manager))

        [item] = inbox(client, org.owner)["items"]
        no_comment = client.post(f"/api/approvals/{item['id']}/reject", json={}, headers=auth(org.owner))
        assert no_comment.status_code == 422
        assert "comment" in no_comment.get_json()["error"]["details"]

        resp = client.post(
            f"/api/approvals/{item['id']}/reject", json={"comment": "Use read-only"}, headers=auth(org.owner)
        )
        body = resp.get_json()
        assert body["status"] == "REJECTED"
        assert [a["decision"] for a in body["approvals"]] == ["APPROVED", "REJECTED"]
        assert body["approvals"][1]["comment"] == "Use read-only"

    def test_non_assignee_who_can_see_the_request_gets_403(self, client, org):
        req = create(client, org.employee, make_app(org.owner))
        for viewer in (org.admin, org.auditor, org.employee):  # can see it, may not decide it
            resp = client.post(f"/api/approvals/{pending_id(req)}/approve", headers=auth(viewer))
            assert resp.status_code == 403, viewer.name
            assert resp.get_json()["error"]["code"] == "NOT_AUTHORIZED"

    def test_outsider_gets_404_so_ids_cannot_be_probed(self, client, org):
        req = create(client, org.employee, make_app(org.owner))
        for action, body in (("approve", None), ("reject", {"comment": "no"})):
            resp = client.post(
                f"/api/approvals/{pending_id(req)}/{action}", json=body, headers=auth(org.colleague)
            )
            assert resp.status_code == 404
        missing = client.post("/api/approvals/999999/approve", headers=auth(org.colleague))
        assert missing.status_code == 404  # indistinguishable from an existing approval

    def test_double_decision_gets_409(self, client, org):
        req = create(client, org.employee, make_app(org.owner))
        url = f"/api/approvals/{pending_id(req)}"
        assert client.post(f"{url}/approve", headers=auth(org.manager)).status_code == 200
        again = client.post(f"{url}/reject", json={"comment": "oops"}, headers=auth(org.manager))
        assert again.status_code == 409
        assert again.get_json()["error"]["code"] == "INVALID_STATE"

    def test_unknown_approval_is_404(self, client, org):
        assert client.post("/api/approvals/999999/approve", headers=auth(org.manager)).status_code == 404

    def test_bad_body(self, client, org):
        req = create(client, org.employee, make_app(org.owner))
        resp = client.post(
            f"/api/approvals/{pending_id(req)}/approve", json={"comment": 5}, headers=auth(org.manager)
        )
        assert resp.status_code == 422
