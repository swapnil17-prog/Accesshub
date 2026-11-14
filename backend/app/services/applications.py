"""Applications, their access levels and their approval workflows.

Permissions: admins manage every application; an app_owner may edit only applications they
own (name/description, access levels, workflow). Creating, re-assigning the owner,
(de)activating and deleting are admin-only. Routes apply the role gate; the object-level
check (``ensure_can_manage``) lives here.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload

from ..errors import ConflictError, InvalidInputError, NotAuthorizedError, NotFoundError
from ..extensions import db
from ..models import (
    AccessRequest,
    AppAccessLevel,
    Application,
    ApproverType,
    AuditAction,
    RoleName,
    User,
    WorkflowStep,
)
from ..utils.pagination import Page, like_pattern, paginate
from . import audit

ENTITY = "application"
MAX_STEPS = 10


# --------------------------------------------------------------------------- permissions


def can_manage(user: User, application: Application) -> bool:
    return user.has_role(RoleName.ADMIN) or (
        user.has_role(RoleName.APP_OWNER) and application.owner_id == user.id
    )


def ensure_can_manage(user: User, application: Application) -> None:
    if not can_manage(user, application):
        raise NotAuthorizedError("Only an admin or this application's owner can change it")


def _ensure_admin(user: User) -> None:
    if not user.has_role(RoleName.ADMIN):
        raise NotAuthorizedError("Only an admin can change this")


# --------------------------------------------------------------------------- reads


def _options() -> tuple:
    return (
        joinedload(Application.owner),
        selectinload(Application.access_levels),
        selectinload(Application.workflow_steps).joinedload(WorkflowStep.approver_user),
    )


def list_applications(
    user: User, *, q: str | None = None, include_inactive: bool = False, page: int = 1, per_page: int = 20
) -> Page:
    """Active applications for everyone; admins may include inactive ones."""
    stmt = select(Application).options(*_options()).order_by(Application.name)
    if not (include_inactive and user.has_role(RoleName.ADMIN)):
        stmt = stmt.where(Application.is_active.is_(True))
    if q:
        stmt = stmt.where(Application.name.ilike(like_pattern(q), escape="\\"))
    return paginate(stmt, page, per_page)


def get_application(app_id: int, user: User) -> Application:
    """Inactive applications are only visible to people who can manage them."""
    application = db.session.scalar(select(Application).where(Application.id == app_id).options(*_options()))
    if application is None or (not application.is_active and not can_manage(user, application)):
        raise NotFoundError("Application not found")
    return application


def _snapshot(application: Application) -> dict[str, Any]:
    return {
        "name": application.name,
        "description": application.description,
        "owner_id": application.owner_id,
        "is_active": application.is_active,
    }


def _steps_snapshot(application: Application) -> list[dict[str, Any]]:
    return [
        {
            "step_order": s.step_order,
            "approver_type": s.approver_type,
            "approver_user_id": s.approver_user_id,
            "sla_hours": s.sla_hours,
        }
        for s in sorted(application.workflow_steps, key=lambda s: s.step_order)
    ]


# --------------------------------------------------------------------------- writes


def _validate_owner(owner_id: int) -> User:
    owner = db.session.get(User, owner_id)
    if owner is None or not owner.is_active:
        raise InvalidInputError(details={"owner_id": ["Owner must be an active user."]})
    if not owner.has_role(RoleName.APP_OWNER, RoleName.ADMIN):
        raise InvalidInputError(details={"owner_id": ["Owner must have the app_owner or admin role."]})
    return owner


def _ensure_name_free(name: str, exclude_id: int | None = None) -> None:
    stmt = select(exists().where(func.lower(Application.name) == name.lower()))
    if exclude_id is not None:
        stmt = select(
            exists().where(func.lower(Application.name) == name.lower(), Application.id != exclude_id)
        )
    if db.session.scalar(stmt):
        raise ConflictError("An application with this name already exists", code="NAME_TAKEN")


def _commit_or_conflict() -> None:
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ConflictError("Conflicts with an existing record", code="NAME_TAKEN") from exc


def create_application(actor: User, data: dict[str, Any]) -> Application:
    """Admin only. ``data``: name, description?, owner_id, access_levels? (list of names)."""
    _ensure_admin(actor)
    name = data["name"].strip()
    _ensure_name_free(name)
    owner = _validate_owner(data["owner_id"])
    application = Application(name=name, description=data.get("description"), owner=owner)
    for level_name in dict.fromkeys(n.strip() for n in data.get("access_levels") or []):
        application.access_levels.append(AppAccessLevel(name=level_name))
    db.session.add(application)
    db.session.flush()
    audit.log_action(
        actor,
        AuditAction.APPLICATION_CREATED,
        ENTITY,
        application.id,
        new={**_snapshot(application), "access_levels": [lvl.name for lvl in application.access_levels]},
    )
    _commit_or_conflict()
    return application


def update_application(actor: User, app_id: int, data: dict[str, Any]) -> Application:
    """Partial update. Owners may change name/description; owner_id/is_active are admin-only."""
    application = get_application(app_id, actor)
    ensure_can_manage(actor, application)
    if {"owner_id", "is_active"} & data.keys():
        _ensure_admin(actor)

    old = _snapshot(application)
    if "name" in data:
        name = data["name"].strip()
        _ensure_name_free(name, exclude_id=application.id)
        application.name = name
    if "description" in data:
        application.description = data["description"]
    if "owner_id" in data:
        application.owner = _validate_owner(data["owner_id"])
    if "is_active" in data:
        application.is_active = data["is_active"]

    new = _snapshot(application)
    changed = {k for k in new if new[k] != old[k]}
    if changed:
        audit.log_action(
            actor,
            AuditAction.APPLICATION_UPDATED,
            ENTITY,
            application.id,
            old={k: old[k] for k in changed},
            new={k: new[k] for k in changed},
        )
    _commit_or_conflict()
    return application


def deactivate_application(actor: User, app_id: int) -> Application:
    """Admin-only soft delete. New requests are blocked; in-flight requests carry on."""
    _ensure_admin(actor)
    application = get_application(app_id, actor)
    if application.is_active:
        application.is_active = False
        audit.log_action(
            actor,
            AuditAction.APPLICATION_DEACTIVATED,
            ENTITY,
            application.id,
            old={"is_active": True},
            new={"is_active": False},
        )
        db.session.commit()
    return application


# --------------------------------------------------------------------------- access levels


def _get_level(application: Application, level_id: int) -> AppAccessLevel:
    level = next((lvl for lvl in application.access_levels if lvl.id == level_id), None)
    if level is None:
        raise NotFoundError("Access level not found")
    return level


def _ensure_level_name_free(application: Application, name: str, exclude_id: int | None = None) -> None:
    if any(lvl.name.lower() == name.lower() and lvl.id != exclude_id for lvl in application.access_levels):
        raise ConflictError("This application already has an access level with that name", code="NAME_TAKEN")


def add_access_level(actor: User, app_id: int, name: str) -> AppAccessLevel:
    application = get_application(app_id, actor)
    ensure_can_manage(actor, application)
    name = name.strip()
    _ensure_level_name_free(application, name)
    level = AppAccessLevel(application=application, name=name)
    db.session.add(level)
    db.session.flush()
    audit.log_action(
        actor,
        AuditAction.ACCESS_LEVEL_CREATED,
        "access_level",
        level.id,
        new={"application_id": application.id, "name": name},
    )
    _commit_or_conflict()
    return level


def rename_access_level(actor: User, app_id: int, level_id: int, name: str) -> AppAccessLevel:
    application = get_application(app_id, actor)
    ensure_can_manage(actor, application)
    level = _get_level(application, level_id)
    name = name.strip()
    _ensure_level_name_free(application, name, exclude_id=level.id)
    if name != level.name:
        audit.log_action(
            actor,
            AuditAction.ACCESS_LEVEL_UPDATED,
            "access_level",
            level.id,
            old={"name": level.name},
            new={"name": name},
        )
        level.name = name
    _commit_or_conflict()
    return level


def delete_access_level(actor: User, app_id: int, level_id: int) -> None:
    """Only levels that no request has ever used can be deleted (history must stay intact)."""
    application = get_application(app_id, actor)
    ensure_can_manage(actor, application)
    level = _get_level(application, level_id)
    in_use = db.session.scalar(select(exists().where(AccessRequest.access_level_id == level.id)))
    if in_use:
        raise ConflictError("This access level has requests and cannot be deleted", code="LEVEL_IN_USE")
    audit.log_action(
        actor,
        AuditAction.ACCESS_LEVEL_DELETED,
        "access_level",
        level.id,
        old={"application_id": application.id, "name": level.name},
    )
    application.access_levels.remove(level)  # delete-orphan cascade removes the row
    db.session.commit()


# --------------------------------------------------------------------------- workflow


def validate_steps(steps: list[dict[str, Any]]) -> None:
    """Business validation of a full workflow (types/ranges are checked by the schema).

    * 1..MAX_STEPS steps, ``step_order`` exactly 1..n (contiguous, no gaps or duplicates)
    * SPECIFIC_USER needs an active ``approver_user_id``; other types must not set one
    * ``sla_hours`` between 1 and 168
    """
    errors: dict[str, Any] = {}
    if not steps:
        raise InvalidInputError(details={"steps": ["At least one step is required."]})
    if len(steps) > MAX_STEPS:
        raise InvalidInputError(details={"steps": [f"At most {MAX_STEPS} steps are allowed."]})

    orders = sorted(s["step_order"] for s in steps)
    if orders != list(range(1, len(steps) + 1)):
        errors["steps"] = ["step_order values must be 1, 2, 3, ... with no gaps or duplicates."]

    for index, step in enumerate(steps):
        step_errors: dict[str, list[str]] = {}
        approver_type = ApproverType(step["approver_type"])
        user_id = step.get("approver_user_id")
        if approver_type == ApproverType.SPECIFIC_USER:
            user = db.session.get(User, user_id) if user_id is not None else None
            if user_id is None:
                step_errors["approver_user_id"] = ["Required for SPECIFIC_USER steps."]
            elif user is None or not user.is_active:
                step_errors["approver_user_id"] = ["Must be an active user."]
        elif user_id is not None:
            step_errors["approver_user_id"] = ["Only SPECIFIC_USER steps take an approver_user_id."]
        if not 1 <= step["sla_hours"] <= 168:
            step_errors["sla_hours"] = ["Must be between 1 and 168 hours."]
        if step_errors:
            errors[str(index)] = step_errors

    if errors:
        raise InvalidInputError("Invalid workflow", details=errors)


def replace_workflow(actor: User, app_id: int, steps: list[dict[str, Any]]) -> Application:
    """Atomically replace the application's whole ordered step list.

    The application row is locked (``FOR UPDATE``) so two concurrent edits cannot interleave;
    old steps are deleted and the new ones inserted in the same transaction.

    In-flight requests are NOT affected: each request copied its chain into
    ``access_requests.workflow_snapshot`` when it was submitted, and the engine only reads
    that snapshot. The new workflow applies to requests submitted from now on.
    """
    application = get_application(app_id, actor)
    ensure_can_manage(actor, application)
    validate_steps(steps)

    db.session.scalar(select(Application.id).where(Application.id == application.id).with_for_update())
    db.session.refresh(application, attribute_names=["workflow_steps"])
    old = _steps_snapshot(application)

    # Delete first, explicitly: the unit of work would otherwise INSERT before DELETE and
    # trip UNIQUE(application_id, step_order).
    db.session.execute(delete(WorkflowStep).where(WorkflowStep.application_id == application.id))
    db.session.expire(application, ["workflow_steps"])
    for step in sorted(steps, key=lambda s: s["step_order"]):
        is_specific = ApproverType(step["approver_type"]) == ApproverType.SPECIFIC_USER
        db.session.add(
            WorkflowStep(
                application_id=application.id,
                step_order=step["step_order"],
                approver_type=ApproverType(step["approver_type"]),
                approver_user_id=step.get("approver_user_id") if is_specific else None,
                sla_hours=step["sla_hours"],
            )
        )
    db.session.flush()
    db.session.refresh(application, attribute_names=["workflow_steps"])
    audit.log_action(
        actor,
        AuditAction.WORKFLOW_UPDATED,
        ENTITY,
        application.id,
        old={"steps": old},
        new={"steps": _steps_snapshot(application)},
    )
    db.session.commit()
    return application
