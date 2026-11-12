"""Shared pytest fixtures. Tests run against a real Postgres test database (never SQLite).

Set TEST_DATABASE_URL to point somewhere else; the database name must end in ``_test``
so the suite can never wipe the development database by accident.
"""
from collections.abc import Iterator

import pytest
from flask import Flask
from flask.testing import FlaskClient
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app import create_app
from app.extensions import db as _db


@pytest.fixture(scope="session")
def app() -> Iterator[Flask]:
    """One app for the whole run; schema is created fresh at start and dropped at the end."""
    app = create_app("testing")
    db_name = make_url(app.config["SQLALCHEMY_DATABASE_URI"]).database or ""
    if not db_name.endswith("_test"):
        pytest.exit(f"Refusing to run tests against non-test database '{db_name}'", returncode=1)

    with app.app_context():
        _db.drop_all()
        _db.create_all()

    yield app

    with app.app_context():
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def db(app: Flask) -> Iterator[SQLAlchemy]:
    """Function-scoped DB access inside an app context; all tables are truncated afterwards.

    Truncation (rather than a rolled-back outer transaction) is used because the workflow
    engine commits and uses SELECT ... FOR UPDATE, which we want to exercise for real.
    """
    with app.app_context():
        yield _db
        _db.session.rollback()
        tables = [f'"{t.name}"' for t in _db.metadata.sorted_tables]
        if tables:
            _db.session.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
            _db.session.commit()
        _db.session.remove()


@pytest.fixture()
def client(app: Flask, db: SQLAlchemy) -> FlaskClient:
    return app.test_client()
