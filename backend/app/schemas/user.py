from marshmallow import fields

from .base import BaseSchema


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
