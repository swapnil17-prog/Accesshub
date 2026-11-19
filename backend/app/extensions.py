"""Flask extension singletons, initialised in create_app()."""

from apscheduler.schedulers.background import BackgroundScheduler
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_mail import Mail
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Deterministic constraint/index names so Alembic migrations are stable and reviewable.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for all models (SQLAlchemy 2.x style)."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


db = SQLAlchemy(model_class=Base)
migrate = Migrate()
jwt = JWTManager()
mail = Mail()
cors = CORS()
# Per-client-IP rate limits (request.remote_addr is the real client behind nginx via ProxyFix).
limiter = Limiter(key_func=get_remote_address)
# Created here, started only when RUN_SCHEDULER=1 (never under the testing config).
scheduler = BackgroundScheduler(timezone="UTC")
