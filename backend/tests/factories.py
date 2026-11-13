"""factory-boy factories. Objects are committed so HTTP calls in the same test can see them."""

from datetime import timedelta

import factory
from factory.alchemy import SQLAlchemyModelFactory
from sqlalchemy import select
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import (
    AccessRequest,
    AppAccessLevel,
    Application,
    Approval,
    ApproverType,
    RequestStatus,
    Role,
    User,
    WorkflowStep,
)
from app.models.mixins import utcnow

TEST_PASSWORD = "Password@123"
_PASSWORD_HASH = generate_password_hash(TEST_PASSWORD, method="pbkdf2:sha256:1000")  # fast, tests only


def get_or_create_role(name: str) -> Role:
    role = db.session.scalar(select(Role).where(Role.name == str(name)))
    if role is None:
        role = Role(name=str(name))
        db.session.add(role)
        db.session.flush()
    return role


class BaseFactory(SQLAlchemyModelFactory):
    class Meta:
        abstract = True
        sqlalchemy_session_factory = lambda: db.session  # noqa: E731
        sqlalchemy_session_persistence = "commit"


class UserFactory(BaseFactory):
    class Meta:
        model = User

    name = factory.Faker("name")
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    password_hash = _PASSWORD_HASH
    department = "Engineering"
    is_active = True

    @factory.post_generation
    def roles(self, create: bool, extracted: list[str] | None, **_kwargs) -> None:
        """``UserFactory(roles=["admin"])``; defaults to ["employee"]."""
        for name in extracted if extracted is not None else ["employee"]:
            self.roles.append(get_or_create_role(name))


class ApplicationFactory(BaseFactory):
    class Meta:
        model = Application

    name = factory.Sequence(lambda n: f"App {n}")
    description = "Test application"
    owner = factory.SubFactory(UserFactory)


class AccessLevelFactory(BaseFactory):
    class Meta:
        model = AppAccessLevel

    application = factory.SubFactory(ApplicationFactory)
    name = factory.Sequence(lambda n: f"Level {n}")


class WorkflowStepFactory(BaseFactory):
    class Meta:
        model = WorkflowStep

    application = factory.SubFactory(ApplicationFactory)
    step_order = 1
    approver_type = ApproverType.MANAGER
    sla_hours = 24


class AccessRequestFactory(BaseFactory):
    class Meta:
        model = AccessRequest

    requester = factory.SubFactory(UserFactory)
    application = factory.SubFactory(ApplicationFactory)
    access_level = factory.SubFactory(AccessLevelFactory, application=factory.SelfAttribute("..application"))
    justification = "I need this access to do my job properly."
    status = RequestStatus.PENDING
    current_step = 1


class ApprovalFactory(BaseFactory):
    class Meta:
        model = Approval

    request = factory.SubFactory(AccessRequestFactory)
    step_order = 1
    approver = factory.SubFactory(UserFactory)
    due_at = factory.LazyFunction(lambda: utcnow() + timedelta(hours=24))
