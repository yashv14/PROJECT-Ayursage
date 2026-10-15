"""Register API routes without creating another application or service."""

from flask import Blueprint

api = Blueprint("api", __name__, url_prefix="/api")

from . import health  # noqa: E402,F401 -- routes attach to the blueprint
from backend.app.auth.routes import auth
api.register_blueprint(auth)
from .patients import patients
from . import access_grants  # noqa: E402,F401 -- attaches to patient blueprint
api.register_blueprint(patients)
from .reception import reception
api.register_blueprint(reception)
