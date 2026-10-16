"""Explicit local auth development startup; never used by the standard factory.

Run: .venv/Scripts/python.exe -B -m backend.local --port 5000
Uses a dedicated local SQLite database and random persistent signing key.
"""
import argparse
import os
from pathlib import Path
import secrets

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import URL

from backend.app import create_app
from backend.app.database import db

ROOT = Path(__file__).resolve().parents[1]


def prepare_local_app(data_dir):
    directory = Path(data_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    key_path = directory / 'jwt.key'
    try:
        descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(descriptor, 'w', encoding='utf-8') as key_file:
            key_file.write(secrets.token_urlsafe(48))
    app = create_app({
        'JWT_SECRET_KEY': key_path.read_text(encoding='utf-8').strip(),
        'JWT_ACCESS_TOKEN_SECONDS': 900,
        'SQLALCHEMY_DATABASE_URI': URL.create('sqlite', database=str(directory / 'auth.sqlite3')),
        'DEBUG': False,
        'V17_MODEL_LOADING_ENABLED': True,
    })
    # This explicitly invoked launcher upgrades only its selected local SQLite DB.
    # The normal application factory still never migrates or supplies secrets.
    migrations = Config(str(ROOT / 'backend' / 'alembic.ini'))
    with app.app_context():
        with db.engine.begin() as connection:
            migrations.attributes['connection'] = connection
            command.upgrade(migrations, 'head')
        try:
            app.extensions['v17'].load()
            print("[INFO] AYUR-SAGE V17 ML model loaded successfully.")
        except Exception as exc:
            print(f"[WARN] V17 model load deferred: {exc}")
    return app


def local_port(value):
    try:
        port = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError('Port must be an integer from 1 to 65535') from None
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError('Port must be an integer from 1 to 65535')
    return port


def main(argv=None):
    parser = argparse.ArgumentParser(description='Start local SQLite-backed AYUR-SAGE authentication development.')
    parser.add_argument('--data-dir', type=Path, default=ROOT / '.local' / 'auth')
    parser.add_argument('--port', type=local_port, default=5000)
    args = parser.parse_args(argv)
    app = prepare_local_app(args.data_dir)
    app.run(host='127.0.0.1', port=args.port, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()
