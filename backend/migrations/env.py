"""Environment-based migrations sharing application metadata and URL validation."""

from alembic import context
from sqlalchemy import create_engine, pool

from backend.app.database import db, enable_sqlite_foreign_keys, validate_database_url
from backend.app import models  # noqa: F401
from backend.config import load_config


target_metadata = db.metadata


def run_migrations():
    # A supplied connection supports isolated migration tests without credentials.
    connection = context.config.attributes.get("connection")
    if connection is not None and not context.is_offline_mode():
        migrate_connection(connection)
        return

    value = load_config()["SQLALCHEMY_DATABASE_URI"]
    if value is None:
        raise ValueError("DATABASE_URL is required for migrations")
    url = validate_database_url(value)
    if context.is_offline_mode():
        context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
        return

    engine = create_engine(url, poolclass=pool.NullPool, hide_parameters=True)
    enable_sqlite_foreign_keys(engine)
    try:
        with engine.connect() as connection:
            migrate_connection(connection)
    finally:
        engine.dispose()


def migrate_connection(connection):
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


run_migrations()
