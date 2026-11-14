"""/api/users: admin user management, manager-cycle prevention and lockout guards."""

import pytest

from app.errors import InvalidStateError
from app.extensions import db as _db
from app.services import users as user_service
from tests.helpers import actions, auth


def put(client, admin, user, body):
    return client.put(f"/api/users/{user.id}", json=body, headers=auth(admin))


class TestList:
    def test_search_filters_and_shape(self, client, org):
        headers = auth(org.admin)
        body = client.get("/api/users?q=MANAGER", headers=headers).get_json()
        assert [u["name"] for u in body["items"]] == ["Max Manager"]
        item = body["items"][0]
        assert item["manager"]["id"] == org.admin.id
        assert "password_hash" not in item and "password" not in item

        by_email = client.get(f"/api/users?q={org.specialist.email}", headers=headers).get_json()
        assert [u["id"] for u in by_email["items"]] == [org.specialist.id]

        auditors = client.get("/api/users?role=auditor", headers=headers).get_json()
        assert [u["id"] for u in auditors["items"]] == [org.auditor.id]

    def test_active_filter_and_pagination(self, client, org, db):
        org.colleague.is_active = False
        db.session.commit()
        headers = auth(org.admin)
        inactive = client.get("/api/users?is_active=false", headers=headers).get_json()
        assert [u["id"] for u in inactive["items"]] == [org.colleague.id]
        page = client.get("/api/users?per_page=3&page=2", headers=headers).get_json()
        assert (page["total"], page["page"], len(page["items"])) == (7, 2, 3)

    def test_lookup_returns_brief_active_users(self, client, org, db):
        org.colleague.is_active = False
        db.session.commit()
        items = client.get("/api/users/lookup?q=c", headers=auth(org.owner)).get_json()["items"]
        assert all(set(i) == {"id", "name", "email"} for i in items)
        assert org.colleague.id not in [i["id"] for i in items]


class TestCreate:
    def test_create_and_log_in(self, client, org):
        resp = client.post(
            "/api/users",
            json={
                "name": "Nina New",
                "email": "Nina@Example.com",
                "password": "Welcome#2026",
                "department": "Sales",
                "manager_id": org.manager.id,
            },
            headers=auth(org.admin),
        )
        assert resp.status_code == 201, resp.get_json()
        body = resp.get_json()
        assert body["email"] == "nina@example.com"
        assert body["roles"] == ["employee"]
        assert body["manager"]["id"] == org.manager.id
        login = client.post("/api/auth/login", json={"email": "nina@example.com", "password": "Welcome#2026"})
        assert login.status_code == 200
        assert actions("user", body["id"])[0] == "USER_CREATED"

    @pytest.mark.parametrize(
        "override, field",
        [
            ({"password": "short"}, "password"),
            ({"email": "not-an-email"}, "email"),
            ({"roles": ["superuser"]}, "roles"),
            ({"manager_id": 999999}, "manager_id"),
        ],
    )
    def test_validation(self, client, org, override, field):
        body = {"name": "X", "email": "x@example.com", "password": "LongEnough1!", **override}
        resp = client.post("/api/users", json=body, headers=auth(org.admin))
        assert resp.status_code == 422
        assert field in resp.get_json()["error"]["details"]

    def test_duplicate_email(self, client, org):
        body = {"name": "Dup", "email": org.employee.email.upper(), "password": "LongEnough1!"}
        resp = client.post("/api/users", json=body, headers=auth(org.admin))
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "EMAIL_TAKEN"


class TestUpdate:
    def test_profile_and_manager(self, client, org):
        resp = put(
            client, org.admin, org.specialist, {"department": "Security", "manager_id": org.manager.id}
        )
        assert resp.status_code == 200
        assert resp.get_json()["department"] == "Security"
        assert resp.get_json()["manager_id"] == org.manager.id
        assert put(client, org.admin, org.specialist, {"manager_id": None}).get_json()["manager_id"] is None

    @pytest.mark.parametrize(
        "target, new_manager",
        [
            ("manager", "employee"),  # employee -> manager: direct cycle
            ("admin", "employee"),  # employee -> manager -> admin: longer cycle
            ("employee", "employee"),  # self
        ],
    )
    def test_manager_cycles_rejected(self, client, org, target, new_manager):
        user, manager = getattr(org, target), getattr(org, new_manager)
        resp = put(client, org.admin, user, {"manager_id": manager.id})
        assert resp.status_code == 422
        assert "manager_id" in resp.get_json()["error"]["details"]
        _db.session.expire_all()
        assert org.manager.manager_id == org.admin.id  # nothing changed

    def test_inactive_manager_rejected(self, client, org, db):
        org.manager.is_active = False
        db.session.commit()
        assert put(client, org.admin, org.specialist, {"manager_id": org.manager.id}).status_code == 422

    def test_deactivate_blocks_further_access(self, client, org):
        token = auth(org.colleague)
        assert put(client, org.admin, org.colleague, {"is_active": False}).get_json()["is_active"] is False
        resp = client.get("/api/auth/me", headers=token)
        assert resp.status_code == 401 and resp.get_json()["error"]["code"] == "USER_INACTIVE"

    def test_cannot_deactivate_self(self, client, org):
        resp = put(client, org.admin, org.admin, {"is_active": False})
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "SELF_LOCKOUT"

    def test_password_change_is_audited_without_the_password(self, client, org):
        assert put(client, org.admin, org.colleague, {"password": "BrandNew#Pass1"}).status_code == 200
        login = client.post(
            "/api/auth/login", json={"email": org.colleague.email, "password": "BrandNew#Pass1"}
        )
        assert login.status_code == 200
        row = _db.session.execute(
            _db.text("SELECT new_value::text AS v FROM audit_logs WHERE action = 'USER_UPDATED'")
        ).one()
        assert "password_changed" in row.v and "BrandNew" not in row.v and "pbkdf2" not in row.v

    def test_email_conflict(self, client, org):
        resp = put(client, org.admin, org.colleague, {"email": org.employee.email})
        assert resp.status_code == 409

    def test_unknown_user(self, client, org):
        assert client.put("/api/users/999999", json={"name": "x"}, headers=auth(org.admin)).status_code == 404


class TestRoles:
    def test_replace_roles(self, client, org):
        resp = client.put(
            f"/api/users/{org.colleague.id}/roles",
            json={"roles": ["employee", "manager", "manager"]},
            headers=auth(org.admin),
        )
        assert resp.status_code == 200
        assert resp.get_json()["roles"] == ["employee", "manager"]
        row = _db.session.execute(
            _db.text("SELECT old_value, new_value FROM audit_logs WHERE action = 'USER_ROLES_CHANGED'")
        ).one()
        assert row.old_value == {"roles": ["employee"]}
        assert row.new_value == {"roles": ["employee", "manager"]}

    def test_cannot_remove_own_admin_role(self, client, org):
        resp = client.put(
            f"/api/users/{org.admin.id}/roles", json={"roles": ["employee"]}, headers=auth(org.admin)
        )
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "SELF_LOCKOUT"

    def test_can_remove_another_admin(self, client, org):
        client.put(
            f"/api/users/{org.manager.id}/roles",
            json={"roles": ["manager", "admin"]},
            headers=auth(org.admin),
        )
        resp = client.put(
            f"/api/users/{org.manager.id}/roles", json={"roles": ["manager"]}, headers=auth(org.admin)
        )
        assert resp.status_code == 200

    def test_last_admin_guard(self, org):
        # Through the API the acting admin always remains, so exercise the guard directly.
        with pytest.raises(InvalidStateError) as exc:
            user_service.set_roles(org.manager, org.admin.id, ["employee"])
        assert exc.value.code == "LAST_ADMIN"

    def test_unknown_role(self, client, org):
        resp = client.put(
            f"/api/users/{org.colleague.id}/roles", json={"roles": ["god"]}, headers=auth(org.admin)
        )
        assert resp.status_code == 422
