"""Opaque-byte checksum tests only; no serialized fixture or model execution."""

from contextlib import redirect_stdout
from dataclasses import FrozenInstanceError
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from ml.inference import checksums
from ml.inference.audit import LoadingDisabled, main, run_audit


class ApprovedHashTests(unittest.TestCase):
    """No fixture patch: expectations are independent literals."""

    def test_production_model_hash_is_approved_literal(self):
        by_path = {spec.relative_path: spec for spec in checksums.APPROVED_ARTIFACTS}
        self.assertEqual(
            by_path["ml/artifacts/ayursage_model.pkl"].expected_sha256,
            "e0b60420eaf618e165822af5f69f8c437794c06ae0ca885e5d68df8e6a9a7c98",
        )

    def test_source_hash_is_approved_literal(self):
        by_path = {spec.relative_path: spec for spec in checksums.APPROVED_ARTIFACTS}
        self.assertEqual(
            by_path["ml/source/AyurSage_Training_v17.py"].expected_sha256,
            "afc2fb4b771467e3a47045b1c3b76f9dc898716078fc47d8f930bfb5093088d3",
        )


class LoadingScaffoldTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.model = self.root / "model.bin"
        self.source = self.root / "source.txt"
        self.model.write_bytes(b"opaque test bytes, not a pickle")
        self.source.write_bytes(b"test text, not executable source")
        self.specs = (
            checksums.Artifact("production_model", "model.bin", sha256(self.model.read_bytes()).hexdigest()),
            checksums.Artifact("v17_source", "source.txt", sha256(self.source.read_bytes()).hexdigest()),
        )
        specs_patch = patch.object(checksums, "APPROVED_ARTIFACTS", self.specs)
        specs_patch.start()
        self.addCleanup(specs_patch.stop)

    def test_checksum_success(self):
        report = checksums.verify_file(self.model, self.specs[0].expected_sha256, "production_model")
        self.assertEqual(report["size_bytes"], self.model.stat().st_size)
        self.assertEqual(report["sha256"], self.specs[0].expected_sha256)

    def test_replaced_path_cannot_change_retained_verified_buffer(self):
        original = self.model.read_bytes()
        real_read = Path.read_bytes

        def read_then_replace(path):
            data = real_read(path)
            path.write_bytes(b"replacement bytes, not a pickle")
            return data

        with patch.object(Path, "read_bytes", autospec=True, side_effect=read_then_replace) as read:
            verified = checksums.read_verified_file(self.model, self.specs[0])
            read.assert_called_once_with(self.model)
        self.assertEqual(verified.buffer, original)
        self.assertNotEqual(self.model.read_bytes(), verified.buffer)
        # Future consumption uses only this retained immutable buffer, never a path.
        with patch.object(Path, "open", side_effect=AssertionError("path reopened")):
            self.assertEqual(sha256(verified.buffer).hexdigest(), verified.metadata()["sha256"])
        with self.assertRaises(checksums.VerificationError):
            checksums.read_verified_file(self.model, self.specs[0])

    def test_retained_object_is_immutable(self):
        verified = checksums.read_verified_file(self.model, self.specs[0])
        with self.assertRaises(FrozenInstanceError):
            verified.buffer = b"replacement"

    def test_mutable_buffer_is_rejected(self):
        with self.assertRaises(TypeError):
            checksums.VerifiedArtifact(self.specs[0], bytearray(self.model.read_bytes()))

    def test_unverified_bytes_cannot_construct_verified_object(self):
        with self.assertRaises(checksums.VerificationError):
            checksums.VerifiedArtifact(self.specs[0], b"wrong bytes")

    def test_workspace_retains_both_verified_buffers(self):
        buffers = checksums.verify_workspace_buffers(self.root)
        self.assertEqual([item.buffer for item in buffers], [self.model.read_bytes(), self.source.read_bytes()])

    def test_checksum_mismatch(self):
        with self.assertRaises(checksums.VerificationError) as caught:
            checksums.verify_file(self.model, "0" * 64, "production_model")
        self.assertEqual(caught.exception.code, "CHECKSUM_MISMATCH")

    def test_missing_file(self):
        with self.assertRaises(checksums.VerificationError) as caught:
            checksums.verify_file(self.root / "absent", "0" * 64, "production_model")
        self.assertEqual(caught.exception.code, "ARTIFACT_MISSING")

    def test_directory_is_unreadable_artifact(self):
        with self.assertRaises(checksums.VerificationError) as caught:
            checksums.verify_file(self.root, "0" * 64, "production_model")
        self.assertEqual(caught.exception.code, "ARTIFACT_UNREADABLE")

    def test_both_artifacts_verified(self):
        report = checksums.verify_workspace(self.root)
        self.assertEqual([item["artifact"] for item in report], ["production_model", "v17_source"])

    def test_verified_audit_never_claims_loading(self):
        report = run_audit(self.root)
        self.assertEqual(report["status"], "CHECKSUMS_VERIFIED_LOADING_DISABLED")
        for flag in ("loading_enabled", "model_loaded", "inference_executed"):
            self.assertIs(report[flag], False)

    def test_loading_refused_even_after_success(self):
        with self.assertRaises(LoadingDisabled):
            run_audit(self.root, request_loading=True)

    def test_bad_source_blocks_loading_request_before_boundary(self):
        self.source.write_bytes(b"changed test text")
        with self.assertRaises(checksums.VerificationError) as caught:
            run_audit(self.root, request_loading=True)
        self.assertEqual(caught.exception.code, "CHECKSUM_MISMATCH")
        self.assertEqual(caught.exception.artifact, "v17_source")

    def test_missing_model_blocks_loading_request_before_boundary(self):
        self.model.unlink()
        with self.assertRaises(checksums.VerificationError) as caught:
            run_audit(self.root, request_loading=True)
        self.assertEqual(caught.exception.code, "ARTIFACT_MISSING")

    def test_cli_exit_codes_and_safe_reports(self):
        for load, expected in ((False, 0), (True, 2)):
            with self.subTest(load=load):
                output = StringIO()
                args = ["--workspace", str(self.root)] + (["--load"] if load else [])
                with redirect_stdout(output):
                    code = main(args)
                self.assertEqual(code, expected)
                self.assertIs(json.loads(output.getvalue())["model_loaded"], False)
        self.source.write_bytes(b"changed test text")
        output = StringIO()
        with redirect_stdout(output):
            code = main(["--workspace", str(self.root), "--load"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())["status"], "CHECKSUM_MISMATCH")
        self.assertNotIn(str(self.root), output.getvalue())


if __name__ == "__main__":
    unittest.main()
