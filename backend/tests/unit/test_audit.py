from datetime import UTC, datetime

from app.models import AuditLog, RequestStatus
from app.services.audit import log_action
from tests.factories import UserFactory


def test_outside_request_context_has_no_ip_or_agent(db):
    entry = log_action(None, "SYSTEM_JOB", "approval", 7)
    db.session.commit()
    assert entry.actor_id is None
    assert entry.ip_address is None and entry.user_agent is None
    assert entry.created_at is not None


def test_captures_ip_and_user_agent_in_request(app, db):
    user = UserFactory()
    with app.test_request_context(
        "/", environ_base={"REMOTE_ADDR": "10.1.2.3"}, headers={"User-Agent": "pytest-agent/1.0"}
    ):
        log_action(user, "SOMETHING", "user", user.id)
    db.session.commit()
    entry = db.session.query(AuditLog).one()
    assert entry.actor_id == user.id
    assert entry.ip_address == "10.1.2.3"
    assert entry.user_agent == "pytest-agent/1.0"


def test_values_are_json_serialised(db):
    when = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    entry = log_action(
        None,
        "CHANGE",
        "access_request",
        3,
        old={"status": RequestStatus.PENDING, "at": when},
        new={"status": RequestStatus.APPROVED, "tags": {"b", "a"}},
    )
    db.session.commit()
    db.session.refresh(entry)
    assert entry.old_value == {"status": "PENDING", "at": "2026-01-02T03:04:05+00:00"}
    assert entry.new_value == {"status": "APPROVED", "tags": ["a", "b"]}


def test_actor_can_be_given_as_id(db):
    user = UserFactory()
    entry = log_action(user.id, "X", "user", user.id)
    db.session.commit()
    assert entry.actor_id == user.id


def test_not_committed_by_log_action(db):
    log_action(None, "X", "thing", 1)
    db.session.rollback()
    assert db.session.query(AuditLog).count() == 0
