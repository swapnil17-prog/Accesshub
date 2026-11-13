import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.models import AuditLogImmutableError, Decision, RequestStatus, user_roles
from app.services.audit import log_action
from tests.factories import (
    AccessLevelFactory,
    AccessRequestFactory,
    ApplicationFactory,
    ApprovalFactory,
    UserFactory,
    WorkflowStepFactory,
    get_or_create_role,
)


class TestUser:
    def test_email_is_unique_case_insensitively(self, db):
        UserFactory(email="dup@example.com")
        with pytest.raises(IntegrityError):
            UserFactory(email="DUP@Example.com ")

    def test_email_is_normalised(self, db):
        assert UserFactory(email="  Mixed@Case.COM").email == "mixed@case.com"

    def test_password_hashing(self, db):
        user = UserFactory()
        user.set_password("S3cret!pass")
        assert user.password_hash != "S3cret!pass"
        assert user.check_password("S3cret!pass")
        assert not user.check_password("wrong")

    def test_cannot_be_own_manager(self, db):
        user = UserFactory()
        user.manager_id = user.id
        with pytest.raises(IntegrityError):
            db.session.commit()

    def test_roles_and_has_role(self, db):
        user = UserFactory(roles=["employee", "manager"])
        assert user.role_names == ["employee", "manager"]
        assert user.has_role("manager", "admin")
        assert not user.has_role("admin")

    def test_role_assignment_primary_key(self, db):
        user = UserFactory(roles=[])
        role = get_or_create_role("admin")
        db.session.execute(user_roles.insert().values(user_id=user.id, role_id=role.id))
        with pytest.raises(IntegrityError):
            db.session.execute(user_roles.insert().values(user_id=user.id, role_id=role.id))

    def test_timestamps(self, db):
        user = UserFactory()
        created, updated = user.created_at, user.updated_at
        assert created is not None and created.tzinfo is not None
        user.department = "Finance"
        db.session.commit()
        assert user.updated_at > updated
        assert user.created_at == created


def test_role_name_unique(db):
    get_or_create_role("auditor")
    db.session.commit()
    with pytest.raises(IntegrityError):
        db.session.execute(text("INSERT INTO roles (name) VALUES ('auditor')"))


def test_application_name_unique(db):
    ApplicationFactory(name="Jira")
    with pytest.raises(IntegrityError):
        ApplicationFactory(name="Jira")


def test_access_level_unique_per_application(db):
    app = ApplicationFactory()
    AccessLevelFactory(application=app, name="Viewer")
    AccessLevelFactory(name="Viewer")  # same name on another app is fine
    with pytest.raises(IntegrityError):
        AccessLevelFactory(application=app, name="Viewer")


class TestWorkflowStep:
    def test_step_order_unique_per_application(self, db):
        app = ApplicationFactory()
        WorkflowStepFactory(application=app, step_order=1)
        with pytest.raises(IntegrityError):
            WorkflowStepFactory(application=app, step_order=1)

    @pytest.mark.parametrize("sla", [0, 169])
    def test_sla_hours_range(self, db, sla):
        with pytest.raises(IntegrityError):
            WorkflowStepFactory(sla_hours=sla)

    def test_step_order_positive(self, db):
        with pytest.raises(IntegrityError):
            WorkflowStepFactory(step_order=0)

    def test_specific_user_requires_approver(self, db):
        with pytest.raises(IntegrityError):
            WorkflowStepFactory(approver_type="SPECIFIC_USER", approver_user=None)

    def test_specific_user_with_approver_ok(self, db):
        step = WorkflowStepFactory(approver_type="SPECIFIC_USER", approver_user=UserFactory())
        assert step.id is not None

    def test_steps_ordered_on_application(self, db):
        app = ApplicationFactory()
        WorkflowStepFactory(application=app, step_order=2)
        WorkflowStepFactory(application=app, step_order=1)
        db.session.expire(app)
        assert [s.step_order for s in app.workflow_steps] == [1, 2]


class TestAccessRequest:
    def test_defaults(self, db):
        req = AccessRequestFactory()
        assert req.status == RequestStatus.PENDING
        assert req.current_step == 1
        assert req.expires_at is None

    def test_only_one_pending_per_user_app_level(self, db):
        first = AccessRequestFactory()
        with pytest.raises(IntegrityError):
            AccessRequestFactory(
                requester=first.requester, application=first.application, access_level=first.access_level
            )

    def test_new_pending_allowed_after_previous_closed(self, db):
        first = AccessRequestFactory(status=RequestStatus.REJECTED)
        second = AccessRequestFactory(
            requester=first.requester, application=first.application, access_level=first.access_level
        )
        assert second.status == RequestStatus.PENDING

    def test_duration_days_positive(self, db):
        with pytest.raises(IntegrityError):
            AccessRequestFactory(duration_days=0)


class TestApproval:
    def test_defaults(self, db):
        approval = ApprovalFactory()
        assert approval.decision == Decision.PENDING
        assert approval.escalated is False
        assert approval.decided_at is None

    def test_only_one_pending_approval_per_request(self, db):
        first = ApprovalFactory()
        ApprovalFactory(request=first.request, step_order=2, decision=Decision.SKIPPED)
        with pytest.raises(IntegrityError):
            ApprovalFactory(request=first.request, step_order=2)

    def test_request_approvals_ordered_by_step(self, db):
        req = AccessRequestFactory()
        ApprovalFactory(request=req, step_order=2)
        ApprovalFactory(request=req, step_order=1, decision=Decision.APPROVED)
        db.session.expire(req)
        assert [a.step_order for a in req.approvals] == [1, 2]


class TestAuditLogAppendOnly:
    def _entry(self, db):
        entry = log_action(None, "TEST", "thing", 1, new={"a": 1})
        db.session.commit()
        return entry

    def test_orm_update_blocked(self, db):
        entry = self._entry(db)
        entry.action = "TAMPERED"
        with pytest.raises(AuditLogImmutableError):
            db.session.commit()

    def test_orm_delete_blocked(self, db):
        entry = self._entry(db)
        db.session.delete(entry)
        with pytest.raises(AuditLogImmutableError):
            db.session.commit()

    @pytest.mark.parametrize("sql", ["UPDATE audit_logs SET action = 'TAMPERED'", "DELETE FROM audit_logs"])
    def test_raw_sql_blocked_by_trigger(self, db, sql):
        self._entry(db)
        with pytest.raises(DBAPIError, match="append-only"):
            db.session.execute(text(sql))
