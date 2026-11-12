"""Blueprint registration. Feature blueprints are nested under the /api parent blueprint."""
from flask import Flask

from .api import api_bp


def register_blueprints(app: Flask) -> None:
    # Feature blueprints (auth, requests, approvals, ...) will be nested here, e.g.:
    #   api_bp.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(api_bp)
