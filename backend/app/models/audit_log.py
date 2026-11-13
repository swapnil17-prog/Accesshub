"""Append-only audit trail.

Append-only is enforced twice: an ORM guard here (fails fast in Python) and a Postgres
trigger created by the initial migration (protects against raw SQL too). There are no
update/delete endpoints for audit logs, ever.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, event, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .mixins import utcnow

if TYPE_CHECKING:
    from .user import User


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_entity_type_entity_id", "entity_type", "entity_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)  # NULL = system
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[int | None]
    old_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    new_value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ip_address: Mapped[str | None] = mapped_column(String(45))
    user_agent: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False
    )

    actor: Mapped[User | None] = relationship()

    def __repr__(self) -> str:
        return f"<AuditLog {self.id} {self.action} {self.entity_type}:{self.entity_id}>"


class AuditLogImmutableError(RuntimeError):
    pass


@event.listens_for(AuditLog, "before_update")
def _block_update(*_args: Any) -> None:
    raise AuditLogImmutableError("audit_logs is append-only; updates are not allowed")


@event.listens_for(AuditLog, "before_delete")
def _block_delete(*_args: Any) -> None:
    raise AuditLogImmutableError("audit_logs is append-only; deletes are not allowed")
