"""Structural validation only; exact feature names from frozen V17 source."""

import json
import math

from flask import request
from werkzeug.exceptions import BadRequest


CATEGORICAL_INPUTS = (
    "Disease", "Symptom Severity", "Nadi Reading", "Constitution/Prakriti",
    "Stress Levels", "Sleep Patterns", "Age Group", "Physical Activity Levels",
)
NUMERIC_INPUTS = ("BP Systolic", "BP Diastolic", "Pulse Rate", "Weight (kg)")
INPUT_FEATURES = CATEGORICAL_INPUTS + NUMERIC_INPUTS
# Exact raw label contract; enrichment and prescriptions are outside this API.
OUTPUT_TARGETS = (
    "Herbal Therapy Strategy", "Lifestyle Recommendations",
    "Therapeutic Yoga Module", "Follow-up Recommendation",
)


class AssessmentValidationError(BadRequest):
    """Safe contract messages only; never include submitted clinical values."""


def valid_text(value, maximum, nonblank=False):
    if not isinstance(value, str) or len(value) > maximum or "\x00" in value or (nonblank and not value.strip()):
        return False
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def json_object():
    request.max_content_length = 16384
    if not request.is_json:
        raise BadRequest()

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError
            result[key] = value
        return result

    def reject_constant(_value):
        raise ValueError

    try:
        value = json.loads(request.get_data(), object_pairs_hook=unique_object, parse_constant=reject_constant)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise BadRequest() from None
    if not isinstance(value, dict):
        raise BadRequest()
    return value


def validate_inputs(inputs):
    """Shared structural check for API submissions and the inference boundary."""
    if not isinstance(inputs, dict) or set(inputs) != set(INPUT_FEATURES):
        raise AssessmentValidationError("inputs must contain exactly the 12 V17 feature names.")
    for name in CATEGORICAL_INPUTS:
        value = inputs[name]
        if not valid_text(value, 256, nonblank=True):
            raise AssessmentValidationError("All eight categorical inputs must be nonblank strings of at most 256 characters.")
    for name in NUMERIC_INPUTS:
        value = inputs[name]
        if type(value) not in (int, float):
            raise AssessmentValidationError("All four numeric inputs must be finite JSON numbers, not strings or booleans.")
        try:
            if not math.isfinite(value):
                raise AssessmentValidationError("All four numeric inputs must be finite JSON numbers.")
        except OverflowError:
            raise AssessmentValidationError("All four numeric inputs must be finite JSON numbers.") from None
    return inputs


def assessment_payload():
    payload = json_object()
    if "inputs" not in payload or set(payload) - {"inputs", "notes", "predict"}:
        raise AssessmentValidationError("Provide inputs, optional notes and optional boolean predict only.")
    inputs = validate_inputs(payload["inputs"])
    predict = payload.get("predict", False)
    if type(predict) is not bool:
        raise AssessmentValidationError("predict must be a JSON boolean.")
    notes = payload.get("notes")
    if notes is not None and not valid_text(notes, 4096):
        raise AssessmentValidationError("notes must be null or a string of at most 4096 characters.")
    # Preserve supplied values; no trimming, encoding, clinical decisions or defaults.
    return inputs, notes, predict
