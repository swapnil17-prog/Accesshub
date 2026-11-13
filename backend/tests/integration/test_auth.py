from datetime import timedelta

import pytest
from flask_jwt_extended import create_access_token, decode_token

from app.models import AuditAction, AuditLog, TokenBlocklist
from tests.conftest import bearer
from tests.factories import TEST_PASSWORD, UserFactory, get_or_create_role


def _audit_rows(db, action):
    return db.session.query(AuditLog).filter_by(action=action.value).all()


class TestLogin:
    def test_success_returns_tokens_and_user(self, client, db):
        user = UserFactory(email="ana@example.com", roles=["employee", "manager"])
        resp = client.post(
            "/api/auth/login",
            json={"email": "ANA@example.com", "password": TEST_PASSWORD},
            headers={"User-Agent": "pytest-browser"},
            environ_base={"REMOTE_ADDR": "192.168.1.5"},
        )
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["token_type"] == "Bearer"
        assert body["user"]["id"] == user.id
        assert body["user"]["roles"] == ["employee", "manager"]
        assert "password_hash" not in body["user"] and "password" not in body["user"]

        claims = decode_token(body["access_token"])
        assert claims["sub"] == str(user.id)
        assert claims["roles"] == ["employee", "manager"]
        assert claims["type"] == "access"
        assert decode_token(body["refresh_token"])["type"] == "refresh"

        [row] = _audit_rows(db, AuditAction.LOGIN_SUCCESS)
        assert row.actor_id == user.id
        assert row.ip_address == "192.168.1.5"
        assert row.user_agent == "pytest-browser"

    def test_wrong_password(self, client, db):
        user = UserFactory()
        resp = client.post("/api/auth/login", json={"email": user.email, "password": "wrong"})
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == "INVALID_CREDENTIALS"
        [row] = _audit_rows(db, AuditAction.LOGIN_FAILED)
        assert row.actor_id == user.id
        assert row.new_value == {"email": user.email, "reason": "bad_password"}

    def test_unknown_email_gives_same_error(self, client, db):
        resp = client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "x"})
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == "INVALID_CREDENTIALS"
        [row] = _audit_rows(db, AuditAction.LOGIN_FAILED)
        assert row.actor_id is None
        assert row.new_value["reason"] == "unknown_email"

    def test_inactive_user_cannot_login(self, client, db):
        user = UserFactory(is_active=False)
        resp = client.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == "INVALID_CREDENTIALS"
        assert _audit_rows(db, AuditAction.LOGIN_FAILED)[0].new_value["reason"] == "inactive"

    @pytest.mark.parametrize(
        "payload, field",
        [
            ({"password": "x"}, "email"),
            ({"email": "not-an-email", "password": "x"}, "email"),
            ({"email": "a@b.com"}, "password"),
            ({"email": "a@b.com", "password": "x", "extra": 1}, "extra"),
        ],
    )
    def test_validation_errors(self, client, db, payload, field):
        resp = client.post("/api/auth/login", json=payload)
        assert resp.status_code == 422
        error = resp.get_json()["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert field in error["details"]

    def test_non_json_body(self, client, db):
        resp = client.post("/api/auth/login", data="email=a", content_type="text/plain")
        assert resp.status_code == 422
        assert resp.get_json()["error"]["code"] == "VALIDATION_ERROR"


class TestMe:
    def test_me(self, client, db, login):
        user = UserFactory(roles=["auditor"])
        tokens = login(user)
        resp = client.get("/api/auth/me", headers=bearer(tokens["access_token"]))
        assert resp.status_code == 200
        assert resp.get_json()["email"] == user.email
        assert "password_hash" not in resp.get_json()

    def test_requires_token(self, client, db):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == "AUTHORIZATION_REQUIRED"

    def test_refresh_token_not_accepted(self, client, db, login):
        tokens = login(UserFactory())
        resp = client.get("/api/auth/me", headers=bearer(tokens["refresh_token"]))
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == "INVALID_TOKEN"

    def test_garbage_token(self, client, db):
        resp = client.get("/api/auth/me", headers=bearer("not.a.jwt"))
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == "INVALID_TOKEN"

    def test_expired_token(self, client, db):
        user = UserFactory()
        token = create_access_token(identity=str(user.id), expires_delta=timedelta(seconds=-1))
        resp = client.get("/api/auth/me", headers=bearer(token))
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == "TOKEN_EXPIRED"

    def test_deactivated_user_token_rejected(self, client, db, login):
        user = UserFactory()
        tokens = login(user)
        user.is_active = False
        db.session.commit()
        resp = client.get("/api/auth/me", headers=bearer(tokens["access_token"]))
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == "USER_INACTIVE"


class TestRefresh:
    def test_refresh_issues_working_access_token(self, client, db, login):
        user = UserFactory(roles=["employee"])
        tokens = login(user)
        resp = client.post("/api/auth/refresh", headers=bearer(tokens["refresh_token"]))
        assert resp.status_code == 200
        new_access = resp.get_json()["access_token"]
        assert client.get("/api/auth/me", headers=bearer(new_access)).status_code == 200

    def test_refresh_picks_up_role_changes(self, client, db, login):
        user = UserFactory(roles=["employee"])
        tokens = login(user)
        user.roles.append(get_or_create_role("admin"))
        db.session.commit()
        resp = client.post("/api/auth/refresh", headers=bearer(tokens["refresh_token"]))
        assert decode_token(resp.get_json()["access_token"])["roles"] == ["admin", "employee"]

    def test_access_token_cannot_refresh(self, client, db, login):
        tokens = login(UserFactory())
        resp = client.post("/api/auth/refresh", headers=bearer(tokens["access_token"]))
        assert resp.status_code == 401


class TestLogout:
    def test_logout_revokes_access_and_refresh(self, client, db, login):
        user = UserFactory()
        tokens = login(user)
        resp = client.post(
            "/api/auth/logout",
            headers=bearer(tokens["access_token"]),
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert resp.status_code == 200
        assert db.session.query(TokenBlocklist).count() == 2

        me = client.get("/api/auth/me", headers=bearer(tokens["access_token"]))
        assert me.status_code == 401
        assert me.get_json()["error"]["code"] == "TOKEN_REVOKED"
        refresh = client.post("/api/auth/refresh", headers=bearer(tokens["refresh_token"]))
        assert refresh.status_code == 401
        assert refresh.get_json()["error"]["code"] == "TOKEN_REVOKED"

        [row] = _audit_rows(db, AuditAction.LOGOUT)
        assert row.actor_id == user.id

    def test_logout_without_body_revokes_access_only(self, client, db, login):
        tokens = login(UserFactory())
        assert client.post("/api/auth/logout", headers=bearer(tokens["access_token"])).status_code == 200
        assert client.post("/api/auth/refresh", headers=bearer(tokens["refresh_token"])).status_code == 200

    def test_cannot_revoke_someone_elses_refresh_token(self, client, db, login):
        mine = login(UserFactory())
        theirs = login(UserFactory())
        resp = client.post(
            "/api/auth/logout",
            headers=bearer(mine["access_token"]),
            json={"refresh_token": theirs["refresh_token"]},
        )
        assert resp.status_code == 422
        assert client.post("/api/auth/refresh", headers=bearer(theirs["refresh_token"])).status_code == 200

    def test_invalid_refresh_token_in_body_is_ignored(self, client, db, login):
        tokens = login(UserFactory())
        resp = client.post(
            "/api/auth/logout", headers=bearer(tokens["access_token"]), json={"refresh_token": "garbage"}
        )
        assert resp.status_code == 200


class TestErrorFormat:
    def test_404(self, client, db):
        resp = client.get("/api/does-not-exist")
        assert resp.status_code == 404
        assert resp.get_json()["error"]["code"] == "NOT_FOUND"

    def test_405_keeps_allow_header(self, client, db):
        resp = client.get("/api/auth/login")
        assert resp.status_code == 405
        assert resp.get_json()["error"]["code"] == "METHOD_NOT_ALLOWED"
        assert "POST" in resp.headers["Allow"]

    def test_500_is_json_and_hides_details(self, app, client, db, monkeypatch):
        def boom(*_args, **_kwargs):
            raise RuntimeError("secret internals")

        monkeypatch.setattr("app.services.auth.authenticate", boom)
        monkeypatch.setitem(app.config, "PROPAGATE_EXCEPTIONS", False)
        resp = client.post("/api/auth/login", json={"email": "a@b.com", "password": "x"})
        assert resp.status_code == 500
        body = resp.get_json()
        assert body == {
            "error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred", "details": {}}
        }
