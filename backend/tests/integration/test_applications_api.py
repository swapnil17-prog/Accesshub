"""/api/applications: CRUD, access levels and workflow replacement/validation."""

import pytest

from app.extensions import db as _db
from app.models import Application, ApproverType
from tests.factories import AccessRequestFactory
from tests.helpers import actions, auth, make_app

MGR, OWN = ApproverType.MANAGER, ApproverType.APP_OWNER
JUSTIFICATION = "Needed for the data migration project."


def step(order, approver_type="MANAGER", sla=24, user_id=None):
    data = {"step_order": order, "approver_type": approver_type, "sla_hours": sla}
    if user_id is not None:
        data["approver_user_id"] = user_id
    return data


class TestCrud:
    def test_create_with_levels(self, client, org):
        resp = client.post(
            "/api/applications",
            json={
                "name": " Confluence ",
                "description": "Wiki",
                "owner_id": org.owner.id,
                "access_levels": ["Read", "Edit", "Read"],
            },
            headers=auth(org.admin),
        )
        assert resp.status_code == 201, resp.get_json()
        body = resp.get_json()
        assert body["name"] == "Confluence"
        assert body["owner"]["id"] == org.owner.id
        assert [lvl["name"] for lvl in body["access_levels"]] == ["Read", "Edit"]
        assert body["workflow_steps"] == [] and body["is_active"] is True
        assert actions("application", body["id"]) == ["APPLICATION_CREATED"]

    def test_duplicate_name_is_409_case_insensitive(self, client, org):
        make_app(org.owner, name="Jira")
        resp = client.post(
            "/api/applications", json={"name": "JIRA", "owner_id": org.owner.id}, headers=auth(org.admin)
        )
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "NAME_TAKEN"

    @pytest.mark.parametrize("who", ["employee", "nobody"])
    def test_owner_must_be_active_app_owner_or_admin(self, client, org, who):
        owner_id = org.employee.id if who == "employee" else 999999
        resp = client.post(
            "/api/applications", json={"name": "X", "owner_id": owner_id}, headers=auth(org.admin)
        )
        assert resp.status_code == 422
        assert "owner_id" in resp.get_json()["error"]["details"]

    def test_list_search_and_inactive(self, client, org):
        make_app(org.owner, name="GitHub")
        make_app(org.owner, name="GitLab", is_active=False)
        make_app(org.owner, name="Workday")

        def names(user, query=""):
            body = client.get(f"/api/applications{query}", headers=auth(user)).get_json()
            return [a["name"] for a in body["items"]]

        assert names(org.employee) == ["GitHub", "Workday"]
        assert names(org.employee, "?include_inactive=true") == [
            "GitHub",
            "Workday",
        ]  # ignored for non-admins
        assert names(org.admin, "?include_inactive=true") == ["GitHub", "GitLab", "Workday"]
        assert names(org.employee, "?q=git") == ["GitHub"]
        assert names(org.employee, "?q=%25") == []  # LIKE wildcards are escaped

    def test_inactive_app_hidden_from_non_managers(self, client, org):
        application = make_app(org.owner, is_active=False)
        assert (
            client.get(f"/api/applications/{application.id}", headers=auth(org.employee)).status_code == 404
        )
        assert client.get(f"/api/applications/{application.id}", headers=auth(org.owner)).status_code == 200

    def test_owner_updates_own_app_and_only_changes_are_audited(self, client, org):
        application = make_app(org.owner, name="Jira", description="old")
        resp = client.put(
            f"/api/applications/{application.id}",
            json={"name": "Jira", "description": "new"},
            headers=auth(org.owner),
        )
        assert resp.status_code == 200
        assert resp.get_json()["description"] == "new"
        row = _db.session.execute(
            _db.text("SELECT old_value, new_value FROM audit_logs WHERE action = 'APPLICATION_UPDATED'")
        ).one()
        assert row.old_value == {"description": "old"} and row.new_value == {"description": "new"}

    def test_admin_reassigns_owner(self, client, org):
        application = make_app(org.owner)
        resp = client.put(
            f"/api/applications/{application.id}", json={"owner_id": org.admin.id}, headers=auth(org.admin)
        )
        assert resp.get_json()["owner"]["id"] == org.admin.id

    def test_soft_delete(self, client, org):
        application = make_app(org.owner)
        resp = client.delete(f"/api/applications/{application.id}", headers=auth(org.admin))
        assert resp.status_code == 200 and resp.get_json()["is_active"] is False
        _db.session.expire_all()
        assert _db.session.get(Application, application.id) is not None  # still in the database
        submit = client.post(
            "/api/requests",
            json={
                "application_id": application.id,
                "access_level_id": application.access_levels[0].id,
                "justification": JUSTIFICATION,
            },
            headers=auth(org.employee),
        )
        assert submit.status_code == 404
        assert actions("application", application.id)[-1] == "APPLICATION_DEACTIVATED"


class TestAccessLevels:
    def test_add_rename_delete(self, client, org):
        application = make_app(org.owner, levels=["Read"])
        base = f"/api/applications/{application.id}/access-levels"
        created = client.post(base, json={"name": "Admin"}, headers=auth(org.owner))
        assert created.status_code == 201
        level_id = created.get_json()["id"]

        assert client.post(base, json={"name": "admin"}, headers=auth(org.owner)).status_code == 409
        renamed = client.put(f"{base}/{level_id}", json={"name": "Administrator"}, headers=auth(org.owner))
        assert renamed.get_json()["name"] == "Administrator"
        assert client.delete(f"{base}/{level_id}", headers=auth(org.owner)).status_code == 204
        names = [lvl["name"] for lvl in client.get(base, headers=auth(org.employee)).get_json()["items"]]
        assert names == ["Read"]
        assert actions("access_level", level_id) == [
            "ACCESS_LEVEL_CREATED",
            "ACCESS_LEVEL_UPDATED",
            "ACCESS_LEVEL_DELETED",
        ]

    def test_level_with_requests_cannot_be_deleted(self, client, org):
        application = make_app(org.owner)
        level = application.access_levels[0]
        AccessRequestFactory(requester=org.employee, application=application, access_level=level)
        resp = client.delete(
            f"/api/applications/{application.id}/access-levels/{level.id}", headers=auth(org.admin)
        )
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "LEVEL_IN_USE"

    def test_unknown_level_is_404(self, client, org):
        application = make_app(org.owner)
        url = f"/api/applications/{application.id}/access-levels/999999"
        assert client.put(url, json={"name": "x"}, headers=auth(org.admin)).status_code == 404


class TestWorkflow:
    def url(self, application):
        return f"/api/applications/{application.id}/workflow"

    def test_get_shows_ordered_steps_with_approver(self, client, org):
        application = make_app(
            org.owner, steps=[(MGR, None, 24), (ApproverType.SPECIFIC_USER, org.specialist, 8)]
        )
        body = client.get(self.url(application), headers=auth(org.employee)).get_json()
        assert body["application_id"] == application.id
        assert [(s["step_order"], s["approver_type"]) for s in body["steps"]] == [
            (1, "MANAGER"),
            (2, "SPECIFIC_USER"),
        ]
        assert body["steps"][1]["approver_user"]["name"] == org.specialist.name

    def test_put_replaces_whole_list_and_is_audited(self, client, org):
        application = make_app(org.owner, steps=[(MGR, None, 24), (OWN, None, 24)])
        steps = [
            step(2, "SPECIFIC_USER", 8, org.specialist.id),  # order in the body does not matter
            step(1, "APP_OWNER", 48),
            step(3, "MANAGER", 12),
        ]
        resp = client.put(self.url(application), json={"steps": steps}, headers=auth(org.owner))
        assert resp.status_code == 200, resp.get_json()
        got = [(s["step_order"], s["approver_type"], s["sla_hours"]) for s in resp.get_json()["steps"]]
        assert got == [(1, "APP_OWNER", 48), (2, "SPECIFIC_USER", 8), (3, "MANAGER", 12)]

        row = _db.session.execute(
            _db.text("SELECT old_value, new_value FROM audit_logs WHERE action = 'WORKFLOW_UPDATED'")
        ).one()
        assert [s["approver_type"] for s in row.old_value["steps"]] == ["MANAGER", "APP_OWNER"]
        assert [s["approver_type"] for s in row.new_value["steps"]] == [
            "APP_OWNER",
            "SPECIFIC_USER",
            "MANAGER",
        ]

    @pytest.mark.parametrize(
        "steps, where",
        [
            ([], "steps"),
            ([step(1), step(3)], "steps"),  # gap
            ([step(1), step(1)], "steps"),  # duplicate
            ([step(2)], "steps"),  # does not start at 1
            ([step(1, "SPECIFIC_USER")], "0"),  # missing user
            ([step(1, "MANAGER", user_id=1)], "0"),  # user on a non-SPECIFIC step
            ([step(i) for i in range(1, 12)], "steps"),  # too many
        ],
        ids=["empty", "gap", "duplicate", "not-from-1", "specific-no-user", "user-on-manager", "too-many"],
    )
    def test_validation(self, client, org, steps, where):
        application = make_app(org.owner, steps=[(MGR, None, 24)])
        resp = client.put(self.url(application), json={"steps": steps}, headers=auth(org.admin))
        assert resp.status_code == 422, resp.get_json()
        assert where in resp.get_json()["error"]["details"]
        # the existing workflow is untouched
        current = client.get(self.url(application), headers=auth(org.admin)).get_json()["steps"]
        assert [(s["step_order"], s["approver_type"]) for s in current] == [(1, "MANAGER")]

    @pytest.mark.parametrize("sla", [0, 169])
    def test_sla_range(self, client, org, sla):
        application = make_app(org.owner)
        resp = client.put(self.url(application), json={"steps": [step(1, sla=sla)]}, headers=auth(org.admin))
        assert resp.status_code == 422

    def test_specific_user_must_be_active(self, client, org, db):
        org.specialist.is_active = False
        db.session.commit()
        application = make_app(org.owner)
        resp = client.put(
            self.url(application),
            json={"steps": [step(1, "SPECIFIC_USER", 8, org.specialist.id)]},
            headers=auth(org.admin),
        )
        assert resp.status_code == 422
        assert resp.get_json()["error"]["details"]["0"]["approver_user_id"] == ["Must be an active user."]

    def test_change_does_not_affect_in_flight_requests(self, client, org):
        application = make_app(org.owner, steps=[(MGR, None, 24)])
        body = {
            "application_id": application.id,
            "access_level_id": application.access_levels[0].id,
            "justification": JUSTIFICATION,
        }
        in_flight = client.post("/api/requests", json=body, headers=auth(org.employee)).get_json()

        new_steps = {"steps": [step(1, "MANAGER"), step(2, "APP_OWNER")]}
        assert client.put(self.url(application), json=new_steps, headers=auth(org.admin)).status_code == 200

        approval_id = in_flight["approvals"][0]["id"]
        done = client.post(f"/api/approvals/{approval_id}/approve", headers=auth(org.manager)).get_json()
        assert done["status"] == "APPROVED" and done["total_steps"] == 1

        newer = client.post("/api/requests", json=body, headers=auth(org.colleague)).get_json()
        assert newer["total_steps"] == 2
