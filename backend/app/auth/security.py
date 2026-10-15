"""Reusable authentication, role checks and deny-by-default ownership checks."""

from datetime import datetime, timezone
from functools import wraps
import re
import uuid

import jwt
from flask import current_app, g, request
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import BadRequest, Forbidden, ServiceUnavailable, Unauthorized
from werkzeug.security import generate_password_hash, check_password_hash

from backend.app.database import db
from backend.app.models import User, ROLE_CODES


def hash_password(password):
    return generate_password_hash(password, method="scrypt:32768:8:1")


def verify_password(stored_hash, password):
    if not stored_hash:
        return False
    try:
        return check_password_hash(stored_hash, password)
    except (ValueError, TypeError):
        return False


def validate_email(value):
    if not isinstance(value, str):
        raise BadRequest()
    value = value.strip().lower()
    if len(value) > 254 or not re.fullmatch(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+", value):
        raise BadRequest()
    local = value.split("@")[0]
    if len(local) > 64 or local.startswith(".") or local.endswith(".") or ".." in local:
        raise BadRequest()
    return value


def validate_password(value, registration=True):
    minimum = 12 if registration else 1
    if not isinstance(value, str) or not minimum <= len(value) <= 128 or not value.strip() or "\x00" in value:
        raise BadRequest()
    return value


def require_auth_configuration():
    if not current_app.config.get("JWT_SECRET_KEY") or "sqlalchemy" not in current_app.extensions:
        raise ServiceUnavailable()


def auth_operation(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        require_auth_configuration()
        try:
            return view(*args, **kwargs)
        except SQLAlchemyError:
            # Do not log DB exceptions: driver messages may contain account data.
            db.session.rollback()
            raise ServiceUnavailable() from None
    return wrapped


def issue_token(user):
    now = int(datetime.now(timezone.utc).timestamp())
    return jwt.encode({
        "sub": str(user.id), "iat": now, "nbf": now,
        "exp": now + current_app.config["JWT_ACCESS_TOKEN_SECONDS"],
        "iss": "ayur-sage", "aud": "ayur-sage-api",
        "jti": str(uuid.uuid4()), "token_type": "access",
    }, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")


def authenticate():
    g.pop("current_user", None)
    parts = request.headers.get("Authorization", "").split()
    if len(parts) != 2 or parts[0].lower() != "bearer" or len(parts[1]) > 4096:
        raise Unauthorized()
    try:
        claims = jwt.decode(
            parts[1], current_app.config["JWT_SECRET_KEY"], algorithms=["HS256"],
            issuer="ayur-sage", audience="ayur-sage-api",
            options={"require": ["sub", "iat", "nbf", "exp", "iss", "aud", "jti", "token_type"]},
        )
        subject = claims["sub"]
        if not isinstance(subject, str) or not subject.isascii() or not subject.isdigit() or len(subject) > 10 or int(subject) < 1:
            raise ValueError
        if claims["token_type"] != "access" or any(type(claims[key]) is not int for key in ("iat", "nbf", "exp")):
            raise ValueError
    except (jwt.InvalidTokenError, ValueError, TypeError, OverflowError):
        raise Unauthorized() from None
    user = db.session.get(User, int(subject))
    if user is None or not user.password_hash or user.role.code not in ROLE_CODES:
        raise Unauthorized()
    g.current_user = user
    return user


def auth_required(view):
    @auth_operation
    @wraps(view)
    def wrapped(*args, **kwargs):
        authenticate()
        return view(*args, **kwargs)
    return wrapped


def roles_required(*roles):
    if not roles or any(role not in ROLE_CODES for role in roles):
        raise ValueError("roles_required requires known role codes")

    def decorate(view):
        @auth_required
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.current_user.role.code not in roles:
                raise Forbidden()
            return view(*args, **kwargs)
        return wrapped
    return decorate


def require_patient_owner(patient):
    """Call after auth_required. No automatic doctor or administrator override."""
    user = getattr(g, "current_user", None)
    if user is None:
        raise Unauthorized()
    if patient is None or user.role.code != "patient" or patient.owner_user_id != user.id:
        raise Forbidden()
