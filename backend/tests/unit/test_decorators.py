import pytest
from flask_jwt_extended import create_access_token
from flask_jwt_extended.exceptions import NoAuthorizationError, UserLookupError

from app.errors import ForbiddenError
from app.utils.decorators import get_current_user, role_required
from tests.factories import UserFactory


@role_required("admin")
def admin_only():
    return "ok"


@role_required("auditor", "admin")
def auditor_or_admin():
    return get_current_user().email


def _call(app, view, user=None):
    headers = {}
    if user is not None:
        headers["Authorization"] = f"Bearer {create_access_token(identity=str(user.id))}"
    with app.test_request_context("/", headers=headers):
        return view()


def test_allows_user_with_role(app, db):
    assert _call(app, admin_only, UserFactory(roles=["employee", "admin"])) == "ok"


def test_denies_user_without_role(app, db):
    with pytest.raises(ForbiddenError) as exc:
        _call(app, admin_only, UserFactory(roles=["employee"]))
    assert exc.value.details == {"required_roles": ["admin"]}


def test_any_of_several_roles(app, db):
    user = UserFactory(roles=["auditor"])
    assert _call(app, auditor_or_admin, user) == user.email


def test_requires_token(app, db):
    with pytest.raises(NoAuthorizationError):
        _call(app, admin_only)


def test_inactive_user_rejected(app, db):
    with pytest.raises(UserLookupError):
        _call(app, admin_only, UserFactory(roles=["admin"], is_active=False))


def test_uses_current_db_roles_not_stale_claims(app, db):
    user = UserFactory(roles=["admin"])
    token = create_access_token(identity=str(user.id), additional_claims={"roles": ["admin"]})
    user.roles.clear()
    db.session.commit()
    with app.test_request_context("/", headers={"Authorization": f"Bearer {token}"}):
        with pytest.raises(ForbiddenError):
            admin_only()


def test_needs_at_least_one_role():
    with pytest.raises(ValueError):
        role_required()
