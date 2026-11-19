"""AccessHub Flask application factory."""

import os
from pathlib import Path

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import CONFIGS, ProductionConfig
from .extensions import cors, db, jwt, mail, migrate

MIGRATIONS_DIR = str(Path(__file__).resolve().parent.parent / "migrations")


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure the Flask app.

    ``config_name`` is one of ``development``, ``testing`` or ``production``;
    it defaults to the ``FLASK_CONFIG`` env var, then ``development``.
    """
    config_name = config_name or os.environ.get("FLASK_CONFIG", "development")
    if config_name not in CONFIGS:
        raise ValueError(f"Unknown config '{config_name}'. Use one of: {', '.join(CONFIGS)}")
    config_cls = CONFIGS[config_name]

    if config_cls is ProductionConfig:
        missing = [name for name in ProductionConfig.REQUIRED_ENV if not os.environ.get(name)]
        if missing:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

    app = Flask(__name__)
    app.config.from_object(config_cls)
    app.json.sort_keys = False  # keep response keys in the order we build them

    hops = app.config.get("PROXY_FIX_HOPS", 0)
    if hops:
        # Behind nginx: trust X-Forwarded-For/Proto from that many proxies, so request.remote_addr
        # (recorded in audit logs) is the real client, not the proxy.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops)

    from . import models  # noqa: F401  (register all models on the metadata)

    db.init_app(app)
    migrate.init_app(app, db, directory=MIGRATIONS_DIR)
    jwt.init_app(app)
    mail.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["FRONTEND_URL"]}})

    from .blueprints import register_blueprints
    from .cli import register_cli
    from .errors import register_error_handlers
    from .jwt_callbacks import register_jwt_callbacks

    register_jwt_callbacks(jwt)
    register_error_handlers(app)
    register_blueprints(app)
    register_cli(app)

    from .scheduler import init_scheduler

    init_scheduler(app)  # no-op unless RUN_SCHEDULER=1 (never under testing)
    return app
