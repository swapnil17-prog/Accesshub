"""AccessHub Flask application factory."""
import os

from flask import Flask

from .config import CONFIGS, ProductionConfig
from .extensions import cors, db, jwt, mail, migrate


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

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    mail.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["FRONTEND_URL"]}})

    from .blueprints import register_blueprints

    register_blueprints(app)
    return app
