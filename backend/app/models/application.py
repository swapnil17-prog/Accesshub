"""Application (a business system people request access to)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .mixins import TimestampMixin

if TYPE_CHECKING:
    from .access_level import AppAccessLevel
    from .user import User
    from .workflow_step import WorkflowStep


class Application(TimestampMixin, db.Model):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())

    owner: Mapped[User] = relationship()
    access_levels: Mapped[list[AppAccessLevel]] = relationship(
        back_populates="application", cascade="all, delete-orphan", order_by="AppAccessLevel.id"
    )
    workflow_steps: Mapped[list[WorkflowStep]] = relationship(
        back_populates="application", cascade="all, delete-orphan", order_by="WorkflowStep.step_order"
    )

    def __repr__(self) -> str:
        return f"<Application {self.name}>"
