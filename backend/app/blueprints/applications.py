"""/api/applications: catalogue, access levels and approval workflows.

Reading the catalogue (and a workflow, for the "approval chain preview") is open to any
signed-in user. Changes need the admin or app_owner role; the service then checks that an
app_owner only touches their own applications.
"""

from flask import Blueprint, url_for
from flask_jwt_extended import jwt_required

from ..models import RoleName
from ..schemas.application import (
    AccessLevelInSchema,
    ApplicationCreateSchema,
    ApplicationListQuerySchema,
    ApplicationSchema,
    ApplicationUpdateSchema,
    WorkflowSchema,
    WorkflowStepSchema,
)
from ..schemas.common import NamedRefSchema
from ..services import applications as app_service
from ..utils.decorators import get_current_user, role_required
from ..utils.http import load_args, load_json, paginated

applications_bp = Blueprint("applications", __name__)

_app_schema = ApplicationSchema()
_apps_schema = ApplicationSchema(many=True)
_create_schema = ApplicationCreateSchema()
_update_schema = ApplicationUpdateSchema()
_list_query_schema = ApplicationListQuerySchema()
_level_in_schema = AccessLevelInSchema()
_level_schema = NamedRefSchema()
_workflow_in_schema = WorkflowSchema()
_steps_schema = WorkflowStepSchema(many=True)

MANAGERS = (RoleName.ADMIN, RoleName.APP_OWNER)


def _workflow_body(application) -> dict:
    return {"application_id": application.id, "steps": _steps_schema.dump(application.workflow_steps)}


@applications_bp.get("")
@jwt_required()
def list_applications():
    page = app_service.list_applications(get_current_user(), **load_args(_list_query_schema))
    return paginated(_apps_schema.dump(page.items), page.page, page.per_page, page.total)


@applications_bp.post("")
@role_required(RoleName.ADMIN)
def create_application():
    application = app_service.create_application(get_current_user(), load_json(_create_schema))
    location = url_for("applications.get_application", app_id=application.id)
    return _app_schema.dump(application), 201, {"Location": location}


@applications_bp.get("/<int:app_id>")
@jwt_required()
def get_application(app_id: int):
    return _app_schema.dump(app_service.get_application(app_id, get_current_user()))


@applications_bp.put("/<int:app_id>")
@role_required(*MANAGERS)
def update_application(app_id: int):
    data = load_json(_update_schema)
    return _app_schema.dump(app_service.update_application(get_current_user(), app_id, data))


@applications_bp.delete("/<int:app_id>")
@role_required(RoleName.ADMIN)
def deactivate_application(app_id: int):
    """Soft delete: the application is marked inactive, never removed."""
    return _app_schema.dump(app_service.deactivate_application(get_current_user(), app_id))


# --- access levels --------------------------------------------------------------------


@applications_bp.get("/<int:app_id>/access-levels")
@jwt_required()
def list_access_levels(app_id: int):
    application = app_service.get_application(app_id, get_current_user())
    return {"items": _level_schema.dump(application.access_levels, many=True)}


@applications_bp.post("/<int:app_id>/access-levels")
@role_required(*MANAGERS)
def add_access_level(app_id: int):
    data = load_json(_level_in_schema)
    level = app_service.add_access_level(get_current_user(), app_id, data["name"])
    return _level_schema.dump(level), 201


@applications_bp.put("/<int:app_id>/access-levels/<int:level_id>")
@role_required(*MANAGERS)
def rename_access_level(app_id: int, level_id: int):
    data = load_json(_level_in_schema)
    return _level_schema.dump(
        app_service.rename_access_level(get_current_user(), app_id, level_id, data["name"])
    )


@applications_bp.delete("/<int:app_id>/access-levels/<int:level_id>")
@role_required(*MANAGERS)
def delete_access_level(app_id: int, level_id: int):
    app_service.delete_access_level(get_current_user(), app_id, level_id)
    return "", 204


# --- workflow -------------------------------------------------------------------------


@applications_bp.get("/<int:app_id>/workflow")
@jwt_required()
def get_workflow(app_id: int):
    return _workflow_body(app_service.get_application(app_id, get_current_user()))


@applications_bp.put("/<int:app_id>/workflow")
@role_required(*MANAGERS)
def replace_workflow(app_id: int):
    data = load_json(_workflow_in_schema)
    application = app_service.replace_workflow(get_current_user(), app_id, data["steps"])
    return _workflow_body(application)
