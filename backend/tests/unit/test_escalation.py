"""Escalation, expiry and reminder jobs. Time is injected (``now=``) or frozen (freezegun)."""

from datetime import timedelta

import pytest
from freezegun import freeze_time
from sqlalchemy import select

from app.errors import NotAuthorizedError
from app.extensions import db as _db
from app.extensions import mail
from app.models import AccessRequest, Approval, ApproverType, AuditLog, Decision, RequestStatus
from app.models.mixins import utcnow
from app.services import escalation, workflow
from tests.factories import AccessRequestFactory
from tests.helpers import make_app

MGR, USR = ApproverType.MANAGER, ApproverType.SPECIFIC_USER
JUSTIFICATION = "Need this for the quarter-end close."


def submit(user, application):
    level = application.access_levels[0]
    req = workflow.submit_request(user, application.id, level.id, JUSTIFICATION)
    return req, req.approvals[0]


def escalation_rows():
    return list(_db.session.scalars(select(AuditLog).where(AuditLog.action == "APPROVAL_ESCALATED")))


class TestEscalation:
    def test_escalates_to_approvers_manager_and_emails_both(self, org):
        req, approval = submit(org.employee, make_app(org.owner, steps=[(MGR, None, 24)]))
        later = utcnow() + timedelta(hours=25)

        with mail.record_messages() as outbox:
            assert escalation.escalate_overdue(now=later) == 1

        _db.session.expire_all()
        approval = _db.session.get(Approval, approval.id)
        assert approval.approver_id == org.admin.id  # the manager's manager
        assert approval.escalated is True
        assert approval.escalated_from_id == org.manager.id
        assert approval.due_at == later + timedelta(hours=24)
        assert approval.decision == Decision.PENDING

        [row] = escalation_rows()
        assert row.actor_id is None  # system
        assert row.old_value["approver_id"] == org.manager.id
        assert row.new_value["approver_id"] == org.admin.id

        assert sorted(m.recipients[0] for m in outbox) == sorted([org.admin.email, org.manager.email])
        assert all(m.subject.startswith("[AccessHub] Escalated:") for m in outbox)
        to_admin = next(m for m in outbox if m.recipients == [org.admin.email])
        assert "escalated to you" in to_admin.body

    def test_only_overdue_and_not_yet_escalated(self, org):
        application = make_app(org.owner, steps=[(MGR, None, 24)])
        _, overdue = submit(org.employee, application)
        _, not_due = submit(org.colleague, application)
        _, already = submit(org.employee, make_app(org.owner, steps=[(MGR, None, 24)]))
        now = utcnow()
        overdue.due_at = now - timedelta(minutes=1)
        not_due.due_at = now + timedelta(minutes=1)
        already.due_at = now - timedelta(hours=1)
        already.escalated = True
        _db.session.commit()

        assert escalation.escalate_overdue(now=now) == 1
        _db.session.expire_all()
        assert _db.session.get(Approval, overdue.id).escalated is True
        assert _db.session.get(Approval, not_due.id).escalated is False
        assert _db.session.get(Approval, already.id).approver_id == org.manager.id  # untouched

    def test_idempotent(self, org):
        submit(org.employee, make_app(org.owner))
        later = utcnow() + timedelta(days=3)
        assert escalation.escalate_overdue(now=later) == 1
        assert escalation.escalate_overdue(now=later) == 0
        assert escalation.escalate_overdue(now=later + timedelta(days=5)) == 0  # escalates once, ever
        assert len(escalation_rows()) == 1

    def test_falls_back_to_admin_when_approver_has_no_manager(self, org):
        _, approval = submit(org.employee, make_app(org.owner, steps=[(USR, org.specialist, 8)]))
        assert escalation.escalate_overdue(now=utcnow() + timedelta(hours=9)) == 1
        _db.session.expire_all()
        assert _db.session.get(Approval, approval.id).approver_id == org.admin.id

    def test_never_escalates_to_the_requester(self, org, db):
        org.specialist.manager = org.employee  # the approver reports to the requester
        db.session.commit()
        _, approval = submit(org.employee, make_app(org.owner, steps=[(USR, org.specialist, 8)]))
        escalation.escalate_overdue(now=utcnow() + timedelta(hours=9))
        _db.session.expire_all()
        assert _db.session.get(Approval, approval.id).approver_id == org.admin.id

    def test_no_target_leaves_approval_alone(self, org, db, caplog):
        # The admin is the overdue approver and has no manager; there is no other admin.
        _, approval = submit(org.specialist, make_app(org.owner, steps=[(MGR, None, 24)]))
        assert approval.approver_id == org.admin.id
        assert escalation.escalate_overdue(now=utcnow() + timedelta(days=2)) == 0
        _db.session.expire_all()
        assert _db.session.get(Approval, approval.id).escalated is False
        assert "No escalation target" in caplog.text

    def test_new_approver_can_decide_old_cannot(self, org):
        req, approval = submit(org.employee, make_app(org.owner))
        escalation.escalate_overdue(now=utcnow() + timedelta(days=2))
        _db.session.expire_all()
        approval = _db.session.get(Approval, approval.id)
        with pytest.raises(NotAuthorizedError):
            workflow.approve(approval, org.manager)
        assert workflow.approve(approval, org.admin).status == RequestStatus.APPROVED

    def test_decided_requests_are_not_escalated(self, org):
        req, approval = submit(org.employee, make_app(org.owner))
        workflow.cancel(req, org.employee)
        assert escalation.escalate_overdue(now=utcnow() + timedelta(days=2)) == 0

    def test_one_failure_does_not_stop_the_rest(self, org, monkeypatch):
        application = make_app(org.owner)
        _, first = submit(org.employee, application)
        _, second = submit(org.colleague, application)
        real = escalation.escalation_target

        def flaky(current, request):
            if request.id == first.request_id:
                raise RuntimeError("boom")
            return real(current, request)

        monkeypatch.setattr(escalation, "escalation_target", flaky)
        assert escalation.escalate_overdue(now=utcnow() + timedelta(days=2)) == 1
        _db.session.expire_all()
        assert _db.session.get(Approval, first.id).escalated is False
        assert _db.session.get(Approval, second.id).escalated is True

    def test_cli_with_frozen_time(self, app, org):
        submit(org.employee, make_app(org.owner))
        with freeze_time(utcnow() + timedelta(hours=30)):
            result = app.test_cli_runner().invoke(args=["escalate"])
        assert result.exit_code == 0, result.output
        assert "Escalated 1 approval(s)." in result.output


def approved_request(org, expires_in: timedelta | None):
    application = make_app(org.owner)
    return AccessRequestFactory(
        requester=org.employee,
        application=application,
        access_level=application.access_levels[0],
        status=RequestStatus.APPROVED,
        duration_days=30,
        expires_at=None if expires_in is None else utcnow() + expires_in,
    )


class TestExpiry:
    def test_expires_past_due_access_and_emails(self, org):
        expired = approved_request(org, timedelta(hours=-1))
        current = approved_request(org, timedelta(days=20))
        forever = approved_request(org, None)

        with mail.record_messages() as outbox:
            assert escalation.expire_access() == 1

        _db.session.expire_all()
        assert _db.session.get(AccessRequest, expired.id).status == RequestStatus.EXPIRED
        assert _db.session.get(AccessRequest, current.id).status == RequestStatus.APPROVED
        assert _db.session.get(AccessRequest, forever.id).status == RequestStatus.APPROVED
        [msg] = outbox
        assert msg.recipients == [org.employee.email] and "has expired" in msg.subject
        row = _db.session.scalar(select(AuditLog).where(AuditLog.action == "REQUEST_EXPIRED"))
        assert row.actor_id is None and row.entity_id == expired.id
        assert escalation.expire_access() == 0  # idempotent

    def test_reminder_once_within_seven_days(self, org):
        soon = approved_request(org, timedelta(days=5, hours=1))
        later = approved_request(org, timedelta(days=10))
        gone = approved_request(org, timedelta(hours=-2))

        with mail.record_messages() as outbox:
            result = escalation.run_daily()
        assert result == {"expired": 1, "reminded": 1}

        reminders = [m for m in outbox if "expires in" in m.subject]
        assert len(reminders) == 1 and "expires in 5 day(s)" in reminders[0].subject
        _db.session.expire_all()
        assert _db.session.get(AccessRequest, soon.id).expiry_reminder_sent_at is not None
        assert _db.session.get(AccessRequest, later.id).expiry_reminder_sent_at is None
        assert _db.session.get(AccessRequest, gone.id).expiry_reminder_sent_at is None

        with mail.record_messages() as outbox:
            assert escalation.run_daily() == {"expired": 0, "reminded": 0}
        assert outbox == []

    def test_frozen_clock_moves_request_through_reminder_then_expiry(self, app, org):
        req = approved_request(org, timedelta(days=30))
        start = utcnow()
        with freeze_time(start + timedelta(days=24)):
            assert escalation.run_daily() == {"expired": 0, "reminded": 1}
        with freeze_time(start + timedelta(days=31)):
            result = app.test_cli_runner().invoke(args=["expire"])
        assert "Expired 1 request(s); sent 0 reminder(s)." in result.output
        _db.session.expire_all()
        assert _db.session.get(AccessRequest, req.id).status == RequestStatus.EXPIRED


class TestScheduler:
    def test_not_started_under_testing(self, app):
        from app.extensions import scheduler

        assert app.testing and not scheduler.running

    def test_registers_jobs_when_enabled(self, app, monkeypatch):
        from apscheduler.schedulers.background import BackgroundScheduler

        import app.scheduler as scheduler_module

        fresh = BackgroundScheduler(timezone="UTC")
        monkeypatch.setattr(scheduler_module, "scheduler", fresh)
        monkeypatch.setitem(app.config, "RUN_SCHEDULER", True)
        monkeypatch.setattr(app, "testing", False)
        try:
            scheduler_module.init_scheduler(app)
            assert fresh.running
            assert {job.id for job in fresh.get_jobs()} == {"escalate_overdue", "expire_and_remind"}
        finally:
            if fresh.running:
                fresh.shutdown(wait=False)

    def test_disabled_flag(self, app, monkeypatch):
        from apscheduler.schedulers.background import BackgroundScheduler

        import app.scheduler as scheduler_module

        fresh = BackgroundScheduler(timezone="UTC")
        monkeypatch.setattr(scheduler_module, "scheduler", fresh)
        monkeypatch.setattr(app, "testing", False)
        monkeypatch.setitem(app.config, "RUN_SCHEDULER", False)
        scheduler_module.init_scheduler(app)
        assert not fresh.running
