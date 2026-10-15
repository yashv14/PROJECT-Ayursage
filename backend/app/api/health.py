"""Application liveness only; no database, storage or model readiness claim."""

from . import api


@api.get("/health")
def health():
    return {"status": "ok"}, 200
