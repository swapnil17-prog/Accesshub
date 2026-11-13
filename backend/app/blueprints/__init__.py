"""Blueprint registration. Every blueprint lives under the /api prefix."""

from flask import Flask

from .auth import auth_bp
from .health import health_bp

API_PREFIX = "/api"


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(health_bp, url_prefix=API_PREFIX)
    app.register_blueprint(auth_bp, url_prefix=f"{API_PREFIX}/auth")
