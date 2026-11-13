"""Blueprint registration. Every blueprint lives under the /api prefix."""

from flask import Flask

from .approvals import approvals_bp
from .auth import auth_bp
from .health import health_bp
from .requests import requests_bp

API_PREFIX = "/api"


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(health_bp, url_prefix=API_PREFIX)
    app.register_blueprint(auth_bp, url_prefix=f"{API_PREFIX}/auth")
    app.register_blueprint(requests_bp, url_prefix=f"{API_PREFIX}/requests")
    app.register_blueprint(approvals_bp, url_prefix=f"{API_PREFIX}/approvals")
