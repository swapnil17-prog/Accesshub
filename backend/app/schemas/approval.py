"""Approval input/output schemas."""

from marshmallow import fields, validate

from .base import BaseSchema
from .request import RequestSummarySchema, is_overdue


class DecisionSchema(BaseSchema):
    """Body of approve/reject. The service enforces "comment required" for reject."""

    comment = fields.String(load_default=None, allow_none=True, validate=validate.Length(max=2000))


class InboxRequestSchema(RequestSummarySchema):
    justification = fields.String()


class InboxItemSchema(BaseSchema):
    id = fields.Integer()
    step_order = fields.Integer()
    assigned_at = fields.DateTime(attribute="created_at")
    due_at = fields.DateTime()
    is_overdue = fields.Function(is_overdue)
    escalated = fields.Boolean()
    request = fields.Nested(InboxRequestSchema)
