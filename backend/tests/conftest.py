"""Shared pytest fixtures. Tests run against a real Postgres test database (never SQLite).

Set TEST_DATABASE_URL to point somewhere else; the database name must end in ``_test``
so the suite can never wipe the development database by accident.
"""

from collections.abc import Callable, Iterator

import flask_migrate
import pytest
from flask import Flask
from flask.testing import FlaskClient
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from sqlalchemy.engine import make_url

from app import create_app
from app.extensions import db as _db
from tests.factories import TEST_PASSWORD


def _reset_schema() -> None:
    _db.session.execute(text("DROP SCHEMA public CASCADE"))
    _db.session.execute(text("CREATE SCHEMA public"))
    _db.session.commit()


@pytest.fixture(scope="session")
def app() -> Iterator[Flask]:
    """One app for the whole run. The schema is built by running the real Alembic migrations,
    so the tests also prove the migrations match the models (see test_migrations.py)."""
    app = create_app("testing")
    db_name = make_url(app.config["SQLALCHEMY_DATABASE_URI"]).database or ""
    if not db_name.endswith("_test"):
        pytest.exit(f"Refusing to run tests against non-test database '{db_name}'", returncode=1)

    with app.app_context():
        _reset_schema()
        flask_migrate.upgrade()

    yield app

    with app.app_context():
        _db.session.remove()
        _reset_schema()


@pytest.fixture()
def db(app: Flask) -> Iterator[SQLAlchemy]:
    """Function-scoped DB access inside an app context; every table is emptied afterwards.

    Real commits (rather than a rolled-back outer transaction) are used because the workflow
    engine commits and uses SELECT ... FOR UPDATE, which we want to exercise for real.
    Cleanup DELETEs children before parents (cheap for tiny tables; TRUNCATE is ~10x slower
    on Docker Desktop). audit_logs is TRUNCATEd instead because its append-only trigger
    blocks DELETE, and TRUNCATE does not fire row triggers.
    """
    with app.app_context():
        yield _db
        _db.session.rollback()
        for table in reversed(_db.metadata.sorted_tables):
            if table.name == "audit_logs":
                if _db.session.execute(text("SELECT 1 FROM audit_logs LIMIT 1")).first():
                    _db.session.execute(text("TRUNCATE audit_logs"))
            else:
                _db.session.execute(table.delete())
        _db.session.commit()
        _db.session.remove()


@pytest.fixture()
def client(app: Flask, db: SQLAlchemy) -> FlaskClient:
    return app.test_client()


@pytest.fixture()
def login(client: FlaskClient) -> Callable[..., dict]:
    """``login(user_or_email, password=TEST_PASSWORD)`` -> the /auth/login JSON body (asserts 200)."""

    def _login(user_or_email, password: str = TEST_PASSWORD) -> dict:
        email = getattr(user_or_email, "email", user_or_email)
        resp = client.post("/api/auth/login", json={"email": email, "password": password})
        assert resp.status_code == 200, resp.get_json()
        return resp.get_json()

    return _login


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
