"""Demo data for `flask seed`. Idempotent: running it again changes nothing.

* Roles, users, apps, access levels: created only if missing (matched by natural key).
* Workflow steps: created only for apps that have no steps yet.
* Historical requests (~40, mixed states, with approvals and audit rows): created only
  when the access_requests table is empty. Generated with a fixed random seed.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select

from .extensions import db
from .models import (
    AccessRequest,
    AppAccessLevel,
    Application,
    Approval,
    ApproverType,
    AuditAction,
    AuditLog,
    Decision,
    RequestStatus,
    Role,
    RoleName,
    User,
    WorkflowStep,
)
from .models.mixins import utcnow
from .models.user import hash_password

DEMO_PASSWORD = "Password@123"
DOMAIN = "accesshub.dev"

# (name, email local part, department, extra roles). Everyone also gets "employee".
CORE_USERS: list[tuple[str, str, str, list[RoleName]]] = [
    ("Alex Admin", "admin", "IT", [RoleName.ADMIN]),
    ("Avery Auditor", "auditor", "Compliance", [RoleName.AUDITOR]),
    ("Morgan Manager", "manager", "Engineering", [RoleName.MANAGER]),
    ("Owen Owner", "owner", "IT", [RoleName.APP_OWNER]),
    ("Emery Employee", "employee", "Engineering", []),
]

EXTRA_EMPLOYEES: list[tuple[str, str]] = [
    ("Priya Sharma", "Engineering"),
    ("Liam Chen", "Engineering"),
    ("Sofia Rossi", "Sales"),
    ("Noah Williams", "Sales"),
    ("Aisha Khan", "Finance"),
    ("Mateo Garcia", "Finance"),
    ("Hana Sato", "HR"),
    ("Jonas Muller", "Engineering"),
    ("Grace Okafor", "Marketing"),
    ("Ravi Patel", "Support"),
]

# steps: (approver type, specific user's email local part or None, SLA hours)
APPS: list[dict[str, Any]] = [
    {
        "name": "Jira",
        "description": "Issue and project tracking.",
        "levels": ["Viewer", "Developer", "Project Admin"],
        "steps": [(ApproverType.MANAGER, None, 24)],
    },
    {
        "name": "Salesforce",
        "description": "Customer relationship management.",
        "levels": ["Read Only", "Sales User"],
        "steps": [(ApproverType.MANAGER, None, 24), (ApproverType.APP_OWNER, None, 48)],
    },
    {
        "name": "GitHub",
        "description": "Source code hosting and code review.",
        "levels": ["Read", "Write", "Maintain"],
        "steps": [(ApproverType.MANAGER, None, 24), (ApproverType.APP_OWNER, None, 24)],
    },
    {
        "name": "AWS Console",
        "description": "Cloud infrastructure management.",
        "levels": ["ReadOnly", "PowerUser", "Administrator"],
        "steps": [
            (ApproverType.MANAGER, None, 24),
            (ApproverType.APP_OWNER, None, 24),
            (ApproverType.SPECIFIC_USER, "admin", 8),
        ],
    },
    {
        "name": "Workday",
        "description": "HR, payroll and time off.",
        "levels": ["Employee Self-Service", "HR Analyst"],
        "steps": [(ApproverType.APP_OWNER, None, 48)],
    },
]

JUSTIFICATIONS = [
    "Joining the platform team and need to work on sprint tickets.",
    "Required to review customer accounts for the quarterly business review.",
    "Need to push fixes to the payments service repository.",
    "Investigating production incidents in the staging and prod accounts.",
    "Updating my bank details and viewing payslips.",
    "Covering for a colleague on leave for the next two weeks.",
    "Preparing the audit evidence pack for the finance team.",
    "Onboarding as a new hire; my manager asked me to request this.",
    "Need read access to build the monthly reporting dashboard.",
    "Running the migration project and need elevated permissions temporarily.",
]
REJECT_COMMENTS = [
    "Not required for your current role.",
    "Please use the shared read-only access instead.",
    "Justification is not sufficient for this level.",
]

# 14 + 8 + 5 + 9 + 4 = 40 historical requests
STATUS_MIX = (
    [RequestStatus.APPROVED] * 14
    + [RequestStatus.REJECTED] * 8
    + [RequestStatus.CANCELLED] * 5
    + [RequestStatus.PENDING] * 9
    + [RequestStatus.EXPIRED] * 4
)


def _email(local: str) -> str:
    return f"{local}@{DOMAIN}"


def _get_or_create_role(name: str) -> Role:
    role = db.session.scalar(select(Role).where(Role.name == name))
    if role is None:
        role = Role(name=name)
        db.session.add(role)
    return role


def _get_or_create_user(name: str, email: str, department: str, password_hash: str) -> User:
    user = db.session.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(name=name, email=email, department=department, password_hash=password_hash)
        db.session.add(user)
    return user


def _ensure_roles(user: User, roles: list[Role]) -> None:
    for role in roles:
        if role not in user.roles:
            user.roles.append(role)


def _seed_users(roles: dict[str, Role]) -> dict[str, User]:
    password_hash = hash_password(DEMO_PASSWORD)  # hash once; scrypt is deliberately slow

    users: dict[str, User] = {}
    for name, local, dept, extra_roles in CORE_USERS:
        user = _get_or_create_user(name, _email(local), dept, password_hash)
        _ensure_roles(user, [roles[RoleName.EMPLOYEE], *(roles[r] for r in extra_roles)])
        users[local] = user

    for name, dept in EXTRA_EMPLOYEES:
        local = name.lower().replace(" ", ".")
        user = _get_or_create_user(name, _email(local), dept, password_hash)
        _ensure_roles(user, [roles[RoleName.EMPLOYEE]])
        users[local] = user

    # Reporting lines (only filled in if unset, so manual edits survive a re-seed).
    admin, manager = users["admin"], users["manager"]
    for local, user in users.items():
        if user.manager_id is None and user.manager is None:
            if local in {"auditor", "manager", "owner"}:
                user.manager = admin
            elif local != "admin":
                user.manager = manager
    return users


def _seed_apps(users: dict[str, User]) -> list[Application]:
    apps: list[Application] = []
    for spec in APPS:
        app = db.session.scalar(select(Application).where(Application.name == spec["name"]))
        if app is None:
            app = Application(name=spec["name"], description=spec["description"], owner=users["owner"])
            db.session.add(app)
        existing_levels = {level.name for level in app.access_levels}
        for level_name in spec["levels"]:
            if level_name not in existing_levels:
                app.access_levels.append(AppAccessLevel(name=level_name))
        if not app.workflow_steps:
            for order, (approver_type, user_local, sla) in enumerate(spec["steps"], start=1):
                app.workflow_steps.append(
                    WorkflowStep(
                        step_order=order,
                        approver_type=approver_type,
                        approver_user=users[user_local] if user_local else None,
                        sla_hours=sla,
                    )
                )
        apps.append(app)
    return apps


def _resolve_approver(step: WorkflowStep, requester: User, app: Application, admin: User) -> User:
    """Seed-local mirror of the workflow engine's resolve_approver (no self-approval)."""
    if step.approver_type == ApproverType.MANAGER:
        approver = requester.manager or admin
    elif step.approver_type == ApproverType.APP_OWNER:
        approver = app.owner
    else:
        approver = step.approver_user or admin
    if approver is requester:
        approver = requester.manager or admin
    return approver


class _HistoryBuilder:
    def __init__(self, rng: random.Random, admin: User, now: datetime) -> None:
        self.rng = rng
        self.admin = admin
        self.now = now

    def audit(
        self,
        actor: User | None,
        action: AuditAction,
        entity_type: str,
        entity_id: int,
        at: datetime,
        new: dict[str, Any] | None = None,
    ) -> None:
        db.session.add(
            AuditLog(
                actor=actor,
                action=action.value,
                entity_type=entity_type,
                entity_id=entity_id,
                new_value=new,
                created_at=at,
            )
        )

    def build(self, status: RequestStatus, requester: User, app: Application, level: AppAccessLevel) -> None:
        rng, now = self.rng, self.now
        steps = list(app.workflow_steps)
        n = len(steps)

        if status == RequestStatus.PENDING:
            created = now - timedelta(days=rng.randint(0, 3), hours=rng.randint(1, 20))
        elif status == RequestStatus.EXPIRED:
            created = now - timedelta(days=rng.randint(70, 120))
        else:
            created = now - timedelta(days=rng.randint(4, 90), hours=rng.randint(0, 23))

        # How far the chain got, and what happened at the last step reached.
        if status in (RequestStatus.APPROVED, RequestStatus.EXPIRED):
            last_step, last_decision = n, Decision.APPROVED
        elif status == RequestStatus.REJECTED:
            last_step, last_decision = rng.randint(1, n), Decision.REJECTED
        elif status == RequestStatus.CANCELLED:
            last_step, last_decision = rng.randint(1, n), Decision.SKIPPED
        else:
            last_step, last_decision = rng.randint(1, n), Decision.PENDING

        duration = None
        if status == RequestStatus.EXPIRED:
            duration = 30
        elif status in (RequestStatus.APPROVED, RequestStatus.PENDING):
            duration = rng.choice([None, None, 90, 180, 365])

        request = AccessRequest(
            requester=requester,
            application=app,
            access_level=level,
            justification=rng.choice(JUSTIFICATIONS),
            status=status,
            current_step=last_step,
            duration_days=duration,
            created_at=created,
            updated_at=created,
        )
        db.session.add(request)
        db.session.flush()
        self.audit(
            requester,
            AuditAction.REQUEST_CREATED,
            "access_request",
            request.id,
            created,
            {"application": app.name, "access_level": level.name},
        )

        t = created
        for step in steps[:last_step]:
            approver = _resolve_approver(step, requester, app, self.admin)
            started = t
            decision = Decision.APPROVED if step.step_order < last_step else last_decision
            approval = Approval(
                request=request,
                step_order=step.step_order,
                approver=approver,
                decision=decision,
                due_at=started + timedelta(hours=step.sla_hours),
                created_at=started,
                updated_at=started,
            )
            db.session.add(approval)
            if decision == Decision.PENDING:
                break

            t = min(
                started + timedelta(hours=rng.randint(1, step.sla_hours + 12)), now - timedelta(minutes=5)
            )
            approval.updated_at = t
            if decision == Decision.SKIPPED:
                db.session.flush()
                self.audit(requester, AuditAction.REQUEST_CANCELLED, "access_request", request.id, t)
                break

            approval.decided_at = t
            approval.comment = rng.choice(REJECT_COMMENTS) if decision == Decision.REJECTED else "Approved."
            db.session.flush()
            action = (
                AuditAction.APPROVAL_APPROVED
                if decision == Decision.APPROVED
                else AuditAction.APPROVAL_REJECTED
            )
            self.audit(approver, action, "approval", approval.id, t, {"comment": approval.comment})
            if decision == Decision.REJECTED:
                self.audit(approver, AuditAction.REQUEST_REJECTED, "access_request", request.id, t)
            elif step.step_order == n:
                self.audit(approver, AuditAction.REQUEST_APPROVED, "access_request", request.id, t)

        if status in (RequestStatus.APPROVED, RequestStatus.EXPIRED) and duration:
            request.expires_at = t + timedelta(days=duration)
            if status == RequestStatus.APPROVED and request.expires_at <= now:
                request.duration_days, request.expires_at = None, None
        if status == RequestStatus.EXPIRED:
            assert request.expires_at is not None
            self.audit(None, AuditAction.REQUEST_EXPIRED, "access_request", request.id, request.expires_at)
            t = request.expires_at
        request.updated_at = t


def _seed_history(users: dict[str, User], apps: list[Application]) -> int:
    if db.session.scalar(select(func.count(AccessRequest.id))):
        return 0

    rng = random.Random(20241112)
    requesters = [u for local, u in users.items() if local not in {"admin", "auditor", "manager", "owner"}]
    builder = _HistoryBuilder(rng, users["admin"], utcnow())
    statuses = STATUS_MIX[:]
    rng.shuffle(statuses)
    pending_keys: set[tuple[int, int, int]] = set()

    for status in statuses:
        while True:
            requester = rng.choice(requesters)
            app = rng.choice(apps)
            level = rng.choice(app.access_levels)
            key = (requester.id, app.id, level.id)
            if status != RequestStatus.PENDING or key not in pending_keys:
                break
        if status == RequestStatus.PENDING:
            pending_keys.add(key)
        builder.build(status, requester, app, level)
    return len(statuses)


def seed_demo_data() -> dict[str, int]:
    """Create demo roles, users, applications, workflows and history. Safe to run repeatedly."""
    roles = {name.value: _get_or_create_role(name.value) for name in RoleName}
    users = _seed_users(roles)
    apps = _seed_apps(users)
    db.session.flush()
    created_requests = _seed_history(users, apps)
    db.session.commit()

    def count(model: type) -> int:
        return db.session.scalar(select(func.count()).select_from(model)) or 0

    return {
        "roles": count(Role),
        "users": count(User),
        "applications": count(Application),
        "access_levels": count(AppAccessLevel),
        "workflow_steps": count(WorkflowStep),
        "access_requests": count(AccessRequest),
        "approvals": count(Approval),
        "audit_logs": count(AuditLog),
        "requests_created_this_run": created_requests,
    }
