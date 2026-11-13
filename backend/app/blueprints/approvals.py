"""/api/approvals: the approver's inbox and approve/reject decisions.

These endpoints need a valid token but no specific role: whoever the workflow assigned
(a manager, an app owner, a SPECIFIC_USER who may be a plain employee, or an admin
fallback) must be able to act. The real check is object-level, in the workflow service:
only the assigned approver (approval.approver_id == current user) can decide.
"""

from flask import Blueprint
from flask_jwt_extended import jwt_required

from ..schemas.approval import DecisionSchema, InboxItemSchema
from ..schemas.common import PaginationQuerySchema
from ..schemas.request import RequestDetailSchema
from ..services import requests as request_queries
from ..services import workflow
from ..utils.decorators import get_current_user
from ..utils.http import load_args, load_json_optional, paginated

approvals_bp = Blueprint("approvals", __name__)

_page_schema = PaginationQuerySchema()
_inbox_schema = InboxItemSchema(many=True)
_decision_schema = DecisionSchema()
_detail_schema = RequestDetailSchema()


@approvals_bp.get("/inbox")
@jwt_required()
def inbox():
    args = load_args(_page_schema)
    page = request_queries.inbox(get_current_user(), **args)
    return paginated(_inbox_schema.dump(page.items), page.page, page.per_page, page.total)


@approvals_bp.post("/<int:approval_id>/approve")
@jwt_required()
def approve(approval_id: int):
    data = load_json_optional(_decision_schema)
    user = get_current_user()
    result = workflow.approve(workflow.get_approval(approval_id), user, data["comment"])
    return _detail_schema.dump(request_queries.get_request_for_user(result.id, user))


@approvals_bp.post("/<int:approval_id>/reject")
@jwt_required()
def reject(approval_id: int):
    data = load_json_optional(_decision_schema)
    user = get_current_user()
    result = workflow.reject(workflow.get_approval(approval_id), user, data["comment"])
    return _detail_schema.dump(request_queries.get_request_for_user(result.id, user))
