"""User administration (admin only; the route enforces the role).

Safety rules beyond plain CRUD:
* reporting lines may not form a cycle (A manages B manages ... manages A);
* an admin cannot deactivate themselves or drop their own admin role;
* the last active admin can never be deactivated or lose the admin role.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from ..errors import ConflictError, InvalidInputError, InvalidStateError, NotFoundError
from ..extensions import db
from ..models import AuditAction, Role, RoleName, User
from ..utils.pagination import Page, like_pattern, paginate
from . import audit

ENTITY = "user"
MAX_CHAIN = 1000  # defensive bound when walking reporting lines


def _snapshot(user: User) -> dict[str, Any]:
    return {
        "name": user.name,
        "email": user.email,
        "department": user.department,
        "manager_id": user.manager_id,
        "is_active": user.is_active,
    }


# --------------------------------------------------------------------------- reads


def list_users(
    *,
    q: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    page: int = 1,
    per_page: int = 20,
) -> Page:
    """Search by name or email (case-insensitive), filter by role/active, ordered by name."""
    stmt = select(User).options(joinedload(User.manager)).order_by(User.name, User.id)
    if q:
        pattern = like_pattern(q)
        stmt = stmt.where(or_(User.name.ilike(pattern, escape="\\"), User.email.ilike(pattern, escape="\\")))
    if role:
        stmt = stmt.where(User.roles.any(Role.name == role))
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))
    return paginate(stmt, page, per_page)


def lookup_users(q: str | None, limit: int = 20) -> list[User]:
    """Active users matching ``q`` — for pickers (e.g. a workflow's SPECIFIC_USER)."""
    stmt = select(User).where(User.is_active.is_(True)).order_by(User.name).limit(limit)
    if q:
        pattern = like_pattern(q)
        stmt = stmt.where(or_(User.name.ilike(pattern, escape="\\"), User.email.ilike(pattern, escape="\\")))
    return list(db.session.scalars(stmt))


def get_user(user_id: int) -> User:
    user = db.session.scalar(select(User).where(User.id == user_id).options(joinedload(User.manager)))
    if user is None:
        raise NotFoundError("User not found")
    return user


# --------------------------------------------------------------------------- validation helpers


def _ensure_email_free(email: str, exclude_id: int | None = None) -> None:
    clauses = [User.email == email.strip().lower()]
    if exclude_id is not None:
        clauses.append(User.id != exclude_id)
    if db.session.scalar(select(exists().where(*clauses))):
        raise ConflictError("A user with this email already exists", code="EMAIL_TAKEN")


def validate_manager(user: User | None, manager_id: int | None) -> User | None:
    """Check ``manager_id`` is an acceptable manager for ``user`` (None for a new user).

    Walks up the proposed manager's own reporting line; meeting ``user`` means the change
    would create a cycle.
    """
    if manager_id is None:
        return None
    manager = db.session.get(User, manager_id)
    if manager is None or not manager.is_active:
        raise InvalidInputError(details={"manager_id": ["Manager must be an active user."]})
    if user is None:
        return manager
    if manager.id == user.id:
        raise InvalidInputError(details={"manager_id": ["A user cannot be their own manager."]})

    current: User | None = manager
    for _ in range(MAX_CHAIN):
        if current is None:
            return manager
        if current.id == user.id:
            raise InvalidInputError(
                details={"manager_id": [f"{manager.name} reports to {user.name}; this would create a cycle."]}
            )
        current = current.manager
    raise InvalidInputError(details={"manager_id": ["Reporting chain is too deep."]})


def _roles_by_name(names: list[str]) -> list[Role]:
    wanted = list(dict.fromkeys(names))
    unknown = sorted(set(wanted) - {r.value for r in RoleName})
    if unknown:
        raise InvalidInputError(details={"roles": [f"Unknown role(s): {', '.join(unknown)}."]})
    roles = {r.name: r for r in db.session.scalars(select(Role).where(Role.name.in_(wanted)))}
    for name in wanted:  # roles table may not be seeded yet in a fresh database
        if name not in roles:
            roles[name] = Role(name=name)
            db.session.add(roles[name])
    return [roles[n] for n in wanted]


def _other_active_admins(user: User) -> int:
    return db.session.scalar(
        select(func.count(User.id)).where(
            User.id != user.id,
            User.is_active.is_(True),
            User.roles.any(Role.name == RoleName.ADMIN.value),
        )
    )


def _ensure_admin_remains(actor: User, user: User, *, losing_admin: bool) -> None:
    if not losing_admin or not user.has_role(RoleName.ADMIN):
        return
    if user.id == actor.id:
        raise InvalidStateError("You cannot remove your own admin access", code="SELF_LOCKOUT")
    if _other_active_admins(user) == 0:
        raise InvalidStateError("At least one active admin must remain", code="LAST_ADMIN")


# --------------------------------------------------------------------------- writes


def _commit_or_email_conflict() -> None:
    try:
        db.session.commit()
    except IntegrityError as exc:  # concurrent create with the same email
        db.session.rollback()
        raise ConflictError("A user with this email already exists", code="EMAIL_TAKEN") from exc


def create_user(actor: User, data: dict[str, Any]) -> User:
    """Create a user. ``data``: name, email, password, department?, manager_id?, roles?."""
    _ensure_email_free(data["email"])
    manager = validate_manager(None, data.get("manager_id"))
    roles = _roles_by_name(data.get("roles") or [RoleName.EMPLOYEE.value])
    user = User(name=data["name"].strip(), email=data["email"], department=data.get("department"))
    user.set_password(data["password"])
    db.session.add(user)
    user.manager = manager
    user.roles = roles
    db.session.flush()
    audit.log_action(
        actor, AuditAction.USER_CREATED, ENTITY, user.id, new={**_snapshot(user), "roles": user.role_names}
    )
    _commit_or_email_conflict()
    return user


def update_user(actor: User, user_id: int, data: dict[str, Any]) -> User:
    """Partial update of profile fields, manager, active flag and (optionally) password."""
    user = get_user(user_id)
    old = _snapshot(user)

    if "email" in data:
        _ensure_email_free(data["email"], exclude_id=user.id)
        user.email = data["email"]
    if "name" in data:
        user.name = data["name"].strip()
    if "department" in data:
        user.department = data["department"]
    if "manager_id" in data:
        user.manager = validate_manager(user, data["manager_id"])
    if "is_active" in data and data["is_active"] != user.is_active:
        if not data["is_active"]:
            if user.id == actor.id:
                raise InvalidStateError("You cannot deactivate your own account", code="SELF_LOCKOUT")
            _ensure_admin_remains(actor, user, losing_admin=True)
        user.is_active = data["is_active"]
    password_changed = bool(data.get("password"))
    if password_changed:
        user.set_password(data["password"])

    new = _snapshot(user)
    changed = {k for k in new if new[k] != old[k]}
    if changed or password_changed:
        audit.log_action(
            actor,
            AuditAction.USER_UPDATED,
            ENTITY,
            user.id,
            old={k: old[k] for k in changed},
            new={**{k: new[k] for k in changed}, **({"password_changed": True} if password_changed else {})},
        )
    _commit_or_email_conflict()
    return user


def set_roles(actor: User, user_id: int, role_names: list[str]) -> User:
    """Replace the user's roles with exactly ``role_names``."""
    user = get_user(user_id)
    old = user.role_names
    roles = _roles_by_name(role_names)
    _ensure_admin_remains(actor, user, losing_admin=RoleName.ADMIN.value not in role_names)
    user.roles = roles
    db.session.flush()
    new = user.role_names
    if sorted(old) != sorted(new):
        audit.log_action(
            actor, AuditAction.USER_ROLES_CHANGED, ENTITY, user.id, old={"roles": old}, new={"roles": new}
        )
    db.session.commit()
    return user
