"""POST /api/auth/change-password and password-change session revocation."""

from datetime import timedelta

from freezegun import freeze_time
from sqlalchemy import select

from app.models import AuditLog
from app.models.mixins import utcnow
from tests.conftest import bearer
from tests.factories import TEST_PASSWORD, UserFactory
from tests.helpers import auth

NEW_PASSWORD = "Lighthouse#Blue7"


def change(client, token, current=TEST_PASSWORD, new=NEW_PASSWORD):
    return client.post(
        "/api/auth/change-password",
        json={"current_password": current, "new_password": new},
        headers=bearer(token),
    )


def test_change_password_signs_out_other_sessions_and_keeps_this_one(client, db, login):
    user = UserFactory(name="Pat Example")
    with freeze_time(utcnow() - timedelta(minutes=5)):
        laptop = login(user)  # another, older session
    phone = login(user)

    with freeze_time(utcnow() + timedelta(seconds=2)):
        resp = change(client, phone["access_token"])
        assert resp.status_code == 200, resp.get_json()
        fresh = resp.get_json()
        assert set(fresh) >= {"access_token", "refresh_token", "message"}

        # the fresh tokens work
        assert client.get("/api/auth/me", headers=bearer(fresh["access_token"])).status_code == 200
        assert client.post("/api/auth/refresh", headers=bearer(fresh["refresh_token"])).status_code == 200
        # every token issued before the change is revoked, access and refresh alike
        for old in (laptop["access_token"], phone["access_token"]):
            me = client.get("/api/auth/me", headers=bearer(old))
            assert me.status_code == 401 and me.get_json()["error"]["code"] == "TOKEN_REVOKED"
        assert client.post("/api/auth/refresh", headers=bearer(laptop["refresh_token"])).status_code == 401

    # and the new password is the one that works
    assert (
        client.post("/api/auth/login", json={"email": user.email, "password": NEW_PASSWORD}).status_code
        == 200
    )
    old_pw = client.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    assert old_pw.status_code == 401

    row = db.session.scalar(select(AuditLog).where(AuditLog.action == "PASSWORD_CHANGED"))
    assert row.actor_id == user.id and row.new_value == {"by": "self", "other_sessions_revoked": True}


def test_wrong_current_password_is_422_not_401(client, db, login):
    """A 401 would make the frontend think the session expired and sign the user out."""
    user = UserFactory()
    tokens = login(user)
    resp = change(client, tokens["access_token"], current="not-my-password")
    assert resp.status_code == 422
    assert resp.get_json()["error"]["details"] == {
        "current_password": ["Your current password is incorrect."]
    }
    assert db.session.scalar(select(AuditLog).where(AuditLog.action == "PASSWORD_CHANGE_FAILED")) is not None
    assert client.get("/api/auth/me", headers=bearer(tokens["access_token"])).status_code == 200


def test_new_password_must_meet_the_policy(client, db, login):
    user = UserFactory(name="Pat Example")
    token = login(user)["access_token"]
    weak = change(client, token, new="patexample")
    assert weak.status_code == 422
    assert len(weak.get_json()["error"]["details"]["new_password"]) >= 2
    same = change(client, token, new=TEST_PASSWORD)
    assert same.status_code == 422
    assert "new_password" in same.get_json()["error"]["details"]


def test_requires_sign_in_and_both_fields(client, db, login):
    assert client.post("/api/auth/change-password", json={}).status_code == 401
    token = login(UserFactory())["access_token"]
    resp = client.post(
        "/api/auth/change-password", json={"new_password": NEW_PASSWORD}, headers=bearer(token)
    )
    assert resp.status_code == 422
    assert "current_password" in resp.get_json()["error"]["details"]


def test_admin_password_reset_signs_the_user_out(client, org):
    victim_token = auth(org.colleague)
    assert client.get("/api/auth/me", headers=victim_token).status_code == 200
    with freeze_time(utcnow() + timedelta(seconds=2)):
        resp = client.put(
            f"/api/users/{org.colleague.id}", json={"password": NEW_PASSWORD}, headers=auth(org.admin)
        )
        assert resp.status_code == 200
        revoked = client.get("/api/auth/me", headers=victim_token)
        assert revoked.status_code == 401 and revoked.get_json()["error"]["code"] == "TOKEN_REVOKED"
