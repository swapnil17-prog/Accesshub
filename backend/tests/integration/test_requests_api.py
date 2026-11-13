"""/api/requests through HTTP with real JWTs."""

from datetime import timedelta

import pytest

from app.extensions import db as _db
from app.models import AccessRequest, ApproverType, RequestStatus
from app.models.mixins import utcnow
from tests.helpers import auth, make_app

MGR, OWN, USR = ApproverType.MANAGER, ApproverType.APP_OWNER, ApproverType.SPECIFIC_USER
JUSTIFICATION = "Need access to work on the quarterly roadmap."


def create(client, user, application, level_index=0, **extra):
    body = {
        "application_id": application.id,
        "access_level_id": application.access_levels[level_index].id,
        "justification": JUSTIFICATION,
        **extra,
    }
    return client.post("/api/requests", json=body, headers=auth(user))


class TestCreate:
    def test_created_with_timeline(self, client, org):
        application = make_app(org.owner, steps=[(MGR, None, 24), (OWN, None, 48)])
        resp = create(client, org.employee, application, duration_days=90)
        assert resp.status_code == 201
        body = resp.get_json()
        assert resp.headers["Location"].endswith(f"/api/requests/{body['id']}")
        assert body["status"] == "PENDING"
        assert body["current_step"] == 1 and body["total_steps"] == 2
        assert body["duration_days"] == 90
        assert body["requester"]["id"] == org.employee.id
        assert body["application"] == {"id": application.id, "name": application.name}
        assert body["steps"] == [
            {"step_order": 1, "approver_type": "MANAGER", "sla_hours": 24},
            {"step_order": 2, "approver_type": "APP_OWNER", "sla_hours": 48},
        ]
        [step1] = body["approvals"]
        assert step1["approver"]["name"] == org.manager.name
        assert step1["decision"] == "PENDING" and step1["is_overdue"] is False

    @pytest.mark.parametrize(
        "override, field",
        [
            ({"justification": "too short"}, "justification"),
            ({"justification": "                         x"}, "justification"),
            ({"duration_days": 0}, "duration_days"),
            ({"duration_days": 400}, "duration_days"),
            ({"application_id": "1"}, "application_id"),
            ({"surprise": True}, "surprise"),
        ],
    )
    def test_validation(self, client, org, override, field):
        application = make_app(org.owner)
        resp = create(client, org.employee, application, **override)
        assert resp.status_code == 422
        assert field in resp.get_json()["error"]["details"]

    def test_missing_fields(self, client, org):
        resp = client.post("/api/requests", json={}, headers=auth(org.employee))
        assert resp.status_code == 422
        assert set(resp.get_json()["error"]["details"]) == {
            "application_id",
            "access_level_id",
            "justification",
        }

    def test_duplicate_is_409(self, client, org):
        application = make_app(org.owner)
        assert create(client, org.employee, application).status_code == 201
        resp = create(client, org.employee, application)
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "DUPLICATE_REQUEST"

    def test_unknown_application_is_404(self, client, org):
        body = {"application_id": 999999, "access_level_id": 1, "justification": JUSTIFICATION}
        assert client.post("/api/requests", json=body, headers=auth(org.employee)).status_code == 404

    def test_requires_employee_role(self, client, org, db):
        org.specialist.roles.clear()
        db.session.commit()
        resp = create(client, org.specialist, make_app(org.owner))
        assert resp.status_code == 403
        assert resp.get_json()["error"]["code"] == "FORBIDDEN"

    def test_requires_auth(self, client, org):
        assert client.post("/api/requests", json={}).status_code == 401


class TestList:
    @pytest.fixture()
    def data(self, client, org):
        jira = make_app(org.owner, name="Jira")
        aws = make_app(org.owner, name="AWS")
        ids = {
            "eve_jira": create(client, org.employee, jira).get_json()["id"],
            "eve_aws": create(client, org.employee, aws).get_json()["id"],
            "carl_jira": create(client, org.colleague, jira).get_json()["id"],
        }
        old = _db.session.get(AccessRequest, ids["eve_aws"])
        old.created_at = utcnow() - timedelta(days=10)
        old.status = RequestStatus.REJECTED
        _db.session.commit()
        return {"jira": jira, "aws": aws, **ids}

    @staticmethod
    def ids(resp):
        return [item["id"] for item in resp.get_json()["items"]]

    def test_employee_sees_only_own(self, client, org, data):
        resp = client.get("/api/requests", headers=auth(org.employee))
        body = resp.get_json()
        assert set(body) == {"items", "page", "per_page", "total"}
        assert self.ids(resp) == [data["eve_jira"], data["eve_aws"]]  # newest first
        # requester_id is ignored for non-auditors
        resp = client.get(f"/api/requests?requester_id={org.colleague.id}", headers=auth(org.employee))
        assert set(self.ids(resp)) == {data["eve_jira"], data["eve_aws"]}

    def test_auditor_sees_all_and_filters(self, client, org, data):
        headers = auth(org.auditor)
        assert client.get("/api/requests", headers=headers).get_json()["total"] == 3
        resp = client.get(f"/api/requests?requester_id={org.colleague.id}", headers=headers)
        assert self.ids(resp) == [data["carl_jira"]]
        resp = client.get(f"/api/requests?application_id={data['jira'].id}", headers=headers)
        assert set(self.ids(resp)) == {data["eve_jira"], data["carl_jira"]}
        resp = client.get("/api/requests?status=REJECTED", headers=headers)
        assert self.ids(resp) == [data["eve_aws"]]

    def test_date_range(self, client, org, data):
        headers = auth(org.admin)
        today = utcnow().date()
        resp = client.get(
            f"/api/requests?from={today - timedelta(days=11)}&to={today - timedelta(days=5)}", headers=headers
        )
        assert self.ids(resp) == [data["eve_aws"]]
        resp = client.get(f"/api/requests?from={today}", headers=headers)
        assert set(self.ids(resp)) == {data["eve_jira"], data["carl_jira"]}

    def test_mine_for_admin(self, client, org, data):
        resp = client.get("/api/requests?mine=true", headers=auth(org.admin))
        assert resp.get_json()["total"] == 0

    def test_pagination(self, client, org, data):
        resp = client.get("/api/requests?per_page=2&page=2", headers=auth(org.auditor))
        body = resp.get_json()
        assert (body["page"], body["per_page"], body["total"], len(body["items"])) == (2, 2, 3, 1)

    @pytest.mark.parametrize("query", ["status=NOPE", "page=0", "per_page=101", "from=yesterday"])
    def test_bad_query(self, client, org, query):
        assert client.get(f"/api/requests?{query}", headers=auth(org.auditor)).status_code == 422


class TestDetailAndCancel:
    def test_visibility(self, client, org):
        req_id = create(client, org.employee, make_app(org.owner)).get_json()["id"]
        url = f"/api/requests/{req_id}"
        for viewer in (org.employee, org.manager, org.auditor, org.admin):
            assert client.get(url, headers=auth(viewer)).status_code == 200, viewer.name
        for outsider in (org.colleague, org.owner):
            resp = client.get(url, headers=auth(outsider))
            assert resp.status_code == 404, outsider.name

    def test_unknown_request_is_404(self, client, org):
        assert client.get("/api/requests/424242", headers=auth(org.admin)).status_code == 404

    def test_cancel(self, client, org):
        req_id = create(client, org.employee, make_app(org.owner)).get_json()["id"]
        resp = client.post(f"/api/requests/{req_id}/cancel", headers=auth(org.employee))
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["status"] == "CANCELLED"
        assert body["approvals"][0]["decision"] == "SKIPPED"

        again = client.post(f"/api/requests/{req_id}/cancel", headers=auth(org.employee))
        assert again.status_code == 409
        assert again.get_json()["error"]["code"] == "INVALID_STATE"

    def test_cancel_by_someone_else(self, client, org):
        req_id = create(client, org.employee, make_app(org.owner)).get_json()["id"]
        # The approver can see it but may not cancel it; an outsider cannot even see it.
        assert client.post(f"/api/requests/{req_id}/cancel", headers=auth(org.manager)).status_code == 403
        assert client.post(f"/api/requests/{req_id}/cancel", headers=auth(org.colleague)).status_code == 404
