"""GET /api/health — liveness + DB connectivity."""

from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from ..extensions import db

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health():
    """Returns 503 if the database is unreachable."""
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify(status="ok", db="ok"), 200
    except Exception:  # noqa: BLE001 - any DB failure means "unhealthy"
        current_app.logger.exception("Health check: database ping failed")
        db.session.rollback()
        return jsonify(status="degraded", db="error"), 503
