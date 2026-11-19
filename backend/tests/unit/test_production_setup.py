"""Production wiring: proxy headers, the scheduler process command."""

from apscheduler.schedulers.background import BackgroundScheduler

import app.scheduler as scheduler_module
from app import create_app
from app.config import TestingConfig
from app.models import AuditLog
from tests.factories import TEST_PASSWORD, UserFactory


def _login(client, user, **kwargs):
    return client.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD}, **kwargs)


def test_forwarded_for_is_ignored_without_proxy_fix(client, db):
    user = UserFactory()
    _login(client, user, headers={"X-Forwarded-For": "6.6.6.6"}, environ_base={"REMOTE_ADDR": "10.0.0.2"})
    assert db.session.query(AuditLog).one().ip_address == "10.0.0.2"  # spoofed header not trusted


def test_proxy_fix_records_real_client_ip(db, monkeypatch):
    monkeypatch.setattr(TestingConfig, "PROXY_FIX_HOPS", 1)
    proxied_app = create_app("testing")
    user = UserFactory()
    resp = _login(
        proxied_app.test_client(),
        user,
        headers={"X-Forwarded-For": "203.0.113.7"},
        environ_base={"REMOTE_ADDR": "172.18.0.5"},  # the nginx container
    )
    assert resp.status_code == 200
    db.session.expire_all()
    assert db.session.query(AuditLog).one().ip_address == "203.0.113.7"


def test_run_scheduler_requires_flag(app):
    result = app.test_cli_runner().invoke(args=["run-scheduler"])
    assert result.exit_code != 0
    assert "RUN_SCHEDULER=1" in result.output


def test_run_scheduler_starts_jobs_and_stops_cleanly(app, monkeypatch):
    fresh = BackgroundScheduler(timezone="UTC")
    monkeypatch.setattr(scheduler_module, "scheduler", fresh)
    monkeypatch.setitem(app.config, "RUN_SCHEDULER", True)
    monkeypatch.setattr(app, "testing", False)
    monkeypatch.setattr("threading.Event.wait", lambda self, timeout=None: True)  # "SIGTERM" at once

    result = app.test_cli_runner().invoke(args=["run-scheduler"])

    assert result.exit_code == 0, result.output
    assert "escalate_overdue" in result.output and "expire_and_remind" in result.output
    assert "Scheduler stopped." in result.output
    assert not fresh.running
