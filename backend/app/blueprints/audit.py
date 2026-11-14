"""/api/audit and /api/reports: read-only compliance views (auditor + admin).

There are deliberately no update or delete endpoints for audit logs.
"""

from flask import Blueprint, Response, stream_with_context

from ..models import RoleName
from ..models.mixins import utcnow
from ..schemas.audit import AuditExportQuerySchema, AuditLogSchema, AuditQuerySchema
from ..services import reports
from ..utils.decorators import get_current_user, role_required
from ..utils.http import load_args, paginated

audit_bp = Blueprint("audit", __name__)
reports_bp = Blueprint("reports", __name__)

READERS = (RoleName.AUDITOR, RoleName.ADMIN)
_logs_schema = AuditLogSchema(many=True)


@audit_bp.get("")
@role_required(*READERS)
def list_audit():
    page = reports.list_audit(**load_args(AuditQuerySchema()))
    return paginated(_logs_schema.dump(page.items), page.page, page.per_page, page.total)


@audit_bp.get("/export.csv")
@role_required(*READERS)
def export_csv():
    rows = reports.export_csv(get_current_user(), **load_args(AuditExportQuerySchema()))
    filename = f"audit-{utcnow():%Y%m%d-%H%M%S}.csv"
    return Response(
        stream_with_context(rows),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )


@reports_bp.get("/summary")
@role_required(*READERS)
def summary():
    return reports.summary()
