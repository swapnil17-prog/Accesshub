"""Access levels offered by an application (e.g. Viewer, Developer, Admin)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .mixins import TimestampMixin

if TYPE_CHECKING:
    from .application import Application


class AppAccessLevel(TimestampMixin, db.Model):
    __tablename__ = "app_access_levels"
    __table_args__ = (UniqueConstraint("application_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(120))

    application: Mapped[Application] = relationship(back_populates="access_levels")

    def __repr__(self) -> str:
        return f"<AppAccessLevel {self.application_id}:{self.name}>"
