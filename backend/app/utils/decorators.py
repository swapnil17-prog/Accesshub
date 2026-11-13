"""Authorization helpers.

``@role_required`` is the coarse, role-level gate. Services must still do object-level checks
(e.g. an approver may only act on approvals where ``approver_id == current_user.id``).
"""

from collections.abc import Callable
from functools import wraps
from typing import ParamSpec, TypeVar

from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_jwt_extended import get_current_user as _jwt_current_user

from ..errors import ForbiddenError, UnauthorizedError
from ..models import User

P = ParamSpec("P")
R = TypeVar("R")

__all__ = ["current_user", "get_current_user", "role_required"]


def get_current_user() -> User:
    """The authenticated user for this request (call after JWT verification)."""
    user = _jwt_current_user()
    if user is None:
        raise UnauthorizedError()
    return user


def role_required(*roles: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Require a valid access token and at least one of ``roles``.

    Roles are checked against the user freshly loaded from the DB (not just the JWT claim),
    so removing a role or deactivating a user takes effect immediately.
    """
    if not roles:
        raise ValueError("role_required() needs at least one role")
    allowed = sorted({str(r) for r in roles})

    def decorator(fn: Callable[P, R]) -> Callable[P, R]:
        @wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            verify_jwt_in_request()
            if not get_current_user().has_role(*allowed):
                raise ForbiddenError(details={"required_roles": allowed})
            return fn(*args, **kwargs)

        return wrapper

    return decorator
