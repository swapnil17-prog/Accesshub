"""Workflow engine unit tests (service layer, real Postgres)."""

import threading
from datetime import timedelta

import pytest
from sqlalchemy import func, select, text

from app.errors import (
    DuplicateRequestError,
    InvalidInputError,
    InvalidStateError,
    NotAuthorizedError,
    NotFoundError,
)
from app.models import (
    AccessRequest,
    Approval,
    ApproverType,
    AuditLog,
    Decision,
    RequestStatus,
    User,
    WorkflowStep,
)
from app.models.mixins import utcnow
from app.services import notifications, workflow
from tests.helpers import actions, make_app

MGR, OWN, USR = ApproverType.MANAGER, ApproverType.APP_OWNER, ApproverType.SPECIFIC_USER
JUSTIFICATION = "I need this to do my job on the new project."


def submit(user, application, level_index=0, duration_days=None):
    level = application.access_levels[level_index]
    return workflow.submit_request(user, application.id, level.id, JUSTIFICATION, duration_days)


def open_approval(request) -> Approval:
    return next(a for a in request.approvals if a.decision == Decision.PENDING)


@pytest.fixture()
def sent(monkeypatch):
    """Records notifications instead of sending them."""
    calls: list[tuple[str, int, list[str]]] = []
    monkeypatch.setattr(
        notifications,
        "notify",
        lambda event, req, users: calls.append((event, req.id, [u.email for u in users])),
    )
    return calls


class TestSubmit:
    def test_creates_request_at_step_one_with_first_approval(self, org, sent):
        application = make_app(org.owner, steps=[(MGR, None, 24)])
        before = utcnow()
        req = submit(org.employee, application)

        assert req.status == RequestStatus.PENDING
        assert req.current_step == 1
        assert len(req.workflow_snapshot) == 1
        [approval] = req.approvals
        assert approval.approver_id == org.manager.id
        assert approval.decision == Decision.PENDING
        assert before + timedelta(hours=24) <= approval.due_at <= utcnow() + timedelta(hours=24)
        assert actions() == ["REQUEST_CREATED", "APPROVAL_ASSIGNED"]
        assert sent == [("approval_needed", req.id, [org.manager.email])]

    def test_duplicate_pending_request_rejected(self, org):
        application = make_app(org.owner)
        submit(org.employee, application)
        with pytest.raises(DuplicateRequestError):
            submit(org.employee, application)
        submit(org.employee, application, level_index=1)  # other level is fine
        submit(org.colleague, application)  # other user is fine

    def test_new_request_allowed_once_previous_is_closed(self, org):
        application = make_app(org.owner)
        first = submit(org.employee, application)
        workflow.cancel(first, org.employee)
        assert submit(org.employee, application).status == RequestStatus.PENDING

    def test_inactive_application(self, org):
        application = make_app(org.owner, is_active=False)
        with pytest.raises(NotFoundError):
            submit(org.employee, application)

    def test_level_must_belong_to_application(self, org):
        app_a, app_b = make_app(org.owner), make_app(org.owner)
        with pytest.raises(InvalidInputError):
            workflow.submit_request(org.employee, app_a.id, app_b.access_levels[0].id, JUSTIFICATION)

    def test_application_without_workflow(self, org):
        application = make_app(org.owner, steps=[])
        with pytest.raises(InvalidStateError) as exc:
            submit(org.employee, application)
        assert exc.value.code == "NO_WORKFLOW"

    def test_no_eligible_approver_creates_nothing(self, org, db):
        # Specialist has no manager; owner is the specialist; remove every admin.
        application = make_app(org.specialist, steps=[(OWN, None, 24)])
        org.admin.is_active = False
        db.session.commit()
        with pytest.raises(InvalidStateError) as exc:
            submit(org.specialist, application)
        assert exc.value.code == "NO_ELIGIBLE_APPROVER"
        assert db.session.scalar(select(func.count(AccessRequest.id))) == 0
        assert actions() == []


class TestResolveApprover:
    def test_manager(self, org):
        req = submit(org.employee, make_app(org.owner, steps=[(MGR, None, 24)]))
        assert open_approval(req).approver_id == org.manager.id

    def test_app_owner(self, org):
        req = submit(org.employee, make_app(org.owner, steps=[(OWN, None, 24)]))
        assert open_approval(req).approver_id == org.owner.id

    def test_specific_user(self, org):
        req = submit(org.employee, make_app(org.owner, steps=[(USR, org.specialist, 24)]))
        assert open_approval(req).approver_id == org.specialist.id

    def test_manager_falls_back_to_admin_when_requester_has_no_manager(self, org):
        req = submit(org.specialist, make_app(org.owner, steps=[(MGR, None, 24)]))
        assert open_approval(req).approver_id == org.admin.id

    def test_inactive_manager_falls_back_to_admin(self, org, db):
        org.manager.is_active = False
        db.session.commit()
        req = submit(org.employee, make_app(org.owner, steps=[(MGR, None, 24)]))
        assert open_approval(req).approver_id == org.admin.id

    def test_self_approval_specific_user_falls_back_to_manager(self, org):
        req = submit(org.employee, make_app(org.owner, steps=[(USR, org.employee, 24)]))
        assert open_approval(req).approver_id == org.manager.id

    def test_self_approval_app_owner_falls_back_to_manager(self, org):
        req = submit(org.owner, make_app(org.owner, steps=[(OWN, None, 24)]))
        assert open_approval(req).approver_id == org.admin.id  # owner's manager is the admin

    def test_self_approval_without_manager_falls_back_to_admin(self, org):
        req = submit(org.specialist, make_app(org.specialist, steps=[(OWN, None, 24)]))
        assert open_approval(req).approver_id == org.admin.id

    def test_admin_requester_never_approves_themself(self, org, db):
        second_admin = User(name="Bo Admin", email="bo@example.com", password_hash="x")
        second_admin.roles.extend(org.admin.roles)
        db.session.add(second_admin)
        db.session.commit()
        req = submit(org.admin, make_app(org.owner, steps=[(MGR, None, 24)]))
        assert open_approval(req).approver_id == second_admin.id


class TestApprove:
    def test_one_step_workflow_end_to_end(self, org, sent):
        req = submit(org.employee, make_app(org.owner), duration_days=30)
        approval = open_approval(req)

        result = workflow.approve(approval, org.manager, "  Looks good  ")
        assert result.status == RequestStatus.APPROVED
        assert approval.decision == Decision.APPROVED
        assert approval.comment == "Looks good"
        assert approval.decided_at is not None
        assert result.expires_at == approval.decided_at + timedelta(days=30)
        assert sent[-1] == ("request_approved", req.id, [org.employee.email])

    def test_no_expiry_without_duration(self, org):
        req = submit(org.employee, make_app(org.owner))
        assert workflow.approve(open_approval(req), org.manager).expires_at is None

    def test_three_step_workflow_end_to_end(self, org, sent):
        application = make_app(org.owner, steps=[(MGR, None, 24), (OWN, None, 48), (USR, org.specialist, 8)])
        req = submit(org.employee, application)

        workflow.approve(open_approval(req), org.manager)
        assert req.current_step == 2 and req.status == RequestStatus.PENDING
        second = open_approval(req)
        assert second.approver_id == org.owner.id and second.step_order == 2

        workflow.approve(second, org.owner)
        third = open_approval(req)
        assert req.current_step == 3 and third.approver_id == org.specialist.id

        workflow.approve(third, org.specialist, "ok")
        assert req.status == RequestStatus.APPROVED
        assert [(a.step_order, a.decision) for a in req.approvals] == [
            (1, Decision.APPROVED),
            (2, Decision.APPROVED),
            (3, Decision.APPROVED),
        ]
        assert [e for e, *_ in sent] == ["approval_needed"] * 3 + ["request_approved"]
        assert actions("access_request", req.id) == [
            "REQUEST_CREATED",
            "REQUEST_ADVANCED",
            "REQUEST_ADVANCED",
            "REQUEST_APPROVED",
        ]
        assert actions("approval") == ["APPROVAL_ASSIGNED", "APPROVAL_APPROVED"] * 3

    def test_audit_rows_record_actor_and_values(self, org, db):
        req = submit(org.employee, make_app(org.owner))
        approval = open_approval(req)
        workflow.approve(approval, org.manager, "fine")
        row = db.session.scalar(select(AuditLog).where(AuditLog.action == "APPROVAL_APPROVED"))
        assert row.actor_id == org.manager.id
        assert row.entity_id == approval.id
        assert row.old_value == {"decision": "PENDING"}
        assert row.new_value == {"decision": "APPROVED", "comment": "fine"}

    def test_non_assigned_user_cannot_approve(self, org):
        req = submit(org.employee, make_app(org.owner))
        approval = open_approval(req)
        for intruder in (org.colleague, org.owner, org.admin, org.employee):
            with pytest.raises(NotAuthorizedError):
                workflow.approve(approval, intruder)
        assert approval.decision == Decision.PENDING

    def test_already_decided_approval_cannot_be_approved_again(self, org):
        req = submit(org.employee, make_app(org.owner, steps=[(MGR, None, 24), (OWN, None, 24)]))
        first = open_approval(req)
        workflow.approve(first, org.manager)
        with pytest.raises(InvalidStateError):
            workflow.approve(first, org.manager)
        with pytest.raises(InvalidStateError):
            workflow.reject(first, org.manager, "changed my mind")

    def test_cannot_approve_after_cancel(self, org):
        req = submit(org.employee, make_app(org.owner))
        approval = open_approval(req)
        workflow.cancel(req, org.employee)
        with pytest.raises(InvalidStateError):
            workflow.approve(approval, org.manager)

    def test_failure_rolls_back_everything(self, org, db):
        """If advancing to step 2 fails, the step-1 approval and its audit rows roll back too."""
        application = make_app(org.owner, steps=[(MGR, None, 24), (USR, org.colleague, 24)])
        req = submit(org.employee, application)
        approval = open_approval(req)
        audit_before = actions()

        # Make step 2 unresolvable: its user, the requester's manager link and every admin gone.
        org.colleague.is_active = False
        org.employee.manager = None
        org.admin.is_active = False
        db.session.commit()

        with pytest.raises(InvalidStateError) as exc:
            workflow.approve(approval, org.manager)
        assert exc.value.code == "NO_ELIGIBLE_APPROVER"

        db.session.expire_all()
        assert db.session.get(Approval, approval.id).decision == Decision.PENDING
        assert db.session.get(AccessRequest, req.id).current_step == 1
        assert actions() == audit_before

    def test_workflow_edit_does_not_affect_in_flight_request(self, org, db):
        application = make_app(org.owner, steps=[(MGR, None, 24)])
        req = submit(org.employee, application)
        db.session.add(WorkflowStep(application=application, step_order=2, approver_type=OWN, sla_hours=24))
        db.session.commit()

        workflow.approve(open_approval(req), org.manager)
        assert req.status == RequestStatus.APPROVED  # still the 1-step chain it was submitted with
        assert len(req.approvals) == 1

    def test_notification_failure_does_not_undo_decision(self, org, monkeypatch, db):
        req = submit(org.employee, make_app(org.owner))

        def broken(*_args):
            raise RuntimeError("SMTP down")

        monkeypatch.setattr(notifications, "notify", broken)
        workflow.approve(open_approval(req), org.manager)
        db.session.expire_all()
        assert db.session.get(AccessRequest, req.id).status == RequestStatus.APPROVED


class TestReject:
    def test_reject_mid_chain_stops_it(self, org, sent):
        application = make_app(org.owner, steps=[(MGR, None, 24), (OWN, None, 24), (USR, org.specialist, 24)])
        req = submit(org.employee, application)
        workflow.approve(open_approval(req), org.manager)

        result = workflow.reject(open_approval(req), org.owner, "Not needed for your role")
        assert result.status == RequestStatus.REJECTED
        assert [(a.step_order, a.decision) for a in req.approvals] == [
            (1, Decision.APPROVED),
            (2, Decision.REJECTED),
        ]  # step 3 never created
        assert req.approvals[1].comment == "Not needed for your role"
        assert sent[-1] == ("request_rejected", req.id, [org.employee.email])
        assert actions("access_request", req.id)[-1] == "REQUEST_REJECTED"

    @pytest.mark.parametrize("comment", [None, "", "   "])
    def test_comment_required(self, org, comment):
        req = submit(org.employee, make_app(org.owner))
        approval = open_approval(req)
        with pytest.raises(InvalidInputError):
            workflow.reject(approval, org.manager, comment)
        assert approval.decision == Decision.PENDING

    def test_non_assigned_user_cannot_reject(self, org):
        req = submit(org.employee, make_app(org.owner))
        with pytest.raises(NotAuthorizedError):
            workflow.reject(open_approval(req), org.colleague, "no")


class TestCancel:
    def test_cancel_skips_pending_approvals(self, org):
        application = make_app(org.owner, steps=[(MGR, None, 24), (OWN, None, 24)])
        req = submit(org.employee, application)
        workflow.approve(open_approval(req), org.manager)

        result = workflow.cancel(req, org.employee)
        assert result.status == RequestStatus.CANCELLED
        assert [(a.step_order, a.decision) for a in req.approvals] == [
            (1, Decision.APPROVED),
            (2, Decision.SKIPPED),
        ]
        assert actions("approval")[-1] == "APPROVAL_SKIPPED"
        assert actions("access_request", req.id)[-1] == "REQUEST_CANCELLED"

    def test_only_requester_can_cancel(self, org):
        req = submit(org.employee, make_app(org.owner))
        for other in (org.manager, org.admin, org.colleague):
            with pytest.raises(NotAuthorizedError):
                workflow.cancel(req, other)
        assert req.status == RequestStatus.PENDING

    @pytest.mark.parametrize("final", ["approve", "reject", "cancel"])
    def test_only_pending_requests_can_be_cancelled(self, org, final):
        req = submit(org.employee, make_app(org.owner))
        if final == "approve":
            workflow.approve(open_approval(req), org.manager)
        elif final == "reject":
            workflow.reject(open_approval(req), org.manager, "no")
        else:
            workflow.cancel(req, org.employee)
        with pytest.raises(InvalidStateError):
            workflow.cancel(req, org.employee)


def test_concurrent_decisions_are_serialised_by_row_lock(app, db, org):
    """approve() waits on SELECT ... FOR UPDATE while another transaction holds the request
    row, then re-reads and sees that the approval was already decided."""
    req = submit(org.employee, make_app(org.owner))
    approval_id, request_id, manager_id = open_approval(req).id, req.id, org.manager.id
    outcome: dict[str, str] = {}

    def approve_in_other_session() -> None:
        with app.app_context():
            try:
                user = db.session.get(User, manager_id)
                workflow.approve(workflow.get_approval(approval_id), user, "second")
                outcome["result"] = "approved"
            except InvalidStateError:
                outcome["result"] = "invalid_state"
            finally:
                db.session.remove()

    with db.engine.connect() as other:
        tx = other.begin()
        other.execute(text("SELECT id FROM access_requests WHERE id = :id FOR UPDATE"), {"id": request_id})
        worker = threading.Thread(target=approve_in_other_session)
        worker.start()
        worker.join(timeout=2)
        assert worker.is_alive(), "approve() should be blocked on the request row lock"

        # The lock holder decides first ...
        other.execute(
            text("UPDATE approvals SET decision = 'APPROVED', decided_at = now() WHERE id = :id"),
            {"id": approval_id},
        )
        other.execute(
            text("UPDATE access_requests SET status = 'APPROVED' WHERE id = :id"), {"id": request_id}
        )
        tx.commit()

    worker.join(timeout=15)
    assert not worker.is_alive()
    assert outcome["result"] == "invalid_state"  # ... so the waiting approver loses cleanly
