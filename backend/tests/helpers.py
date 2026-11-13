"""Builders for workflow tests: a small org chart and applications with given workflows."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from flask_jwt_extended import create_access_token
from sqlalchemy import select

from app.extensions import db
from app.models import Application, ApproverType, AuditLog, User, WorkflowStep
from tests.factories import AccessLevelFactory, ApplicationFactory, UserFactory


@dataclass
class Org:
    """admin <- manager <- employee/colleague ; admin <- owner ; specialist (no manager)."""

    admin: User
    manager: User
    owner: User
    employee: User
    colleague: User
    specialist: User
    auditor: User


def make_org() -> Org:
    admin = UserFactory(name="Ada Admin", roles=["employee", "admin"])
    manager = UserFactory(name="Max Manager", roles=["employee", "manager"], manager=admin)
    owner = UserFactory(name="Olga Owner", roles=["employee", "app_owner"], manager=admin)
    employee = UserFactory(name="Eve Employee", roles=["employee"], manager=manager)
    colleague = UserFactory(name="Carl Colleague", roles=["employee"], manager=manager)
    specialist = UserFactory(name="Sam Specialist", roles=["employee"])
    auditor = UserFactory(name="Aud Itor", roles=["employee", "auditor"], manager=admin)
    return Org(admin, manager, owner, employee, colleague, specialist, auditor)


StepDef = tuple[ApproverType, User | None, int]


def make_app(
    owner: User,
    steps: Sequence[StepDef] = ((ApproverType.MANAGER, None, 24),),
    levels: Sequence[str] = ("Read", "Write"),
    **kwargs,
) -> Application:
    application = ApplicationFactory(owner=owner, **kwargs)
    for name in levels:
        AccessLevelFactory(application=application, name=name)
    for order, (approver_type, user, sla) in enumerate(steps, start=1):
        db.session.add(
            WorkflowStep(
                application=application,
                step_order=order,
                approver_type=approver_type,
                approver_user=user,
                sla_hours=sla,
            )
        )
    db.session.commit()
    db.session.refresh(application)
    return application


def actions(entity_type: str | None = None, entity_id: int | None = None) -> list[str]:
    """Audit actions in insertion order, optionally for one entity."""
    stmt = select(AuditLog.action).order_by(AuditLog.id)
    if entity_type is not None:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        stmt = stmt.where(AuditLog.entity_id == entity_id)
    return list(db.session.scalars(stmt))


def auth(user: User) -> dict[str, str]:
    """Authorization header with a real access token for ``user``."""
    token = create_access_token(identity=str(user.id), additional_claims={"roles": user.role_names})
    return {"Authorization": f"Bearer {token}"}
