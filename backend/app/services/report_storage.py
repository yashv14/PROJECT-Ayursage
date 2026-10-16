"""Provider-neutral private storage. No default/provider/credentials at startup."""
from threading import Lock
from typing import Protocol


class PrivateReportStorage(Protocol):
    # Implementations must use private ACLs, bounded I/O and create-only keys.
    # A failed put may have written bytes; delete must be idempotent.
    def put(self, key: str, content: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class MemoryReportStorage:
    """Disposable local/test storage only; never selected automatically."""
    def __init__(self):
        self._objects = {}
        self._lock = Lock()

    def put(self, key, content):
        with self._lock:
            if key in self._objects:
                raise ValueError('Object already exists')
            self._objects[key] = bytes(content)

    def get(self, key):
        with self._lock:
            return self._objects[key]

    def delete(self, key):
        with self._lock:
            self._objects.pop(key, None)
