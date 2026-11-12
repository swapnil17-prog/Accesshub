import pytest

from app import create_app


def test_testing_config_flags(app):
    assert app.config["TESTING"] is True
    assert app.config["RUN_SCHEDULER"] is False


def test_unknown_config_rejected():
    with pytest.raises(ValueError):
        create_app("nope")


def test_production_requires_secrets(monkeypatch):
    for name in ("SECRET_KEY", "JWT_SECRET_KEY", "DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app("production")
