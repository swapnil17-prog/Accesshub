"""User model."""

from __future__ import annotations

from datetime import datetime

from flask import current_app, has_app_context
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, true
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from .mixins import TimestampMixin, utcnow
from .role import Role, user_roles


def hash_password(password: str) -> str:
    """Hash with the configured method (PASSWORD_HASH_METHOD), scrypt by default."""
    method = current_app.config.get("PASSWORD_HASH_METHOD", "scrypt") if has_app_context() else "scrypt"
    return generate_password_hash(password, method=method)


class User(TimestampMixin, db.Model):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("manager_id IS NULL OR manager_id <> id", name="not_own_manager"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    department: Mapped[str | None] = mapped_column(String(120))
    manager_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    # Tokens issued before this moment are rejected (see jwt_callbacks.is_revoked), so changing or
    # resetting a password signs the user out of every other session.
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    manager: Mapped[User | None] = relationship(remote_side="User.id", back_populates="reports")
    reports: Mapped[list[User]] = relationship(back_populates="manager")
    roles: Mapped[list[Role]] = relationship(secondary=user_roles, lazy="selectin", order_by=Role.name)

    @validates("email")
    def _normalise_email(self, _key: str, value: str) -> str:
        # Stored lower-cased so the UNIQUE constraint is effectively case-insensitive.
        return value.strip().lower()

    def set_password(self, password: str) -> None:
        self.password_hash = hash_password(password)
        self.password_changed_at = utcnow()

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def role_names(self) -> list[str]:
        return [role.name for role in self.roles]

    def has_role(self, *names: str) -> bool:
        """True if the user holds at least one of ``names``."""
        return bool(set(self.role_names) & {str(n) for n in names})

    def __repr__(self) -> str:
        return f"<User {self.email}>"
