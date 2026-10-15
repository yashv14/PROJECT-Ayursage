"""Read configuration at app creation time, never at module import time."""

import os


def load_config():
    """Use process environment only; no secret defaults or implicit .env loading."""
    debug_value = os.environ.get("FLASK_DEBUG", "").strip().lower()
    if debug_value not in {"", "0", "1", "false", "true"}:
        raise ValueError("FLASK_DEBUG must be 0, 1, false or true")

    port_value = os.environ.get("BACKEND_PORT", "").strip() or "5000"
    try:
        port = int(port_value)
    except ValueError:
        raise ValueError("BACKEND_PORT must be an integer between 1 and 65535") from None
    if not 1 <= port <= 65535:
        raise ValueError("BACKEND_PORT must be an integer between 1 and 65535")

    return {
        # Internal bootstrap opt-in only; no automatic loading or HTTP override.
        # Remains false until a separately authorized runtime is prepared.
        "V17_MODEL_LOADING_ENABLED": False,
        "DEBUG": debug_value in {"1", "true"},
        "SECRET_KEY": os.environ.get("SECRET_KEY") or None,
        "JWT_SECRET_KEY": os.environ.get("JWT_SECRET_KEY") or None,
        "JWT_ACCESS_TOKEN_SECONDS": os.environ.get("JWT_ACCESS_TOKEN_SECONDS", "").strip() or 900,
        "BACKEND_PORT": port,
        "SQLALCHEMY_DATABASE_URI": os.environ.get("DATABASE_URL", "").strip() or None,
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SQLALCHEMY_ENGINE_OPTIONS": {"hide_parameters": True},
    }
