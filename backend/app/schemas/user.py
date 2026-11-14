from marshmallow import fields, validate

from ..models import RoleName
from .base import BaseSchema
from .common import PaginationQuerySchema, QuerySchema, UserBriefSchema, not_blank

ROLE_NAMES = [r.value for r in RoleName]
PASSWORD_MIN = 8


class UserSchema(BaseSchema):
    """Public user representation. password_hash is never exposed."""

    id = fields.Integer(dump_only=True)
    name = fields.String()
    email = fields.Email()
    department = fields.String(allow_none=True)
    manager_id = fields.Integer(allow_none=True)
    is_active = fields.Boolean()
    roles = fields.Function(lambda user: user.role_names, dump_only=True)
    created_at = fields.DateTime(dump_only=True)


class UserAdminSchema(UserSchema):
    manager = fields.Nested(UserBriefSchema, allow_none=True)
    updated_at = fields.DateTime(dump_only=True)


_name = [validate.Length(max=120), not_blank(1)]
_password = validate.Length(min=PASSWORD_MIN, max=128)


class UserCreateSchema(BaseSchema):
    name = fields.String(required=True, validate=_name)
    email = fields.Email(required=True, validate=validate.Length(max=255))
    password = fields.String(required=True, load_only=True, validate=_password)
    department = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=120))
    manager_id = fields.Integer(load_default=None, allow_none=True, strict=True)
    roles = fields.List(fields.String(validate=validate.OneOf(ROLE_NAMES)), load_default=lambda: ["employee"])


class UserUpdateSchema(BaseSchema):
    """All fields optional; only the ones sent are changed."""

    name = fields.String(validate=_name)
    email = fields.Email(validate=validate.Length(max=255))
    password = fields.String(load_only=True, validate=_password)
    department = fields.String(allow_none=True, validate=validate.Length(max=120))
    manager_id = fields.Integer(allow_none=True, strict=True)
    is_active = fields.Boolean()


class RolesSchema(BaseSchema):
    roles = fields.List(fields.String(validate=validate.OneOf(ROLE_NAMES)), required=True)


class UserListQuerySchema(PaginationQuerySchema):
    q = fields.String(load_default=None)
    role = fields.String(load_default=None, validate=validate.OneOf(ROLE_NAMES))
    is_active = fields.Boolean(load_default=None)


class UserLookupQuerySchema(QuerySchema):
    q = fields.String(load_default=None)
