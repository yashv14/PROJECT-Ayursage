"""Raw V17 inference only. Importing/constructing this service never loads ML.

The loader is an internal operation for a separately authorized runtime bootstrap;
neither application creation nor an HTTP request calls it. Training source is
never imported. Bundle expectations come from its static serving steps 1-3.
"""

from io import BytesIO
from threading import Lock
import warnings

from werkzeug.exceptions import BadRequest

from backend.app.api.assessment_validation import (
    CATEGORICAL_INPUTS, NUMERIC_INPUTS, INPUT_FEATURES, OUTPUT_TARGETS,
    validate_inputs, valid_text,
)
from ml.inference.checksums import verify_workspace_buffers


class V17Error(Exception):
    status = 500
    reason = "inference_error"
    message = "V17 inference failed; no prediction or assessment was saved."


class V17Unavailable(V17Error):
    status = 503
    reason = "model_unavailable"
    message = "V17 model is unavailable; no prediction or assessment was saved."


class V17InvalidInput(V17Error):
    status = 400
    reason = "invalid_model_input"
    message = "V17 requires all 12 typed inputs and exact fitted categorical values."


class V17Service:
    def __init__(self, *, loading_enabled=False):
        self._loading_enabled = loading_enabled is True
        self._bundle = None
        self._vocabulary = None
        self._numpy = None
        self._pandas = None
        self._lock = Lock()

    def load(self):
        """Explicit internal load, disabled unless the bootstrap opts in.

        No path, checksum, estimator, or deserializer overrides. Verify both
        frozen identities and deserialize the retained model bytes, never a
        reopened path. This is an identity gate, not a sandbox for pickle code.
        A bounded, approved runtime must be established before calling this.
        """
        if not self._loading_enabled:
            raise V17Unavailable()
        with self._lock:
            if self._bundle is not None:
                return
            try:
                verified_model, _verified_source = verify_workspace_buffers()
                # Optional runtime imports occur ONLY inside the explicit loader.
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=UserWarning)
                    try:
                        from sklearn.exceptions import InconsistentVersionWarning
                        warnings.filterwarnings("ignore", category=InconsistentVersionWarning)
                    except ImportError:
                        pass
                    import joblib
                    import numpy as np
                    import pandas as pd

                    bundle = joblib.load(BytesIO(verified_model.buffer))
                    vocabulary = self._validate_bundle(bundle, np)
            except Exception:
                # Do not log serialized objects, paths, patient data or exceptions.
                raise V17Unavailable() from None
            self._numpy, self._pandas = np, pd
            self._vocabulary = vocabulary
            self._bundle = bundle  # Publish only after every check succeeds.

    @staticmethod
    def _validate_bundle(bundle, np):
        if not isinstance(bundle, dict) or bundle.get("pipeline_version") != "AyurSage_v17":
            raise ValueError("Unsupported bundle")
        for key, expected in (
            ("input_features", INPUT_FEATURES), ("output_targets", OUTPUT_TARGETS),
            ("categorical_cols", CATEGORICAL_INPUTS), ("numeric_cols", NUMERIC_INPUTS),
        ):
            if tuple(bundle[key]) != expected:
                raise ValueError("Unsupported contract")
        winner = bundle["best_overall_model"]
        if winner not in ("RF", "ET", "GB", "XGB", "CB"):
            raise ValueError("Unsupported winner")
        pre = bundle["shared_pre"]
        if tuple(pre.feature_names_in_) != INPUT_FEATURES:
            raise ValueError("Unsupported fitted features")
        # The source uses cat OHE and num passthrough in exactly this order.
        configured_cat, configured_num = pre.transformers
        cat, num, *remainder = pre.transformers_
        # Fitting may replace the 'passthrough' sentinel with an identity
        # transformer; validate the original configuration as well as columns.
        if (configured_cat[0] != "cat" or tuple(configured_cat[2]) != CATEGORICAL_INPUTS
                or configured_num[0] != "num" or configured_num[1] != "passthrough"
                or tuple(configured_num[2]) != NUMERIC_INPUTS
                or cat[0] != "cat" or tuple(cat[2]) != CATEGORICAL_INPUTS
                or num[0] != "num"
                or tuple(num[2]) != NUMERIC_INPUTS or pre.remainder != "drop"
                or any(item[1] != "drop" for item in remainder)):
            raise ValueError("Unsupported preprocessing")
        encoder = pre.named_transformers_["cat"]
        if encoder.handle_unknown != "ignore" or encoder.sparse_output is not False:
            raise ValueError("Unsupported categorical encoder")
        if len(encoder.categories_) != len(CATEGORICAL_INPUTS):
            raise ValueError("Missing fitted categories")
        vocabulary = {}
        for name, categories in zip(CATEGORICAL_INPUTS, encoder.categories_):
            if len(categories) == 0 or any(not isinstance(value, str) for value in categories):
                raise ValueError("Unsupported fitted categories")
            vocabulary[name] = frozenset(categories)
        for target in OUTPUT_TARGETS:
            clf = bundle["models"][target][winner]
            labels = bundle["le_output"][target]
            if not callable(clf.predict) or not callable(labels.inverse_transform):
                raise ValueError("Missing serving interface")
            if len(labels.classes_) == 0 or any(not valid_text(value, 4096, True) for value in labels.classes_):
                raise ValueError("Invalid output labels")
            classes = np.asarray(clf.classes_)
            if (classes.ndim != 1 or classes.size == 0
                    or not np.issubdtype(classes.dtype, np.integer)
                    or np.any(classes < 0) or np.any(classes >= len(labels.classes_))):
                raise ValueError("Invalid encoded classes")
        return vocabulary

    def predict(self, inputs):
        # Revalidate even for non-HTTP callers; no missing/default/coerced values.
        try:
            inputs = dict(validate_inputs(inputs))
        except BadRequest:
            raise V17InvalidInput() from None
        with self._lock:
            if self._bundle is None:
                raise V17Unavailable()
            for name in CATEGORICAL_INPUTS:
                if inputs[name] not in self._vocabulary[name]:
                    raise V17InvalidInput()
            try:
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=UserWarning)
                    bundle, np = self._bundle, self._numpy
                    frame = self._pandas.DataFrame([inputs], columns=list(INPUT_FEATURES))
                    transformed = bundle["shared_pre"].transform(frame)
                    outputs = {}
                    for target in OUTPUT_TARGETS:
                        clf = bundle["models"][target][bundle["best_overall_model"]]
                        predicted = np.asarray(clf.predict(transformed)).reshape(-1)
                        if (predicted.size != 1 or not np.issubdtype(predicted.dtype, np.number)
                                or not np.isfinite(predicted[0])
                                or predicted[0] != int(predicted[0])
                                or predicted[0] not in clf.classes_):
                            raise ValueError("Invalid prediction")
                        decoded = bundle["le_output"][target].inverse_transform([int(predicted[0])])
                        if len(decoded) != 1 or not valid_text(decoded[0], 4096, True):
                            raise ValueError("Invalid decoded label")
                        outputs[target] = str(decoded[0])
            except Exception:
                raise V17Error() from None
            return {
                "model_version": "AyurSage_v17",
                "status": "pending_clinical_review",
                "persisted": False,
                "outputs": outputs,
            }
