"""Read-only artifact identity checks. Never imports source or loads models."""

from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path


@dataclass(frozen=True)
class Artifact:
    name: str
    relative_path: str
    expected_sha256: str


APPROVED_ARTIFACTS = (
    Artifact(
        "production_model",
        "ml/artifacts/ayursage_model.pkl",
        "e0b60420eaf618e165822af5f69f8c437794c06ae0ca885e5d68df8e6a9a7c98",
    ),
    Artifact(
        "v17_source",
        "ml/source/AyurSage_Training_v17.py",
        "afc2fb4b771467e3a47045b1c3b76f9dc898716078fc47d8f930bfb5093088d3",
    ),
)
WORKSPACE = Path(__file__).resolve().parents[2]


class VerificationError(Exception):
    """Stable audit error code; excludes filesystem and source contents."""

    def __init__(self, code, artifact):
        self.code = code
        self.artifact = artifact
        super().__init__(f"{artifact}: {code}")


@dataclass(frozen=True)
class VerifiedArtifact:
    """Immutable verified bytes, not permission to deserialize them."""

    artifact: Artifact
    buffer: bytes = field(repr=False)

    def __post_init__(self):
        if type(self.buffer) is not bytes:
            raise TypeError("VerifiedArtifact requires immutable bytes")
        if sha256(self.buffer).hexdigest() != self.artifact.expected_sha256:
            raise VerificationError("CHECKSUM_MISMATCH", self.artifact.name)

    def metadata(self):
        return {
            "artifact": self.artifact.name,
            "size_bytes": len(self.buffer),
            "sha256": self.artifact.expected_sha256,
        }


def read_verified_file(path, artifact):
    """Read once and verify the retained bytes; never reopen for consumption."""
    try:
        buffer = Path(path).read_bytes()
    except FileNotFoundError:
        raise VerificationError("ARTIFACT_MISSING", artifact.name) from None
    except OSError:
        raise VerificationError("ARTIFACT_UNREADABLE", artifact.name) from None
    return VerifiedArtifact(artifact, buffer)


def verify_file(path, expected_sha256, name):
    """Compatibility metadata helper; metadata must never authorize loading."""
    artifact = Artifact(name, "", expected_sha256)
    return read_verified_file(path, artifact).metadata()


def verify_workspace_buffers(workspace=WORKSPACE):
    """Return retained buffers only after both approved identities verify."""
    root = Path(workspace)
    return tuple(
        read_verified_file(root / spec.relative_path, spec)
        for spec in APPROVED_ARTIFACTS
    )


def verify_workspace(workspace=WORKSPACE):
    """Require both fixed approved identities; no caller-supplied hash overrides."""
    return [item.metadata() for item in verify_workspace_buffers(workspace)]
