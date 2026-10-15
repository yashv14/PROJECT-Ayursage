"""Public patient signup and login; no patient-management or privileged HTTP API."""

from flask import Blueprint, current_app, g, request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import BadRequest, Conflict, ServiceUnavailable, Unauthorized

from backend.app.database import db
from backend.app.models import User, Role, Patient
from .security import (
    auth_operation, auth_required, hash_password, issue_token,
    validate_email, validate_password, verify_password,
)


auth = Blueprint("auth", __name__, url_prefix="/auth")


def public_user(user):
    return {"id": user.id, "email": user.email, "role": user.role.code}


def credentials(registration=True):
    request.max_content_length = 4096
    if not request.is_json:
        raise BadRequest()
    data = request.get_json()
    if not isinstance(data, dict) or set(data) != {"email", "password"}:
        raise BadRequest()
    return validate_email(data["email"]), validate_password(data["password"], registration=registration)


def find_accounts(email):
    # Also handle pre-existing mixed-case emails without granting ambiguous logins.
    return db.session.scalars(select(User).where(func.lower(User.email) == email).limit(2)).all()


def create_account(email, password, role_code):
    if find_accounts(email):
        raise Conflict()
    role = db.session.scalar(select(Role).where(Role.code == role_code))
    if role is None:
        raise ServiceUnavailable()
    user = User(email=email, role=role, password_hash=hash_password(password))
    db.session.add(user)
    if role_code == "patient":
        db.session.add(Patient(owner=user))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise Conflict() from None
    return user


@auth.post("/register")
@auth_operation
def register():
    email, password = credentials()
    user = create_account(email, password, "patient")
    return {"user": public_user(user)}, 201, {"Cache-Control": "no-store"}


@auth.post("/login")
@auth_operation
def login():
    email, password = credentials(registration=False)
    accounts = find_accounts(email)
    user = accounts[0] if len(accounts) == 1 else None
    stored = user.password_hash if user and user.password_hash else current_app.extensions["auth_dummy_hash"]
    verified = verify_password(stored, password)
    if not user or not user.password_hash or not verified:
        raise Unauthorized()
    return {
        "access_token": issue_token(user), "token_type": "Bearer",
        "expires_in": current_app.config["JWT_ACCESS_TOKEN_SECONDS"],
    }, 200, {"Cache-Control": "no-store"}


@auth.get("/me")
@auth_required
def me():
    return {"user": public_user(g.current_user)}, 200, {"Cache-Control": "no-store"}
