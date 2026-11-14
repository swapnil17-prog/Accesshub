"""Audit log queries, CSV export and the summary report (auditor/admin, read-only)."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import aliased, joinedload

from ..extensions import db
from ..models import (
    AccessRequest,
    Application,
    Approval,
    AuditAction,
    AuditLog,
    Decision,
    RequestStatus,
    User,
)
from ..models.mixins import utcnow
from ..utils.pagination import Page, paginate
from . import audit

SYSTEM_ACTOR = "system"
CSV_COLUMNS = [
    "id",
    "created_at",
    "actor_id",
    "actor_name",
    "actor_email",
    "action",
    "entity_type",
    "entity_id",
    "old_value",
    "new_value",
    "ip_address",
    "user_agent",
]
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


# --------------------------------------------------------------------------- audit log


def _filtered(
    stmt: Select,
    *,
    actor: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    action: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> Select:
    if actor == SYSTEM_ACTOR:
        stmt = stmt.where(AuditLog.actor_id.is_(None))
    elif actor is not None:
        stmt = stmt.where(AuditLog.actor_id == int(actor))
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if created_from is not None:
        stmt = stmt.where(AuditLog.created_at >= created_from)
    if created_to is not None:
        stmt = stmt.where(AuditLog.created_at < created_to)
    return stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())


def list_audit(*, page: int = 1, per_page: int = 50, **filters: Any) -> Page:
    """Newest first. ``actor`` is a user id or ``"system"`` (rows written by jobs)."""
    stmt = _filtered(select(AuditLog).options(joinedload(AuditLog.actor)), **filters)
    return paginate(stmt, page, per_page)


def _csv_safe(value: Any) -> str:
    """Neutralise spreadsheet formula injection (a cell starting with = + - @ ...)."""
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(_FORMULA_PREFIXES) else text


def _json_cell(value: Any) -> str:
    return "" if value is None else json.dumps(value, sort_keys=True)


def export_csv(exported_by: User, **filters: Any) -> Iterator[str]:
    """Record the export itself, then stream matching rows as CSV text chunks.

    Rows are fetched with a server-side cursor in batches (``yield_per``) and joined to the
    actor in SQL, so memory stays flat however large the log is.
    """
    audit.log_action(
        exported_by,
        AuditAction.AUDIT_EXPORTED,
        "audit_log",
        None,
        new={k: v for k, v in filters.items() if v is not None},
    )
    db.session.commit()

    actor_alias = aliased(User)
    stmt = _filtered(
        select(AuditLog, actor_alias.name, actor_alias.email).outerjoin(
            actor_alias, AuditLog.actor_id == actor_alias.id
        ),
        **filters,
    ).execution_options(yield_per=500)

    def generate() -> Iterator[str]:
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(CSV_COLUMNS)
        for count, (row, actor_name, actor_email) in enumerate(db.session.execute(stmt), start=1):
            writer.writerow(
                [
                    row.id,
                    row.created_at.isoformat(),
                    row.actor_id if row.actor_id is not None else SYSTEM_ACTOR,
                    _csv_safe(actor_name),
                    _csv_safe(actor_email),
                    _csv_safe(row.action),
                    _csv_safe(row.entity_type),
                    row.entity_id if row.entity_id is not None else "",
                    _csv_safe(_json_cell(row.old_value)),
                    _csv_safe(_json_cell(row.new_value)),
                    _csv_safe(row.ip_address),
                    _csv_safe(row.user_agent),
                ]
            )
            if count % 500 == 0:
                yield buffer.getvalue()
                buffer.seek(0)
                buffer.truncate()
        yield buffer.getvalue()

    return generate()


# --------------------------------------------------------------------------- summary report


def summary(now: datetime | None = None) -> dict[str, Any]:
    """Headline numbers for the dashboard.

    * ``by_status``: request count per status (every status present, zeros included)
    * ``by_application``: totals and per-status counts per application
    * ``avg_approval_hours``: mean time from submission to the final approval, for requests
      that were approved (including ones that have since expired)
    * ``escalations_last_30_days``: APPROVAL_ESCALATED audit events in the last 30 days
    * ``overdue_approvals``: approvals currently pending past their due time
    """
    now = now or utcnow()

    status_counts = dict(
        db.session.execute(select(AccessRequest.status, func.count()).group_by(AccessRequest.status)).all()
    )
    by_status = {s.value: status_counts.get(s, 0) for s in RequestStatus}

    per_status = [
        func.count(AccessRequest.id).filter(AccessRequest.status == s).label(s.value) for s in RequestStatus
    ]
    app_rows = db.session.execute(
        select(Application.id, Application.name, func.count(AccessRequest.id).label("total"), *per_status)
        .outerjoin(AccessRequest, AccessRequest.application_id == Application.id)
        .group_by(Application.id, Application.name)
        .order_by(func.count(AccessRequest.id).desc(), Application.name)
    ).all()
    by_application = [
        {
            "application_id": row.id,
            "name": row.name,
            "total": row.total,
            "by_status": {s.value: getattr(row, s.value) for s in RequestStatus},
        }
        for row in app_rows
    ]

    final_decision = (
        select(Approval.request_id, func.max(Approval.decided_at).label("decided_at"))
        .where(Approval.decided_at.is_not(None))
        .group_by(Approval.request_id)
        .subquery()
    )
    avg_seconds = db.session.scalar(
        select(func.avg(func.extract("epoch", final_decision.c.decided_at - AccessRequest.created_at)))
        .join(final_decision, final_decision.c.request_id == AccessRequest.id)
        .where(AccessRequest.status.in_([RequestStatus.APPROVED, RequestStatus.EXPIRED]))
    )

    escalations = db.session.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.action == AuditAction.APPROVAL_ESCALATED.value,
            AuditLog.created_at >= now - timedelta(days=30),
        )
    )
    overdue = db.session.scalar(
        select(func.count(Approval.id)).where(Approval.decision == Decision.PENDING, Approval.due_at < now)
    )

    return {
        "total_requests": sum(by_status.values()),
        "by_status": by_status,
        "by_application": by_application,
        "avg_approval_hours": round(float(avg_seconds) / 3600, 1) if avg_seconds is not None else None,
        "escalations_last_30_days": escalations or 0,
        "overdue_approvals": overdue or 0,
        "generated_at": now.isoformat(),
    }
