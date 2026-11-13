"""One ordered approval step in an application's workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .enums import ApproverType
from .mixins import TimestampMixin

if TYPE_CHECKING:
    from .application import Application
    from .user import User


class WorkflowStep(TimestampMixin, db.Model):
    __tablename__ = "workflow_steps"
    __table_args__ = (
        UniqueConstraint("application_id", "step_order"),
        CheckConstraint("step_order >= 1", name="step_order_positive"),
        CheckConstraint("sla_hours BETWEEN 1 AND 168", name="sla_hours_range"),
        CheckConstraint(
            "approver_type <> 'SPECIFIC_USER' OR approver_user_id IS NOT NULL",
            name="specific_user_has_approver",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    step_order: Mapped[int]
    approver_type: Mapped[ApproverType] = mapped_column(Enum(ApproverType, name="approver_type"))
    approver_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    sla_hours: Mapped[int] = mapped_column(default=24, server_default="24")

    application: Mapped[Application] = relationship(back_populates="workflow_steps")
    approver_user: Mapped[User | None] = relationship()

    def __repr__(self) -> str:
        return f"<WorkflowStep app={self.application_id} #{self.step_order} {self.approver_type}>"
