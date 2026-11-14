from marshmallow import fields, validate

from .base import BaseSchema
from .common import FlexibleDateTime, PaginationQuerySchema, QuerySchema, UserBriefSchema


class AuditLogSchema(BaseSchema):
    id = fields.Integer()
    created_at = fields.DateTime()
    actor = fields.Nested(UserBriefSchema, allow_none=True)  # null = system
    action = fields.String()
    entity_type = fields.String()
    entity_id = fields.Integer(allow_none=True)
    old_value = fields.Raw(allow_none=True)
    new_value = fields.Raw(allow_none=True)
    ip_address = fields.String(allow_none=True)
    user_agent = fields.String(allow_none=True)


class _AuditFilters:
    """Shared filters for the list and the CSV export. ``actor`` is a user id or "system"."""

    actor = fields.String(load_default=None, validate=validate.Regexp(r"^(\d+|system)$"))
    entity_type = fields.String(load_default=None)
    entity_id = fields.Integer(load_default=None)
    action = fields.String(load_default=None)
    created_from = FlexibleDateTime(data_key="from", load_default=None)
    created_to = FlexibleDateTime(data_key="to", end_of_day=True, load_default=None)


class AuditQuerySchema(PaginationQuerySchema, _AuditFilters):
    per_page = fields.Integer(load_default=50, validate=validate.Range(min=1, max=200))


class AuditExportQuerySchema(QuerySchema, _AuditFilters):
    pass
