"""Flask-JWT-Extended hooks: user loading, revocation checks and uniform error JSON."""

from __future__ import annotations

from typing import Any

from flask_jwt_extended import JWTManager
from sqlalchemy import select

from .errors import error_response
from .extensions import db
from .models import TokenBlocklist, User


def register_jwt_callbacks(jwt: JWTManager) -> None:
    @jwt.user_lookup_loader
    def load_user(_header: dict[str, Any], payload: dict[str, Any]) -> User | None:
        # Loaded from the DB on every request, so deactivation takes effect immediately.
        user = db.session.get(User, int(payload["sub"]))
        return user if user is not None and user.is_active else None

    @jwt.token_in_blocklist_loader
    def is_revoked(_header: dict[str, Any], payload: dict[str, Any]) -> bool:
        """Revoked by logout (blocklist) or issued before the user's last password change."""
        blocked = db.session.scalar(select(TokenBlocklist.id).where(TokenBlocklist.jti == payload["jti"]))
        if blocked is not None:
            return True
        user = db.session.get(User, int(payload["sub"]))  # identity map: no extra query later
        changed_at = user.password_changed_at if user is not None else None
        # ``iat`` has whole-second precision, so compare at that precision: tokens issued in the
        # same second as the change (the fresh ones returned by change-password) stay valid.
        return changed_at is not None and payload.get("iat", 0) < int(changed_at.timestamp())

    @jwt.user_lookup_error_loader
    def user_lookup_error(_header, _payload):
        return error_response(401, "USER_INACTIVE", "User not found or inactive")

    @jwt.expired_token_loader
    def expired(_header, _payload):
        return error_response(401, "TOKEN_EXPIRED", "Token has expired")

    @jwt.revoked_token_loader
    def revoked(_header, _payload):
        return error_response(401, "TOKEN_REVOKED", "Token has been revoked")

    @jwt.invalid_token_loader
    def invalid(reason: str):
        return error_response(401, "INVALID_TOKEN", "Invalid token", {"reason": reason})

    @jwt.unauthorized_loader
    def missing(reason: str):
        return error_response(401, "AUTHORIZATION_REQUIRED", "Authentication required", {"reason": reason})

    @jwt.needs_fresh_token_loader
    def needs_fresh(_header, _payload):
        return error_response(401, "FRESH_TOKEN_REQUIRED", "Fresh token required")
