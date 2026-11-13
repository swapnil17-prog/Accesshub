"""Workflow engine: every state change of an access request goes through this module.

Rules (see CLAUDE.md "Workflow engine rules"):

* A request walks an ordered chain of approval steps. Only the *current* step has an
  approval row; the next one is created when the current one is approved. Rejecting stops
  the chain (later approvals are never created); cancelling SKIPs the open approval.
* The chain is the application's workflow **as it was at submission** (``workflow_snapshot``),
  so editing a workflow never changes requests that are already in flight.
* Each public function is one database transaction: the business change and its audit rows
  commit together or not at all. Approve/reject/cancel first take ``SELECT ... FOR UPDATE``
  on the request row, so two approvers (or an approve racing a cancel) are serialised and the
  loser sees the already-decided state and gets InvalidStateError.
* Notifications are sent only after the commit succeeds, and a failing notification never
  undoes the business change.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol

from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError

from ..errors import (
    DuplicateRequestError,
    InvalidInputError,
    InvalidStateError,
    NotAuthorizedError,
    NotFoundError,
)
from ..extensions import db
from ..models import (
    AccessRequest,
    AppAccessLevel,
    Application,
    Approval,
    ApproverType,
    AuditAction,
    Decision,
    RequestStatus,
    Role,
    RoleName,
    User,
)
from ..models.mixins import utcnow
from . import audit, notifications

logger = logging.getLogger(__name__)

ENTITY_REQUEST = "access_request"
ENTITY_APPROVAL = "approval"


# --------------------------------------------------------------------------- steps


class StepLike(Protocol):
    step_order: int
    approver_type: ApproverType
    approver_user_id: int | None
    sla_hours: int


@dataclass(frozen=True)
class StepSpec:
    """One step of a request's (snapshotted) approval chain."""

    step_order: int
    approver_type: ApproverType
    approver_user_id: int | None
    sla_hours: int

    @classmethod
    def from_step(cls, step: StepLike) -> StepSpec:
        return cls(step.step_order, ApproverType(step.approver_type), step.approver_user_id, step.sla_hours)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StepSpec:
        return cls(
            int(data["step_order"]),
            ApproverType(data["approver_type"]),
            data.get("approver_user_id"),
            int(data["sla_hours"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_order": self.step_order,
            "approver_type": self.approver_type.value,
            "approver_user_id": self.approver_user_id,
            "sla_hours": self.sla_hours,
        }


def snapshot_workflow(application: Application) -> list[dict[str, Any]]:
    """The application's current workflow as plain JSON, ordered by step_order."""
    return [
        StepSpec.from_step(s).to_dict()
        for s in sorted(application.workflow_steps, key=lambda s: s.step_order)
    ]


def request_steps(request: AccessRequest) -> list[StepSpec]:
    """The approval chain this request follows (from its submission-time snapshot)."""
    return sorted((StepSpec.from_dict(d) for d in request.workflow_snapshot), key=lambda s: s.step_order)


# --------------------------------------------------------------------------- approver resolution


def _any_admin(exclude_user_id: int | None) -> User | None:
    stmt = (
        select(User)
        .join(User.roles)
        .where(Role.name == RoleName.ADMIN.value, User.is_active.is_(True))
        .order_by(User.id)
        .limit(1)
    )
    if exclude_user_id is not None:
        stmt = stmt.where(User.id != exclude_user_id)
    return db.session.scalar(stmt)


def resolve_approver(step: StepLike, request: AccessRequest) -> User:
    """Who must decide ``step`` of ``request``.

    * MANAGER       -> the requester's manager
    * APP_OWNER     -> the application's owner
    * SPECIFIC_USER -> ``step.approver_user_id``

    If that person is missing, inactive, or is the requester (no self-approval), fall back
    to the requester's manager, then to an active admin who is not the requester.
    Raises InvalidStateError if nobody is eligible.
    """
    requester = request.requester
    if step.approver_type == ApproverType.MANAGER:
        primary = requester.manager
    elif step.approver_type == ApproverType.APP_OWNER:
        primary = request.application.owner
    else:
        primary = db.session.get(User, step.approver_user_id) if step.approver_user_id else None

    for candidate in (primary, requester.manager):
        if candidate is not None and candidate.is_active and candidate.id != requester.id:
            return candidate

    admin = _any_admin(exclude_user_id=requester.id)
    if admin is None:
        raise InvalidStateError(
            "No eligible approver could be found for this step",
            code="NO_ELIGIBLE_APPROVER",
            details={"step_order": step.step_order},
        )
    return admin


# --------------------------------------------------------------------------- helpers


@contextmanager
def _transaction() -> Iterator[None]:
    """Commit on success, roll back everything (business rows and audit rows) on error."""
    try:
        yield
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise


Notification = tuple[str, AccessRequest, list[User]]


def _dispatch(pending: list[Notification]) -> None:
    """Send notifications after commit. Failures are logged, never raised."""
    for event, request, recipients in pending:
        try:
            notifications.notify(event, request, recipients)
        except Exception:
            logger.exception("Notification %s for request %s failed", event, request.id)


def _lock_request(request_id: int) -> AccessRequest:
    """SELECT ... FOR UPDATE the request row and refresh it from the database."""
    request = db.session.scalar(
        select(AccessRequest)
        .where(AccessRequest.id == request_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if request is None:
        raise NotFoundError("Access request not found")
    return request


def _open_approval(request: AccessRequest, step: StepSpec, actor: User | None, now: datetime) -> Approval:
    """Create the approval for ``step`` and audit the assignment."""
    approver = resolve_approver(step, request)
    approval = Approval(
        request=request,
        step_order=step.step_order,
        approver=approver,
        due_at=now + timedelta(hours=step.sla_hours),
    )
    db.session.add(approval)
    db.session.flush()
    audit.log_action(
        actor,
        AuditAction.APPROVAL_ASSIGNED,
        ENTITY_APPROVAL,
        approval.id,
        new={
            "request_id": request.id,
            "step_order": step.step_order,
            "approver_id": approver.id,
            "due_at": approval.due_at,
        },
    )
    return approval


def _locked_pending_approval(approval: Approval, user: User) -> tuple[Approval, AccessRequest]:
    """Lock the approval's request, re-read the approval and check ``user`` may decide it."""
    request = _lock_request(approval.request_id)
    db.session.refresh(approval)

    if approval.approver_id != user.id:
        raise NotAuthorizedError("Only the assigned approver can decide this approval")
    if approval.approver_id == request.requester_id:
        raise NotAuthorizedError("You cannot approve your own request")
    if approval.decision != Decision.PENDING or request.status != RequestStatus.PENDING:
        raise InvalidStateError(
            "This approval has already been decided",
            details={"decision": approval.decision.value, "request_status": request.status.value},
        )
    return approval, request


def _clean_comment(comment: str | None) -> str | None:
    comment = (comment or "").strip()
    return comment or None


# --------------------------------------------------------------------------- public API


def get_approval(approval_id: int) -> Approval:
    approval = db.session.get(Approval, approval_id)
    if approval is None:
        raise NotFoundError("Approval not found")
    return approval


def submit_request(
    user: User,
    app_id: int,
    level_id: int,
    justification: str,
    duration_days: int | None = None,
) -> AccessRequest:
    """Create a PENDING request at step 1 and assign the step-1 approver.

    Raises NotFoundError (unknown/inactive app), InvalidInputError (level not on this app),
    InvalidStateError (app has no workflow) or DuplicateRequestError (already pending).
    """
    application = db.session.get(Application, app_id)
    if application is None or not application.is_active:
        raise NotFoundError("Application not found")
    level = db.session.get(AppAccessLevel, level_id)
    if level is None or level.application_id != application.id:
        raise InvalidInputError(details={"access_level_id": ["Not an access level of this application."]})
    snapshot = snapshot_workflow(application)
    if not snapshot:
        raise InvalidStateError("This application has no approval workflow configured", code="NO_WORKFLOW")

    already_pending = db.session.scalar(
        select(
            exists().where(
                AccessRequest.requester_id == user.id,
                AccessRequest.application_id == application.id,
                AccessRequest.access_level_id == level.id,
                AccessRequest.status == RequestStatus.PENDING,
            )
        )
    )
    if already_pending:
        raise DuplicateRequestError()

    now = utcnow()
    with _transaction():
        request = AccessRequest(
            requester=user,
            application=application,
            access_level=level,
            justification=justification.strip(),
            duration_days=duration_days,
            current_step=1,
            status=RequestStatus.PENDING,
            workflow_snapshot=snapshot,
        )
        db.session.add(request)
        try:
            db.session.flush()
        except IntegrityError as exc:  # lost a race with a concurrent identical submit
            raise DuplicateRequestError() from exc
        audit.log_action(
            user,
            AuditAction.REQUEST_CREATED,
            ENTITY_REQUEST,
            request.id,
            new={
                "application_id": application.id,
                "access_level_id": level.id,
                "duration_days": duration_days,
                "status": RequestStatus.PENDING,
                "steps": len(snapshot),
            },
        )
        first = _open_approval(request, StepSpec.from_dict(snapshot[0]), user, now)

    _dispatch([(notifications.APPROVAL_NEEDED, request, [first.approver])])
    return request


def approve(approval: Approval, user: User, comment: str | None = None) -> AccessRequest:
    """Approve the current step. Advances to the next step, or approves the whole request.

    Raises NotAuthorizedError if ``user`` is not the assignee, InvalidStateError if the
    approval or request is no longer pending.
    """
    pending: list[Notification] = []
    with _transaction():
        approval, request = _locked_pending_approval(approval, user)
        now = utcnow()
        approval.decision = Decision.APPROVED
        approval.comment = _clean_comment(comment)
        approval.decided_at = now
        audit.log_action(
            user,
            AuditAction.APPROVAL_APPROVED,
            ENTITY_APPROVAL,
            approval.id,
            old={"decision": Decision.PENDING},
            new={"decision": Decision.APPROVED, "comment": approval.comment},
        )

        later = [s for s in request_steps(request) if s.step_order > approval.step_order]
        if later:
            next_step = later[0]
            old_step = request.current_step
            request.current_step = next_step.step_order
            audit.log_action(
                user,
                AuditAction.REQUEST_ADVANCED,
                ENTITY_REQUEST,
                request.id,
                old={"current_step": old_step},
                new={"current_step": next_step.step_order},
            )
            nxt = _open_approval(request, next_step, user, now)
            pending.append((notifications.APPROVAL_NEEDED, request, [nxt.approver]))
        else:
            request.status = RequestStatus.APPROVED
            if request.duration_days:
                request.expires_at = now + timedelta(days=request.duration_days)
            audit.log_action(
                user,
                AuditAction.REQUEST_APPROVED,
                ENTITY_REQUEST,
                request.id,
                old={"status": RequestStatus.PENDING},
                new={"status": RequestStatus.APPROVED, "expires_at": request.expires_at},
            )
            pending.append((notifications.REQUEST_APPROVED, request, [request.requester]))

    _dispatch(pending)
    return request


def reject(approval: Approval, user: User, comment: str | None) -> AccessRequest:
    """Reject the current step, which rejects the whole request. A comment is required.

    Later steps are never created.
    """
    comment = _clean_comment(comment)
    if comment is None:
        raise InvalidInputError(details={"comment": ["A comment is required when rejecting."]})

    with _transaction():
        approval, request = _locked_pending_approval(approval, user)
        now = utcnow()
        approval.decision = Decision.REJECTED
        approval.comment = comment
        approval.decided_at = now
        request.status = RequestStatus.REJECTED
        audit.log_action(
            user,
            AuditAction.APPROVAL_REJECTED,
            ENTITY_APPROVAL,
            approval.id,
            old={"decision": Decision.PENDING},
            new={"decision": Decision.REJECTED, "comment": comment},
        )
        audit.log_action(
            user,
            AuditAction.REQUEST_REJECTED,
            ENTITY_REQUEST,
            request.id,
            old={"status": RequestStatus.PENDING},
            new={"status": RequestStatus.REJECTED, "rejected_at_step": approval.step_order},
        )

    _dispatch([(notifications.REQUEST_REJECTED, request, [request.requester])])
    return request


def cancel(request: AccessRequest, user: User) -> AccessRequest:
    """Requester withdraws their own PENDING request; open approvals become SKIPPED."""
    with _transaction():
        request = _lock_request(request.id)
        if request.requester_id != user.id:
            raise NotAuthorizedError("Only the requester can cancel this request")
        if request.status != RequestStatus.PENDING:
            raise InvalidStateError(
                "Only pending requests can be cancelled", details={"status": request.status.value}
            )

        open_approvals = db.session.scalars(
            select(Approval)
            .where(Approval.request_id == request.id, Approval.decision == Decision.PENDING)
            .execution_options(populate_existing=True)
        ).all()
        for approval in open_approvals:
            approval.decision = Decision.SKIPPED
            audit.log_action(
                user,
                AuditAction.APPROVAL_SKIPPED,
                ENTITY_APPROVAL,
                approval.id,
                old={"decision": Decision.PENDING},
                new={"decision": Decision.SKIPPED, "reason": "request_cancelled"},
            )
        request.status = RequestStatus.CANCELLED
        audit.log_action(
            user,
            AuditAction.REQUEST_CANCELLED,
            ENTITY_REQUEST,
            request.id,
            old={"status": RequestStatus.PENDING},
            new={"status": RequestStatus.CANCELLED},
        )
    return request
