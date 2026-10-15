"""One app-scoped database extension; startup never connects or creates tables."""

from pathlib import Path

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)


def validate_database_url(value):
    """Restrict configured drivers and reject ambiguous relative SQLite paths."""
    message = "DATABASE_URL must use mysql+pymysql or SQLite with an absolute path or :memory:"
    try:
        url = make_url(value)
        if url.drivername == "mysql+pymysql" and url.database:
            return url
        if url.drivername in {"sqlite", "sqlite+pysqlite"}:
            local = not any((url.host, url.username, url.password, url.port))
            if local and (url.database == ":memory:" or (url.database and Path(url.database).is_absolute())):
                return url
    except (ArgumentError, TypeError, ValueError):
        pass
    raise ValueError(message) from None


def enable_sqlite_foreign_keys(engine):
    if engine.dialect.name != "sqlite":
        return

    @event.listens_for(engine, "checkin")
    def restore_after_migration(connection, _record):
        # Alembic's SQLite role CHECK rebuild uses a dedicated connection with
        # FK checks temporarily off. Pool return follows commit/rollback; restore
        # enforcement before that connection is reused by application requests.
        if connection is not None:
            connection.execute("PRAGMA foreign_keys=ON")

    @event.listens_for(engine, "connect")
    def foreign_keys_on(connection, _record):
        cursor = connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


def init_database(app):
    # Register metadata even when the optional database is disabled.
    from backend.app import models  # noqa: F401

    value = app.config.get("SQLALCHEMY_DATABASE_URI")
    if value is None:
        return
    app.config["SQLALCHEMY_DATABASE_URI"] = validate_database_url(value)
    db.init_app(app)
    with app.app_context():
        enable_sqlite_foreign_keys(db.engine)
