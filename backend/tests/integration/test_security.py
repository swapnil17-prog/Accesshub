"""Sign-in brute-force protection, password policy and production secret checks."""

from datetime import timedelta

import pytest
from freezegun import freeze_time
from sqlalchemy import select

from app import create_app
from app.config import TestingConfig
from app.extensions import limiter
from app.models import AuditLog
from app.models.mixins import utcnow
from app.services.passwords import password_problems
from tests.factories import TEST_PASSWORD, UserFactory
from tests.helpers import auth


def login(client, email, password, ip="127.0.0.1"):
    return client.post(
        "/api/auth/login", json={"email": email, "password": password}, environ_base={"REMOTE_ADDR": ip}
    )


@pytest.fixture()
def limited_client(db, monkeypatch):
    """A separate app with rate limiting ON and a tiny login limit.

    Flask-Limiter's init_app does nothing when disabled (the testing default), so limiting is
    exercised on its own app; the shared limiter is switched back off afterwards.
    """
    monkeypatch.setattr(TestingConfig, "RATELIMIT_ENABLED", True)
    monkeypatch.setattr(TestingConfig, "LOGIN_RATE_LIMIT", "3 per minute", raising=False)
    was_enabled = limiter.enabled
    limited_app = create_app("testing")
    limiter.reset()
    yield limited_app.test_client()
    limiter.reset()
    limiter.enabled = was_enabled


class TestRateLimit:
    def test_login_is_rate_limited_per_ip(self, limited_client):
        client = limited_client
        codes = [login(client, "ghost@example.com", "nope").status_code for _ in range(4)]
        assert codes == [401, 401, 401, 429]
        blocked = login(client, "ghost@example.com", "nope")
        body = blocked.get_json()["error"]
        assert body["code"] == "TOO_MANY_REQUESTS"
        assert body["details"]["limit"] == "3 per 1 minute"
        assert int(blocked.headers["Retry-After"]) > 0
        # another client address is unaffected
        assert login(client, "ghost@example.com", "nope", ip="10.9.8.7").status_code == 401

    def test_refresh_has_its_own_limit(self, limited_client):
        client = limited_client
        user = UserFactory()
        tokens = login(client, user.email, TEST_PASSWORD, ip="10.0.0.5").get_json()
        headers = {"Authorization": f"Bearer {tokens['refresh_token']}"}
        codes = [
            client.post(
                "/api/auth/refresh", headers=headers, environ_base={"REMOTE_ADDR": "10.0.0.5"}
            ).status_code
            for _ in range(4)
        ]
        assert codes == [200, 200, 200, 429]  # counted separately from login attempts


class TestAccountLockout:
    def test_locks_after_repeated_failures_even_with_the_right_password(self, client, db):
        user = UserFactory()
        for _ in range(5):
            assert login(client, user.email, "wrong-password").status_code == 401
        locked = login(client, user.email, TEST_PASSWORD)
        assert locked.status_code == 429
        assert locked.get_json()["error"]["code"] == "TOO_MANY_ATTEMPTS"
        reasons = [r.new_value["reason"] for r in db.session.scalars(select(AuditLog).order_by(AuditLog.id))]
        assert reasons == ["bad_password"] * 5 + ["locked_out"]

    def test_lock_expires_after_the_window(self, client, db):
        user = UserFactory()
        for _ in range(5):
            login(client, user.email, "wrong-password")
        with freeze_time(utcnow() + timedelta(minutes=16)):
            assert login(client, user.email, TEST_PASSWORD).status_code == 200

    def test_locked_out_attempts_do_not_extend_the_lock(self, client, db):
        user = UserFactory()
        for _ in range(5):
            login(client, user.email, "wrong-password")
        start = utcnow()
        with freeze_time(start + timedelta(minutes=10)):
            assert login(client, user.email, TEST_PASSWORD).status_code == 429
        with freeze_time(start + timedelta(minutes=16)):
            assert login(client, user.email, TEST_PASSWORD).status_code == 200

    def test_success_resets_the_count(self, client, db):
        user = UserFactory()
        for _ in range(4):
            login(client, user.email, "wrong-password")
        assert login(client, user.email, TEST_PASSWORD).status_code == 200
        for _ in range(4):
            login(client, user.email, "wrong-password")
        assert login(client, user.email, TEST_PASSWORD).status_code == 200

    def test_unknown_emails_lock_the_same_way(self, client, db):
        for _ in range(5):
            assert login(client, "nobody@example.com", "x").status_code == 401
        assert login(client, "nobody@example.com", "x").status_code == 429

    def test_accounts_lock_independently(self, client, db):
        victim, bystander = UserFactory(), UserFactory()
        for _ in range(5):
            login(client, victim.email, "wrong-password")
        assert login(client, bystander.email, TEST_PASSWORD).status_code == 200


class TestPasswordPolicy:
    @pytest.mark.parametrize(
        "password, expected",
        [
            ("Short1!", "at least 10"),
            ("alllowercaseletters", "three of"),
            ("Password@123", "too common"),
            ("Nina-2026-Secure", "name or email"),
            ("x" * 120 + "Aa1!aaaaaa", "at most 128"),
        ],
    )
    def test_rejects(self, password, expected):
        problems = password_problems(password, email="nina@example.com", name="Nina New")
        assert any(expected in p for p in problems), problems

    @pytest.mark.parametrize("password", ["Correct-Horse-42", "Lighthouse#Blue7", "tide pool ROCKS 9"])
    def test_accepts(self, password):
        assert password_problems(password, email="nina@example.com", name="Nina New") == []

    def test_api_returns_every_problem(self, client, org):
        body = {"name": "Nina New", "email": "nina@example.com", "password": "nina"}
        resp = client.post("/api/users", json=body, headers=auth(org.admin))
        assert resp.status_code == 422
        problems = resp.get_json()["error"]["details"]["password"]
        assert len(problems) == 3  # too short, too little variety, contains the name

    def test_admin_password_reset_is_checked_too(self, client, org):
        resp = client.put(
            f"/api/users/{org.colleague.id}", json={"password": "password123"}, headers=auth(org.admin)
        )
        assert resp.status_code == 422


class TestProductionSecrets:
    @pytest.mark.parametrize(
        "secret",
        ["short", "change-me-long-random-xxxxxxxxxxxxxxxxxxxxx", "dev-only-secret-key-change-me-0123456789"],
    )
    def test_weak_secrets_are_refused(self, monkeypatch, secret):
        monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@db/x")
        monkeypatch.setenv("SECRET_KEY", secret)
        monkeypatch.setenv("JWT_SECRET_KEY", "a" * 48)
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            create_app("production")
