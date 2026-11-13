"""A single approver decision on one step of an access request."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, Text, false, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .enums import Decision
from .mixins import TimestampMixin

if TYPE_CHECKING:
    from .access_request import AccessRequest
    from .user import User


class Approval(TimestampMixin, db.Model):
    __tablename__ = "approvals"
    __table_args__ = (
        CheckConstraint("step_order >= 1", name="step_order_positive"),
        # Inbox query: "my pending approvals".
        Index("ix_approvals_approver_id_decision", "approver_id", "decision"),
        # Escalation job: "pending approvals past due".
        Index("ix_approvals_due_at_pending", "due_at", postgresql_where=text("decision = 'PENDING'")),
        # Engine invariant: a request has at most one open approval at a time.
        Index(
            "uq_approvals_one_pending_per_request",
            "request_id",
            unique=True,
            postgresql_where=text("decision = 'PENDING'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("access_requests.id", ondelete="CASCADE"), index=True)
    step_order: Mapped[int]
    approver_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[Decision] = mapped_column(
        Enum(Decision, name="approval_decision"),
        default=Decision.PENDING,
        server_default=Decision.PENDING.value,
    )
    comment: Mapped[str | None] = mapped_column(Text)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    escalated: Mapped[bool] = mapped_column(default=False, server_default=false())
    escalated_from_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    request: Mapped[AccessRequest] = relationship(back_populates="approvals")
    approver: Mapped[User] = relationship(foreign_keys=[approver_id])
    escalated_from: Mapped[User | None] = relationship(foreign_keys=[escalated_from_id])

    def __repr__(self) -> str:
        return f"<Approval {self.id} req={self.request_id} #{self.step_order} {self.decision}>"
