"""Authentication: credential checks, token issuing and revocation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from functools import cache
from typing import Any

from flask import current_app
from flask_jwt_extended import create_access_token, create_refresh_token, decode_token
from flask_jwt_extended.exceptions import JWTExtendedException
from jwt.exceptions import PyJWTError
from sqlalchemy import func, select
from werkzeug.security import check_password_hash

from ..errors import InvalidCredentialsError, InvalidInputError, TooManyAttemptsError
from ..extensions import db
from ..models import AuditAction, AuditLog, TokenBlocklist, User
from ..models.mixins import utcnow
from ..models.user import hash_password
from . import audit
from .passwords import password_problems


@cache
def _dummy_hash() -> str:
    return hash_password("timing-equaliser")  # same method as real users, so timings match


def _record_login_failure(user: User | None, email: str, reason: str) -> None:
    audit.log_action(
        user,
        AuditAction.LOGIN_FAILED,
        "user",
        user.id if user else None,
        new={"email": email, "reason": reason},
    )
    db.session.commit()


def _recent_failures(email: str, user: User | None) -> int:
    """Failed sign-ins for ``email`` within the lockout window and since its last success.

    Read from the audit log, so the count is shared by every worker and container.
    Attempts refused *because of* the lockout are not counted (the lock doesn't extend itself).
    """
    since = utcnow() - timedelta(minutes=current_app.config["LOGIN_LOCKOUT_MINUTES"])
    if user is not None:
        last_success = db.session.scalar(
            select(func.max(AuditLog.created_at)).where(
                AuditLog.action == AuditAction.LOGIN_SUCCESS.value,
                AuditLog.entity_type == "user",
                AuditLog.entity_id == user.id,
            )
        )
        if last_success is not None and last_success > since:
            since = last_success
    return db.session.scalar(
        select(func.count(AuditLog.id)).where(
            AuditLog.action == AuditAction.LOGIN_FAILED.value,
            AuditLog.created_at >= since,
            AuditLog.new_value["email"].astext == email,
            AuditLog.new_value["reason"].astext != "locked_out",
        )
    )


def authenticate(email: str, password: str) -> User:
    """Return the active user matching the credentials, or raise InvalidCredentialsError.

    After LOGIN_LOCKOUT_ATTEMPTS failures within LOGIN_LOCKOUT_MINUTES the account is locked
    for that window (TooManyAttemptsError, HTTP 429).

    Every attempt is audited (LOGIN_SUCCESS / LOGIN_FAILED). The client always gets the same
    error for unknown email, wrong password and inactive account, so accounts can't be probed;
    the real reason is kept in the audit log.
    """
    email = email.strip().lower()
    user = db.session.scalar(select(User).where(User.email == email))

    # Checked before the password, so a locked account can't be brute-forced at all. Unknown
    # emails lock the same way, so the lockout doesn't reveal which accounts exist.
    if _recent_failures(email, user) >= current_app.config["LOGIN_LOCKOUT_ATTEMPTS"]:
        _record_login_failure(user, email, "locked_out")
        minutes = current_app.config["LOGIN_LOCKOUT_MINUTES"]
        raise TooManyAttemptsError(
            f"Too many failed sign-in attempts. Try again in {minutes} minutes.",
            details={"retry_after_minutes": minutes},
        )

    if user is None:
        check_password_hash(_dummy_hash(), password)  # keep response time similar
        _record_login_failure(None, email, "unknown_email")
        raise InvalidCredentialsError()
    if not user.check_password(password):
        _record_login_failure(user, email, "bad_password")
        raise InvalidCredentialsError()
    if not user.is_active:
        _record_login_failure(user, email, "inactive")
        raise InvalidCredentialsError()

    audit.log_action(user, AuditAction.LOGIN_SUCCESS, "user", user.id)
    db.session.commit()
    return user


def _claims(user: User) -> dict[str, Any]:
    return {"roles": user.role_names, "name": user.name}


def issue_tokens(user: User) -> dict[str, str]:
    """Access token (15 min) carries user id (``sub``) and role names; refresh token (7 days)."""
    identity = str(user.id)
    return {
        "access_token": create_access_token(identity=identity, additional_claims=_claims(user)),
        "refresh_token": create_refresh_token(identity=identity),
    }


def refresh_access_token(user: User) -> str:
    """New access token with roles re-read from the DB, so role changes apply on refresh."""
    return create_access_token(identity=str(user.id), additional_claims=_claims(user))


def _revoke(payload: dict[str, Any]) -> None:
    exists = db.session.scalar(select(TokenBlocklist.id).where(TokenBlocklist.jti == payload["jti"]))
    if exists is None:
        db.session.add(
            TokenBlocklist(
                jti=payload["jti"],
                token_type=payload["type"],
                user_id=int(payload["sub"]),
                expires_at=datetime.fromtimestamp(payload["exp"], UTC),
            )
        )


def logout(user: User, access_payload: dict[str, Any], refresh_token: str | None = None) -> None:
    """Revoke the presented access token and, if given, the user's refresh token."""
    _revoke(access_payload)
    if refresh_token:
        try:
            refresh_payload = decode_token(refresh_token)
        except (JWTExtendedException, PyJWTError):
            refresh_payload = None  # already expired/revoked/garbage: nothing left to revoke
        if refresh_payload is not None:
            if refresh_payload.get("type") != "refresh" or refresh_payload.get("sub") != str(user.id):
                raise InvalidInputError(details={"refresh_token": ["Not a refresh token for this user."]})
            _revoke(refresh_payload)

    audit.log_action(user, AuditAction.LOGOUT, "user", user.id)
    db.session.commit()


def change_password(user: User, current_password: str, new_password: str) -> dict[str, str]:
    """The signed-in user changes their own password.

    Errors are 422s (never 401: the frontend treats 401 as an expired session). On success every
    existing token for the user stops working (``password_changed_at``) and a fresh token pair
    is returned so the current browser stays signed in.
    """
    if not user.check_password(current_password):
        audit.log_action(
            user, AuditAction.PASSWORD_CHANGE_FAILED, "user", user.id, new={"reason": "bad_password"}
        )
        db.session.commit()
        raise InvalidInputError(details={"current_password": ["Your current password is incorrect."]})
    if new_password == current_password:
        raise InvalidInputError(details={"new_password": ["Choose a new password, not your current one."]})
    problems = password_problems(new_password, email=user.email, name=user.name)
    if problems:
        raise InvalidInputError("Password does not meet the policy", details={"new_password": problems})

    user.set_password(new_password)
    audit.log_action(
        user,
        AuditAction.PASSWORD_CHANGED,
        "user",
        user.id,
        new={"by": "self", "other_sessions_revoked": True},
    )
    db.session.commit()
    return issue_tokens(user)
