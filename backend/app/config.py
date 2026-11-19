"""Configuration classes. All secrets and environment-specific values come from env vars."""

import os
from datetime import timedelta


def _bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


DEFAULT_DB_URL = "postgresql+psycopg://accesshub:accesshub@localhost:5432/accesshub"
DEFAULT_TEST_DB_URL = "postgresql+psycopg://accesshub:accesshub@localhost:5432/accesshub_test"


class BaseConfig:
    # Dev-only fallbacks (>= 32 bytes for HS256); production refuses to start without real ones.
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-secret-key-change-me-0123456789")
    # werkzeug hash method; scrypt is the secure default, tests override with a fast one.
    PASSWORD_HASH_METHOD = os.environ.get("PASSWORD_HASH_METHOD", "scrypt")

    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", DEFAULT_DB_URL)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    # JWT
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "dev-only-jwt-secret-change-me-0123456789")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)

    # Mail (MailHog in development)
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "localhost")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "1025"))
    MAIL_USE_TLS = _bool("MAIL_USE_TLS")
    MAIL_USE_SSL = _bool("MAIL_USE_SSL")
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "AccessHub <no-reply@accesshub.dev>")

    # App
    FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:5173")
    RUN_SCHEDULER = _bool("RUN_SCHEDULER")
    # Number of trusted reverse proxies in front of the app (nginx in production = 1). With 0,
    # X-Forwarded-* headers are ignored so clients can't spoof the IP written to audit logs.
    PROXY_FIX_HOPS = int(os.environ.get("PROXY_FIX_HOPS", "0"))

    # Brute-force protection for sign-in.
    # 1) Per-IP rate limit (Flask-Limiter). memory:// is per process, so with N Gunicorn workers
    #    the effective limit is up to N times higher; point RATELIMIT_STORAGE_URI at Redis
    #    (redis://host:6379) for one shared counter.
    RATELIMIT_ENABLED = _bool("RATELIMIT_ENABLED", default=True)
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True
    LOGIN_RATE_LIMIT = os.environ.get("LOGIN_RATE_LIMIT", "10 per minute")
    # 2) Per-account lockout, counted from LOGIN_FAILED audit rows in the database, so it holds
    #    across all workers and containers.
    LOGIN_LOCKOUT_ATTEMPTS = int(os.environ.get("LOGIN_LOCKOUT_ATTEMPTS", "5"))
    LOGIN_LOCKOUT_MINUTES = int(os.environ.get("LOGIN_LOCKOUT_MINUTES", "15"))
    ESCALATION_INTERVAL_MINUTES = int(os.environ.get("ESCALATION_INTERVAL_MINUTES", "15"))
    DAILY_JOB_HOUR_UTC = int(os.environ.get("DAILY_JOB_HOUR_UTC", "2"))
    EXPIRY_REMINDER_DAYS = int(os.environ.get("EXPIRY_REMINDER_DAYS", "7"))


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DB_URL)
    MAIL_SUPPRESS_SEND = True
    RUN_SCHEDULER = False  # the scheduler never runs under tests
    PASSWORD_HASH_METHOD = "pbkdf2:sha256:1000"  # fast hashing for tests only
    RATELIMIT_ENABLED = False  # tests log in many times; the limiter has its own tests


class ProductionConfig(BaseConfig):
    DEBUG = False
    # These must be provided via env vars in production (checked in create_app).
    REQUIRED_ENV = ("SECRET_KEY", "JWT_SECRET_KEY", "DATABASE_URL")


CONFIGS: dict[str, type[BaseConfig]] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
