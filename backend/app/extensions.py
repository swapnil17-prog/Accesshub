"""Flask extension singletons, initialised in create_app()."""
from apscheduler.schedulers.background import BackgroundScheduler
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all models (SQLAlchemy 2.x style)."""


db = SQLAlchemy(model_class=Base)
migrate = Migrate()
jwt = JWTManager()
mail = Mail()
cors = CORS()
# Created here, started only when RUN_SCHEDULER=1 (never under the testing config).
scheduler = BackgroundScheduler(timezone="UTC")
