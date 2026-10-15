"""Verification-only audit scaffold. Deserialization is intentionally absent."""

import argparse
import json

from .checksums import VerificationError, WORKSPACE, verify_workspace_buffers


class LoadingDisabled(Exception):
    """Matching hashes do not authorize deserialization or inference."""


def run_audit(workspace=WORKSPACE, *, request_loading=False):
    verified = verify_workspace_buffers(workspace)
    # This boundary must be reviewed before any deserializer is implemented.
    # A future loader must hash the same bytes it loads, not reopen these paths.
    if request_loading:
        raise LoadingDisabled("LOADING_DISABLED_PENDING_REVIEW")
    return {
        "status": "CHECKSUMS_VERIFIED_LOADING_DISABLED",
        "artifacts": [item.metadata() for item in verified],
        "loading_enabled": False,
        "model_loaded": False,
        "inference_executed": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=str(WORKSPACE))
    parser.add_argument(
        "--load", action="store_true", help="Always refused; loading is disabled."
    )
    args = parser.parse_args(argv)
    try:
        report = run_audit(args.workspace, request_loading=args.load)
    except VerificationError as error:
        report = {
            "status": error.code,
            "artifact": error.artifact,
            "loading_enabled": False,
            "model_loaded": False,
            "inference_executed": False,
        }
        exit_code = 1
    except LoadingDisabled:
        report = {
            "status": "LOADING_DISABLED_PENDING_REVIEW",
            "loading_enabled": False,
            "model_loaded": False,
            "inference_executed": False,
        }
        exit_code = 2
    else:
        exit_code = 0
    print(json.dumps(report, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
