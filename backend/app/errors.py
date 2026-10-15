"""Consistent JSON errors, preserving HTTP status codes and protocol headers."""

from flask import json
from werkzeug.exceptions import HTTPException
from .services.v17 import V17Error
from .api.assessment_validation import AssessmentValidationError


def register_error_handlers(app):
    @app.errorhandler(AssessmentValidationError)
    def assessment_validation_error(error):
        return {"error": {
            "code": 400, "reason": "invalid_assessment", "message": error.description,
        }}, 400

    @app.errorhandler(V17Error)
    def model_error(error):
        return {"error": {
            "code": error.status, "reason": error.reason, "message": error.message,
        }}, error.status

    @app.errorhandler(HTTPException)
    def http_error(error):
        response = error.get_response()
        response.data = json.dumps(
            {"error": {"code": error.code, "message": error.name}}
        )
        response.content_type = "application/json"
        if error.code == 401:
            response.headers["WWW-Authenticate"] = "Bearer"
        return response

    @app.errorhandler(500)
    def internal_error(error):
        # Flask logs the original exception; do not include it in the response.
        return {"error": {"code": 500, "message": "Internal Server Error"}}, 500
