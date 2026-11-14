"""Background jobs: escalate overdue approvals, expire time-limited access, send reminders.

Run every 15 minutes (escalation) and daily (expiry + reminders) by APScheduler when
RUN_SCHEDULER=1, and on demand with ``flask escalate`` / ``flask expire``.

Every job is **idempotent** and safe to run concurrently with users and with itself:
* it selects candidate ids, then handles each one in its own transaction after locking the
  request row (``SELECT ... FOR UPDATE``) and re-checking the condition, so a decision made
  in the meantime wins and the row is skipped;
* "already done" is recorded in the row itself (``escalated = true``, status EXPIRED,
  ``expiry_reminder_sent_at``), so a second run finds nothing to do;
* one failing row is logged and does not stop the others.
Audit rows written here have ``actor_id = NULL`` (the system).
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from datetime import datetime, timedelta

from flask import current_app
from sqlalchemy import select

from ..extensions import db
from ..models import AccessRequest, Approval, AuditAction, Decision, RequestStatus, User
from ..models.mixins import utcnow
from . import audit, notifications
from .workflow import (
    ENTITY_APPROVAL,
    ENTITY_REQUEST,
    dispatch_notifications,
    find_admin,
    lock_request,
    request_steps,
    transaction,
)

logger = logging.getLogger(__name__)

DEFAULT_SLA_HOURS = 24


def _each(ids: list[int], handle: Callable[[int], bool], label: str) -> int:
    """Run ``handle`` per id; count successes; isolate failures."""
    done = 0
    for item_id in ids:
        try:
            if handle(item_id):
                done += 1
        except Exception:
            db.session.rollback()
            logger.exception("%s failed for id %s", label, item_id)
    return done


# --------------------------------------------------------------------------- escalation


def escalation_target(current: User, request: AccessRequest) -> User | None:
    """The overdue approver's manager, else an admin. Never the requester or the current
    approver. None if nobody is eligible (the approval is then left as it is)."""
    manager = current.manager
    if manager is not None and manager.is_active and manager.id not in (request.requester_id, current.id):
        return manager
    return find_admin([request.requester_id, current.id])


def _escalate_one(approval_id: int, now: datetime) -> bool:
    approval = db.session.get(Approval, approval_id)
    if approval is None:
        return False
    with transaction():
        request = lock_request(approval.request_id)
        db.session.refresh(approval)
        still_overdue = (
            approval.decision == Decision.PENDING
            and not approval.escalated
            and approval.due_at < now
            and request.status == RequestStatus.PENDING
        )
        if not still_overdue:
            return False

        previous = approval.approver
        target = escalation_target(previous, request)
        if target is None:
            logger.warning(
                "No escalation target for approval %s; leaving it with %s", approval.id, previous.email
            )
            return False

        step = next((s for s in request_steps(request) if s.step_order == approval.step_order), None)
        old = {"approver_id": previous.id, "due_at": approval.due_at, "escalated": False}
        approval.approver = target
        approval.escalated_from = previous
        approval.escalated = True
        approval.due_at = now + timedelta(hours=step.sla_hours if step else DEFAULT_SLA_HOURS)
        audit.log_action(
            None,
            AuditAction.APPROVAL_ESCALATED,
            ENTITY_APPROVAL,
            approval.id,
            old=old,
            new={"approver_id": target.id, "due_at": approval.due_at, "escalated": True},
        )

    dispatch_notifications(
        [
            (
                notifications.APPROVAL_ESCALATED,
                request,
                [target, previous],
                {"approval": approval, "previous_approver": previous, "new_approver": target},
            )
        ]
    )
    return True


def escalate_overdue(now: datetime | None = None) -> int:
    """Reassign PENDING approvals past ``due_at`` that were not escalated yet.

    Each moves to the current approver's manager (fallback: an admin), gets
    ``escalated=true``, ``escalated_from_id`` and a fresh due date, is audited as
    APPROVAL_ESCALATED by the system, and both people are emailed. Returns how many
    approvals were escalated.
    """
    now = now or utcnow()
    ids = list(
        db.session.scalars(
            select(Approval.id)
            .join(Approval.request)
            .where(
                Approval.decision == Decision.PENDING,
                Approval.due_at < now,
                Approval.escalated.is_(False),
                AccessRequest.status == RequestStatus.PENDING,
            )
            .order_by(Approval.due_at)
        )
    )
    return _each(ids, lambda i: _escalate_one(i, now), "Escalation")


# --------------------------------------------------------------------------- expiry


def _expire_one(request_id: int, now: datetime) -> bool:
    with transaction():
        request = lock_request(request_id)
        if (
            request.status != RequestStatus.APPROVED
            or request.expires_at is None
            or request.expires_at >= now
        ):
            return False
        request.status = RequestStatus.EXPIRED
        audit.log_action(
            None,
            AuditAction.REQUEST_EXPIRED,
            ENTITY_REQUEST,
            request.id,
            old={"status": RequestStatus.APPROVED},
            new={"status": RequestStatus.EXPIRED, "expires_at": request.expires_at},
        )
    dispatch_notifications([(notifications.ACCESS_EXPIRED, request, [request.requester])])
    return True


def expire_access(now: datetime | None = None) -> int:
    """APPROVED requests whose ``expires_at`` has passed become EXPIRED (requester emailed)."""
    now = now or utcnow()
    ids = list(
        db.session.scalars(
            select(AccessRequest.id).where(
                AccessRequest.status == RequestStatus.APPROVED,
                AccessRequest.expires_at.is_not(None),
                AccessRequest.expires_at < now,
            )
        )
    )
    return _each(ids, lambda i: _expire_one(i, now), "Expiry")


def _remind_one(request_id: int, now: datetime, days: int) -> bool:
    with transaction():
        request = lock_request(request_id)
        due = (
            request.status == RequestStatus.APPROVED
            and request.expires_at is not None
            and now < request.expires_at <= now + timedelta(days=days)
            and request.expiry_reminder_sent_at is None
        )
        if not due:
            return False
        request.expiry_reminder_sent_at = now
        audit.log_action(
            None,
            AuditAction.EXPIRY_REMINDER_SENT,
            ENTITY_REQUEST,
            request.id,
            new={"expires_at": request.expires_at},
        )
    days_left = max(1, math.floor((request.expires_at - now).total_seconds() / 86400))
    dispatch_notifications(
        [(notifications.ACCESS_EXPIRING, request, [request.requester], {"days_left": days_left})]
    )
    return True


def send_expiry_reminders(now: datetime | None = None, days: int | None = None) -> int:
    """Email requesters whose access expires within ``days`` (default 7), once per request."""
    now = now or utcnow()
    days = days if days is not None else current_app.config["EXPIRY_REMINDER_DAYS"]
    ids = list(
        db.session.scalars(
            select(AccessRequest.id).where(
                AccessRequest.status == RequestStatus.APPROVED,
                AccessRequest.expires_at > now,
                AccessRequest.expires_at <= now + timedelta(days=days),
                AccessRequest.expiry_reminder_sent_at.is_(None),
            )
        )
    )
    return _each(ids, lambda i: _remind_one(i, now, days), "Expiry reminder")


def run_daily(now: datetime | None = None) -> dict[str, int]:
    """The daily job: expire first, then remind (so expired requests are never reminded)."""
    now = now or utcnow()
    return {"expired": expire_access(now), "reminded": send_expiry_reminders(now)}
