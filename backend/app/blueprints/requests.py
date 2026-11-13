"""/api/requests: submit, list, view and cancel access requests.

Routes only parse input, call a service and serialize the result.
"""

from flask import Blueprint, url_for
from flask_jwt_extended import jwt_required

from ..models import RoleName
from ..schemas.request import (
    RequestCreateSchema,
    RequestDetailSchema,
    RequestListQuerySchema,
    RequestSummarySchema,
)
from ..services import requests as request_queries
from ..services import workflow
from ..utils.decorators import get_current_user, role_required
from ..utils.http import load_args, load_json, paginated

requests_bp = Blueprint("requests", __name__)

_create_schema = RequestCreateSchema()
_list_query_schema = RequestListQuerySchema()
_summary_schema = RequestSummarySchema(many=True)
_detail_schema = RequestDetailSchema()


def _detail(request_id: int) -> dict:
    return _detail_schema.dump(request_queries.get_request_for_user(request_id, get_current_user()))


@requests_bp.post("")
@role_required(RoleName.EMPLOYEE)
def create_request():
    data = load_json(_create_schema)
    created = workflow.submit_request(
        get_current_user(),
        data["application_id"],
        data["access_level_id"],
        data["justification"],
        data["duration_days"],
    )
    location = url_for("requests.get_request", request_id=created.id)
    return _detail(created.id), 201, {"Location": location}


@requests_bp.get("")
@jwt_required()
def list_requests():
    args = load_args(_list_query_schema)
    page = request_queries.list_requests(get_current_user(), **args)
    return paginated(_summary_schema.dump(page.items), page.page, page.per_page, page.total)


@requests_bp.get("/<int:request_id>")
@jwt_required()
def get_request(request_id: int):
    return _detail(request_id)


@requests_bp.post("/<int:request_id>/cancel")
@jwt_required()
def cancel_request(request_id: int):
    user = get_current_user()
    access_request = request_queries.get_request_for_user(request_id, user)
    workflow.cancel(access_request, user)
    return _detail(request_id)
