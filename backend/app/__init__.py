"""Application factory for the single modular Flask REST API."""

from flask import Flask

from backend.config import load_config

from .api import api
from .errors import register_error_handlers
from .database import init_database
from .auth import init_auth
from .services.v17 import V17Service


def create_app(test_config=None):
    app = Flask(__name__, static_folder=None)
    app.config.from_mapping(load_config())
    if test_config is not None:
        app.config.from_mapping(test_config)

    init_database(app)
    init_auth(app)
    # Construct an unloaded service. Runtime bootstrap must call load explicitly.
    app.extensions["v17"] = V17Service(
        loading_enabled=app.config["V17_MODEL_LOADING_ENABLED"],
    )
    app.register_blueprint(api)
    register_error_handlers(app)
    return app
