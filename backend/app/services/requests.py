"""Read-side queries for access requests and approvals (no state changes here).

Every list query eager-loads the relationships its serializer uses, to avoid N+1 queries.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from ..errors import NotFoundError
from ..extensions import db
from ..models import AccessRequest, Approval, Decision, RequestStatus, RoleName, User
from ..utils.pagination import Page, paginate

# Roles that may read every request.
READ_ALL_ROLES = (RoleName.AUDITOR, RoleName.ADMIN)


def _request_summary_options() -> tuple:
    return (
        joinedload(AccessRequest.requester),
        joinedload(AccessRequest.application),
        joinedload(AccessRequest.access_level),
    )


def list_requests(
    user: User,
    *,
    page: int = 1,
    per_page: int = 20,
    mine: bool = False,
    status: RequestStatus | None = None,
    application_id: int | None = None,
    requester_id: int | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> Page:
    """Requests visible to ``user``, newest first.

    Employees only ever see their own requests (``requester_id`` is ignored for them).
    Auditors and admins see everyone's, unless ``mine`` is set.
    """
    stmt = select(AccessRequest).options(*_request_summary_options())

    if mine or not user.has_role(*READ_ALL_ROLES):
        stmt = stmt.where(AccessRequest.requester_id == user.id)
    elif requester_id is not None:
        stmt = stmt.where(AccessRequest.requester_id == requester_id)

    if status is not None:
        stmt = stmt.where(AccessRequest.status == status)
    if application_id is not None:
        stmt = stmt.where(AccessRequest.application_id == application_id)
    if created_from is not None:
        stmt = stmt.where(AccessRequest.created_at >= created_from)
    if created_to is not None:
        stmt = stmt.where(AccessRequest.created_at < created_to)

    stmt = stmt.order_by(AccessRequest.created_at.desc(), AccessRequest.id.desc())
    return paginate(stmt, page, per_page)


def get_request_for_user(request_id: int, user: User) -> AccessRequest:
    """A request with its approval timeline, if ``user`` may see it.

    Visible to the requester, to anyone who is or was an approver on it, and to
    auditors/admins. Everyone else gets 404 (not 403) so ids cannot be probed.
    """
    request = db.session.scalar(
        select(AccessRequest)
        .where(AccessRequest.id == request_id)
        .options(
            *_request_summary_options(),
            selectinload(AccessRequest.approvals).options(
                joinedload(Approval.approver), joinedload(Approval.escalated_from)
            ),
        )
    )
    if request is None or not can_view(request, user):
        raise NotFoundError("Access request not found")
    return request


def can_view(request: AccessRequest, user: User) -> bool:
    if request.requester_id == user.id or user.has_role(*READ_ALL_ROLES):
        return True
    return any(user.id in (a.approver_id, a.escalated_from_id) for a in request.approvals)


def inbox(user: User, *, page: int = 1, per_page: int = 20) -> Page:
    """``user``'s open approvals, the one due soonest first."""
    stmt = (
        select(Approval)
        .join(Approval.request)
        .where(
            Approval.approver_id == user.id,
            Approval.decision == Decision.PENDING,
            AccessRequest.status == RequestStatus.PENDING,
        )
        .options(selectinload(Approval.request).options(*_request_summary_options()))
        .order_by(Approval.due_at.asc(), Approval.id.asc())
    )
    return paginate(stmt, page, per_page)
