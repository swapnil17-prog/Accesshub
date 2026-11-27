from marshmallow import fields, validate

from .base import BaseSchema


class LoginSchema(BaseSchema):
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True, validate=validate.Length(min=1, max=128))


class LogoutSchema(BaseSchema):
    refresh_token = fields.String(load_default=None)


class ChangePasswordSchema(BaseSchema):
    current_password = fields.String(required=True, load_only=True, validate=validate.Length(min=1, max=128))
    new_password = fields.String(required=True, load_only=True, validate=validate.Length(min=1, max=128))
