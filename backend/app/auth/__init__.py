"""JWT configuration and operator-controlled privileged account provisioning."""

import secrets
import click
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from backend.app.database import db
from .security import hash_password


def init_auth(app):
    secret = app.config.get("JWT_SECRET_KEY")
    if secret is not None and (not isinstance(secret, str) or len(secret.encode("utf-8")) < 32 or len(set(secret)) < 16):
        raise ValueError("JWT_SECRET_KEY must be a randomly generated secret of at least 32 bytes")
    try:
        raw = app.config["JWT_ACCESS_TOKEN_SECONDS"]
        seconds = int(raw)
        if isinstance(raw, bool) or str(seconds) != str(raw) or not 60 <= seconds <= 86400:
            raise ValueError
    except (TypeError, ValueError):
        raise ValueError("JWT_ACCESS_TOKEN_SECONDS must be an integer between 60 and 86400") from None
    app.config["JWT_ACCESS_TOKEN_SECONDS"] = seconds
    if secret is not None:
        app.extensions["auth_dummy_hash"] = hash_password(secrets.token_urlsafe(32))

    @app.cli.command("create-privileged-user")
    @click.option("--email", required=True)
    @click.option("--role", required=True, type=click.Choice(["doctor", "admin", "receptionist"]))
    def create_privileged_user(email, role):
        """Provision a new privileged account using local operator access only."""
        from .security import require_auth_configuration, validate_email, validate_password
        from .routes import create_account

        try:
            require_auth_configuration()
            email = validate_email(email)
            password = click.prompt("Password", hide_input=True, confirmation_prompt=True)
            validate_password(password)
            create_account(email, password, role)
        except HTTPException as error:
            if "sqlalchemy" in app.extensions:
                db.session.rollback()
            raise click.ClickException(error.name) from None
        except SQLAlchemyError:
            db.session.rollback()
            raise click.ClickException("Account provisioning unavailable") from None
        click.echo("Privileged account created.")

    @app.cli.command("authorize-grant-administrator")
    @click.option("--email", required=True)
    def authorize_grant_administrator(email):
        """Trusted local operator: explicitly authorize an existing administrator."""
        from .routes import find_accounts
        from .security import require_auth_configuration, validate_email
        from .grants import utc_now
        from backend.app.models import GrantAdministrator
        try:
            require_auth_configuration()
            accounts = find_accounts(validate_email(email))
            if len(accounts) != 1 or accounts[0].role.code != "admin" or not accounts[0].password_hash:
                raise click.ClickException("An existing administrator account is required")
            user = accounts[0]
            if db.session.get(GrantAdministrator, user.id) is None:
                db.session.add(GrantAdministrator(user_id=user.id, authorized_at=utc_now()))
                db.session.commit()
        except HTTPException as error:
            raise click.ClickException(error.name) from None
        except SQLAlchemyError:
            db.session.rollback()
            raise click.ClickException("Grant administrator authorization unavailable") from None
        click.echo("Grant administrator authorized.")
