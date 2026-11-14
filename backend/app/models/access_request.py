"""An employee's request for an access level on an application."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .enums import RequestStatus
from .mixins import TimestampMixin

if TYPE_CHECKING:
    from .access_level import AppAccessLevel
    from .application import Application
    from .approval import Approval
    from .user import User


class AccessRequest(TimestampMixin, db.Model):
    __tablename__ = "access_requests"
    __table_args__ = (
        CheckConstraint("current_step >= 1", name="current_step_positive"),
        CheckConstraint("duration_days IS NULL OR duration_days > 0", name="duration_days_positive"),
        # DB-level backstop for "one PENDING request per user + app + level"; the workflow
        # service checks first to return a friendly error.
        Index(
            "uq_access_requests_one_pending",
            "requester_id",
            "application_id",
            "access_level_id",
            unique=True,
            postgresql_where=text("status = 'PENDING'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    access_level_id: Mapped[int] = mapped_column(ForeignKey("app_access_levels.id"), index=True)
    justification: Mapped[str] = mapped_column(Text)
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, name="request_status"),
        default=RequestStatus.PENDING,
        server_default=RequestStatus.PENDING.value,
        index=True,
    )
    current_step: Mapped[int] = mapped_column(default=1, server_default="1")
    duration_days: Mapped[int | None]
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set when the "expires soon" email goes out, so the daily job reminds only once.
    expiry_reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Copy of the application's workflow steps taken at submission time, so editing a
    # workflow never changes the chain of a request that is already in flight.
    workflow_snapshot: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )

    requester: Mapped[User] = relationship()
    application: Mapped[Application] = relationship()
    access_level: Mapped[AppAccessLevel] = relationship()
    approvals: Mapped[list[Approval]] = relationship(back_populates="request", order_by="Approval.step_order")

    def __repr__(self) -> str:
        return f"<AccessRequest {self.id} {self.status}>"
