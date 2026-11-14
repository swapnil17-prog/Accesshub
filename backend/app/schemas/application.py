"""Application, access level and workflow schemas."""

from marshmallow import fields, validate

from ..models import ApproverType
from .base import BaseSchema
from .common import NamedRefSchema, PaginationQuerySchema, UserBriefSchema, not_blank

_name = [validate.Length(max=120), not_blank(1)]


class WorkflowStepSchema(BaseSchema):
    """Used for both input (PUT /workflow) and output."""

    step_order = fields.Integer(required=True, strict=True)
    approver_type = fields.Enum(ApproverType, required=True)
    approver_user_id = fields.Integer(load_default=None, allow_none=True, strict=True)
    approver_user = fields.Nested(UserBriefSchema, dump_only=True, allow_none=True)
    sla_hours = fields.Integer(load_default=24, strict=True, validate=validate.Range(min=1, max=168))


class WorkflowSchema(BaseSchema):
    steps = fields.List(fields.Nested(WorkflowStepSchema), required=True)


class ApplicationSchema(BaseSchema):
    id = fields.Integer(dump_only=True)
    name = fields.String()
    description = fields.String(allow_none=True)
    owner = fields.Nested(UserBriefSchema)
    is_active = fields.Boolean()
    access_levels = fields.List(fields.Nested(NamedRefSchema))
    workflow_steps = fields.List(fields.Nested(WorkflowStepSchema))
    created_at = fields.DateTime()
    updated_at = fields.DateTime()


class ApplicationCreateSchema(BaseSchema):
    name = fields.String(required=True, validate=_name)
    description = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=2000))
    owner_id = fields.Integer(required=True, strict=True)
    access_levels = fields.List(fields.String(validate=_name), load_default=list)


class ApplicationUpdateSchema(BaseSchema):
    """All fields optional; only the ones sent are changed."""

    name = fields.String(validate=_name)
    description = fields.String(allow_none=True, validate=validate.Length(max=2000))
    owner_id = fields.Integer(strict=True)
    is_active = fields.Boolean()


class AccessLevelInSchema(BaseSchema):
    name = fields.String(required=True, validate=_name)


class ApplicationListQuerySchema(PaginationQuerySchema):
    q = fields.String(load_default=None)
    include_inactive = fields.Boolean(load_default=False)
