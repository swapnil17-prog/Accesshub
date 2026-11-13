"""Access request input/output schemas."""

from __future__ import annotations

from typing import Any

from marshmallow import fields, validate

from ..models import AccessRequest, Approval, Decision, RequestStatus
from ..models.mixins import utcnow
from .base import BaseSchema
from .common import FlexibleDateTime, NamedRefSchema, PaginationQuerySchema, UserBriefSchema, not_blank

JUSTIFICATION_MIN = 20


class RequestCreateSchema(BaseSchema):
    application_id = fields.Integer(required=True, strict=True)
    access_level_id = fields.Integer(required=True, strict=True)
    justification = fields.String(
        required=True, validate=[validate.Length(max=2000), not_blank(JUSTIFICATION_MIN)]
    )
    duration_days = fields.Integer(
        load_default=None, allow_none=True, validate=validate.Range(min=1, max=365)
    )


class RequestListQuerySchema(PaginationQuerySchema):
    status = fields.Enum(RequestStatus, load_default=None)
    application_id = fields.Integer(load_default=None)
    requester_id = fields.Integer(load_default=None)
    created_from = FlexibleDateTime(data_key="from", load_default=None)
    created_to = FlexibleDateTime(data_key="to", end_of_day=True, load_default=None)
    mine = fields.Boolean(load_default=False)


def is_overdue(approval: Approval) -> bool:
    return approval.decision == Decision.PENDING and approval.due_at < utcnow()


class ApprovalTimelineSchema(BaseSchema):
    id = fields.Integer()
    step_order = fields.Integer()
    approver = fields.Nested(UserBriefSchema)
    decision = fields.Enum(Decision)
    comment = fields.String(allow_none=True)
    due_at = fields.DateTime()
    decided_at = fields.DateTime(allow_none=True)
    escalated = fields.Boolean()
    escalated_from = fields.Nested(UserBriefSchema, allow_none=True)
    is_overdue = fields.Function(is_overdue)
    created_at = fields.DateTime()


class RequestSummarySchema(BaseSchema):
    id = fields.Integer()
    requester = fields.Nested(UserBriefSchema)
    application = fields.Nested(NamedRefSchema)
    access_level = fields.Nested(NamedRefSchema)
    status = fields.Enum(RequestStatus)
    current_step = fields.Integer()
    total_steps = fields.Function(lambda r: len(r.workflow_snapshot))
    duration_days = fields.Integer(allow_none=True)
    expires_at = fields.DateTime(allow_none=True)
    created_at = fields.DateTime()
    updated_at = fields.DateTime()


def _steps(request: AccessRequest) -> list[dict[str, Any]]:
    return [
        {"step_order": s["step_order"], "approver_type": s["approver_type"], "sla_hours": s["sla_hours"]}
        for s in sorted(request.workflow_snapshot, key=lambda s: s["step_order"])
    ]


class RequestDetailSchema(RequestSummarySchema):
    justification = fields.String()
    steps = fields.Function(_steps)
    approvals = fields.List(fields.Nested(ApprovalTimelineSchema))
