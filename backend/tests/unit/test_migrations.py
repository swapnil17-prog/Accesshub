from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext


def test_migrations_match_models(db):
    """The test DB is built from the migrations; any diff means a migration is missing."""
    with db.engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), db.metadata)
    assert diff == []
