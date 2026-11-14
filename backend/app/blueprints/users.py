"""/api/users: user administration (admin only), plus a small lookup for pickers."""

from flask import Blueprint, url_for

from ..models import RoleName
from ..schemas.common import UserBriefSchema
from ..schemas.user import (
    RolesSchema,
    UserAdminSchema,
    UserCreateSchema,
    UserListQuerySchema,
    UserLookupQuerySchema,
    UserUpdateSchema,
)
from ..services import users as user_service
from ..utils.decorators import get_current_user, role_required
from ..utils.http import load_args, load_json, paginated

users_bp = Blueprint("users", __name__)

_user_schema = UserAdminSchema()
_users_schema = UserAdminSchema(many=True)
_brief_schema = UserBriefSchema(many=True)


@users_bp.get("")
@role_required(RoleName.ADMIN)
def list_users():
    page = user_service.list_users(**load_args(UserListQuerySchema()))
    return paginated(_users_schema.dump(page.items), page.page, page.per_page, page.total)


@users_bp.get("/lookup")
@role_required(RoleName.ADMIN, RoleName.APP_OWNER)
def lookup_users():
    """Brief active-user search for the workflow builder's SPECIFIC_USER picker."""
    args = load_args(UserLookupQuerySchema())
    return {"items": _brief_schema.dump(user_service.lookup_users(args["q"]))}


@users_bp.post("")
@role_required(RoleName.ADMIN)
def create_user():
    user = user_service.create_user(get_current_user(), load_json(UserCreateSchema()))
    return _user_schema.dump(user), 201, {"Location": url_for("users.get_user", user_id=user.id)}


@users_bp.get("/<int:user_id>")
@role_required(RoleName.ADMIN)
def get_user(user_id: int):
    return _user_schema.dump(user_service.get_user(user_id))


@users_bp.put("/<int:user_id>")
@role_required(RoleName.ADMIN)
def update_user(user_id: int):
    """Partial update; send ``{"is_active": false}`` to deactivate (users are never deleted)."""
    user = user_service.update_user(get_current_user(), user_id, load_json(UserUpdateSchema()))
    return _user_schema.dump(user)


@users_bp.put("/<int:user_id>/roles")
@role_required(RoleName.ADMIN)
def set_roles(user_id: int):
    data = load_json(RolesSchema())
    return _user_schema.dump(user_service.set_roles(get_current_user(), user_id, data["roles"]))
