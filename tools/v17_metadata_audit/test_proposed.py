"""Synthetic review tests. All tests remain proposed and unexecuted.

The I/O tripwire is a regression test, not an execution sandbox.
"""

import builtins
import hashlib
import io
import os
import pathlib
import socket
import subprocess
import unittest
import json
from unittest.mock import patch
from dataclasses import replace

from proposed import (
    CANDIDATES, Rejected, SidecarRequest, Transport, WheelFixture,
    ProjectPageRequest, audit, check_response, serialize,
    compare_versions, marker_applies, marker_tokens, parse_metadata,
    normalized, version_key, parse_specifiers,
    MAX_PROJECT_NAME_CHARS, MAX_VERSION_CHARS,
    MAX_SPECIFIER_BOUND_CHARS, MAX_SPECIFIER_TEXT_CHARS,
    MAX_SPECIFIER_CLAUSES, MAX_MARKER_TOKENS, MAX_METADATA_BYTES,
    SyntheticResponse, SyntheticProvider, BoundSidecarRequest, audit_index,
    parse_index, wheel_identity, MAX_INDEX_BYTES, MAX_INDEX_FILES,
    MAX_FIXTURE_RESPONSES,
    recursive_dependency_closure,
)


def from_body(name, body, suffix="a"):
    filename = name.replace("-", "_") + "-" + suffix + ".whl"
    request = SidecarRequest(
        "https://files.pythonhosted.org/packages/synthetic/"
        + filename + ".metadata",
        hashlib.sha256(body).hexdigest(),
    )
    return WheelFixture(filename, True, request, body)


def fixture(name, requirements=(), version=None, python=">=3.12", suffix="a"):
    headers = [
        "Metadata-Version: 2.4",
        "Name: " + name,
        "Version: " + (version or CANDIDATES[name]),
        "Requires-Python: " + python,
    ]
    headers += ["Requires-Dist: " + item for item in requirements]
    return from_body(
        name, ("\n".join(headers) + "\n\n").encode("ascii"), suffix
    )


def valid():
    result = {name: [fixture(name)] for name in CANDIDATES}
    result["pandas"] = [fixture("pandas", (
        'numpy>=1.26; python_version < "3.14"',
        "python-dateutil>=2.8.2",
        'tzdata; sys_platform == "win32"',
    ))]
    result["python-dateutil"] = [fixture("python-dateutil", ("six>=1.5",))]
    result["scipy"] = [fixture("scipy", ("numpy>=2.0,<2.8",))]
    result["scikit-learn"] = [fixture("scikit-learn", (
        "numpy>=1.24.1", "scipy>=1.10", "joblib>=1.4",
        "narwhals>=2", "threadpoolctl>=3.5",
    ))]
    result["xgboost"] = [fixture("xgboost", (
        "numpy", "scipy",
        'nvidia-nccl-cu12; platform_system == "Linux"',
    ))]
    return result


class Tests(unittest.TestCase):
    def rejected(self, data, code):
        result = audit(data)
        self.assertEqual(result["status"], "incomplete/rejected")
        self.assertEqual(result["rejection"]["code"], code)
        self.assertFalse(result["real_dependency_resolution"])
        return result

    def test_valid_synthetic_closure(self):
        result = audit(valid())
        self.assertEqual(result["status"], "synthetic-only")
        graph = result["synthetic_dependency_graph"]
        self.assertEqual(graph["python-dateutil"], ["six"])
        self.assertEqual(graph["xgboost"], ["numpy", "scipy"])
        self.assertEqual(set(graph), set(CANDIDATES))

    def test_unapproved_dependency(self):
        data = valid()
        data["numpy"] = [fixture("numpy", ("unapproved-package>=1",))]
        result = self.rejected(data, "UNAPPROVED_DEPENDENCY")
        self.assertEqual(
            result["rejection"]["details"]["dependency"], "unapproved-package"
        )

    def test_unapproved_metadata_version_pin(self):
        data = valid()
        data["numpy"] = [fixture("numpy", version="2.4.5")]
        self.rejected(data, "UNAPPROVED_VERSION")

    def test_requirement_outside_fixed_map(self):
        data = valid()
        data["scipy"] = [fixture("scipy", ("numpy>=3.0",))]
        result = self.rejected(data, "DEPENDENCY_VERSION_OUTSIDE_FIXED_MAP")
        self.assertEqual(result["rejection"]["details"]["candidate"], "2.4.6")

    def test_incompatible_python(self):
        data = valid()
        data["numpy"] = [fixture("numpy", python=">=3.13")]
        self.rejected(data, "INCOMPATIBLE_REQUIRES_PYTHON")

    def test_unresolved_marker_in_inactive_branch(self):
        data = valid()
        data["numpy"] = [fixture("numpy", (
            'six; sys_platform == "linux" and platform_release == "11"',
        ))]
        self.rejected(data, "UNRESOLVED_MARKER")

    def test_unknown_marker(self):
        data = valid()
        data["numpy"] = [fixture("numpy", ('six; unknown_name == "x"',))]
        self.rejected(data, "UNKNOWN_MARKER")

    def test_unknown_marker_in_inactive_boolean_branch(self):
        cases = [
            'sys_platform == "linux" and unknown_name == "x"',
            'sys_platform == "win32" or unknown_name == "x"',
        ]
        for expression in cases:
            with self.subTest(expression=expression):
                with self.assertRaisesRegex(Rejected, "^UNKNOWN_MARKER$"):
                    marker_applies(expression)

    def test_marker_trailing_whitespace(self):
        for expression in (
            'python_version >= "3.12" ',
            '\tpython_version >= "3.12"\t ',
        ):
            with self.subTest(expression=expression):
                self.assertTrue(marker_applies(expression))

        data = valid()
        data["numpy"] = [fixture(
            "numpy", ('six; python_version >= "3.12" \t',)
        )]
        self.assertEqual(audit(data)["status"], "synthetic-only")

    def test_malformed_markers(self):
        cases = [
            ('python_version ==', "MALFORMED_MARKER"),
            ('python_version == "3.12" and', "MALFORMED_MARKER"),
            ('(python_version == "3.12"', "MALFORMED_MARKER"),
            ('python_version == "3.12")', "MALFORMED_MARKER"),
            ('()', "UNSUPPORTED_MARKER_FORM"),
            (
                'python_version == "3.12" python_version == "3.12"',
                "MALFORMED_MARKER",
            ),
            ('python_version == "3.12" == "3.12"', "MALFORMED_MARKER"),
            ('python_version == other_name', "UNSUPPORTED_MARKER_FORM"),
            ('python_version "3.12"', "MALFORMED_MARKER"),
            ('not python_version == "3.12"', "UNSUPPORTED_MARKER_FORM"),
        ]
        for expression, code in cases:
            with self.subTest(expression=expression):
                with self.assertRaisesRegex(Rejected, "^" + code + "$"):
                    marker_applies(expression)

    def test_unsupported_operators_stable_rejection(self):
        cases = [
            ('python_version ~= "3.12"', "UNSUPPORTED_MARKER_OPERATOR"),
            ('python_version === "3.12"', "UNSUPPORTED_MARKER_OPERATOR"),
            # Membership words are non-operator tokens in this grammar.
            ('sys_platform in "win32"', "MALFORMED_MARKER"),
            ('sys_platform not in "linux"', "MALFORMED_MARKER"),
            ('sys_platform > "linux"', "UNSUPPORTED_MARKER_OPERATOR"),
            ('python_version = "3.12"', "UNSUPPORTED_MARKER_SYNTAX"),
        ]
        # The ambiguous "<>" case is intentionally omitted.
        for expression, code in cases:
            with self.subTest(expression=expression):
                with self.assertRaisesRegex(Rejected, "^" + code + "$"):
                    marker_applies(expression)

    def test_reversed_marker_comparison(self):
        with self.assertRaisesRegex(Rejected, "^UNSUPPORTED_MARKER_FORM$"):
            marker_applies('"win32" == sys_platform')

    def test_adjacent_literals_rejected(self):
        for expression in (
            'sys_platform == "win" "32"',
            "sys_platform == 'win''32'",
        ):
            with self.subTest(expression=expression):
                with self.assertRaisesRegex(
                    Rejected, "^ADJACENT_MARKER_LITERALS$"
                ):
                    marker_applies(expression)

    def test_marker_nesting_limit(self):
        expression = "(" * 17 + 'python_version == "3.12"' + ")" * 17
        with self.assertRaisesRegex(Rejected, "^MARKER_NESTING_LIMIT$"):
            marker_applies(expression)

    def test_marker_expression_length_boundary(self):
        # The implementation uses a literal 4096, not a named length constant.
        length_limit = 4096
        expression = 'python_version == "3.12"'
        boundary = expression + " " * (length_limit - len(expression))
        self.assertEqual(len(boundary), length_limit)
        self.assertTrue(marker_applies(boundary))
        with self.assertRaisesRegex(Rejected, "^MARKER_TOO_LARGE$"):
            marker_applies(boundary + " ")

    def test_marker_token_count_boundary(self):
        # Valid expressions have odd token counts: 3 per comparison,
        # one per Boolean connector, and two per parenthesis pair.
        # Thus 128 tokens can be accepted by the tokenizer, not the parser.
        comparisons = MAX_MARKER_TOKENS // 4
        expression = " and ".join(
            ['python_version == "3.12"'] * comparisons
        )
        self.assertEqual(len(marker_tokens(expression)), MAX_MARKER_TOKENS - 1)
        self.assertTrue(marker_applies(expression))
        boundary = expression + " and"
        self.assertEqual(len(marker_tokens(boundary)), MAX_MARKER_TOKENS)
        with self.assertRaisesRegex(Rejected, "^MALFORMED_MARKER$"):
            marker_applies(boundary)
        above = boundary + " python_version"
        with self.assertRaisesRegex(Rejected, "^MARKER_TOO_COMPLEX$"):
            marker_tokens(above)
        with self.assertRaisesRegex(Rejected, "^MARKER_TOO_COMPLEX$"):
            marker_applies(above)

    def test_empty_and_unsupported_marker_syntax(self):
        cases = [
            (" \t ", "EMPTY_MARKER"),
            ('sys_platform == "win\\x33\\x32"', "UNSUPPORTED_MARKER_SYNTAX"),
            ('sys_platform == "win32"\n', "UNSUPPORTED_MARKER_SYNTAX"),
            ('sys_platform == "win32" # comment', "UNSUPPORTED_MARKER_SYNTAX"),
        ]
        for expression, code in cases:
            with self.subTest(expression=expression):
                with self.assertRaisesRegex(Rejected, "^" + code + "$"):
                    marker_applies(expression)

    def test_release_zero_padding(self):
        for left, right in (("1.2", "1.2.0"), ("1.2.0.0", "1.2")):
            with self.subTest(left=left, right=right):
                self.assertEqual(compare_versions(left, right), 0)
        self.assertLess(compare_versions("1.2.0", "1.2.1"), 0)

    def test_post_release_ordering(self):
        self.assertLess(compare_versions("1.2", "1.2.post0"), 0)
        self.assertLess(compare_versions("1.2.post0", "1.2.post1"), 0)
        self.assertEqual(compare_versions("1.2.post1", "1.2.0.post1"), 0)
        self.assertLess(compare_versions("1.2.post9", "1.3"), 0)

    def test_unsupported_version_syntax(self):
        values = (
            "2.4rc1", "2.4.dev1", "1!2.4", "2.4+local", "02.4",
            "v1.2", "1.2-1", "1.2post1", "1.2.post01", "1.2 ",
        )
        for value in values:
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    Rejected, "^UNSUPPORTED_VERSION_SYNTAX$"
                ):
                    compare_versions(value, "1.2")

    def test_unsupported_specifiers(self):
        cases = [
            ("~=2.4", "UNSUPPORTED_SPECIFIER"),
            ("===2.4.6", "UNSUPPORTED_VERSION_SYNTAX"),
            ("==2.*", "UNSUPPORTED_VERSION_SYNTAX"),
            (">=2.0,", "UNSUPPORTED_SPECIFIER"),
        ]
        for specifier, code in cases:
            with self.subTest(specifier=specifier):
                data = valid()
                data["scipy"] = [fixture("scipy", ("numpy" + specifier,))]
                self.rejected(data, code)

    def test_unsupported_requirement_forms(self):
        cases = [
            ("numpy[test]>=2", "UNSUPPORTED_REQUIREMENT"),
            ("numpy @ https://example.org/numpy.whl", "DIRECT_URL_OR_VCS"),
            ("git+https://example.org/repo", "DIRECT_URL_OR_VCS"),
            ("numpy>=2 # comment", "UNSUPPORTED_REQUIREMENT"),
        ]
        for requirement, code in cases:
            with self.subTest(requirement=requirement):
                data = valid()
                data["scipy"] = [fixture("scipy", (requirement,))]
                self.rejected(data, code)

    def test_missing_sidecar(self):
        data = valid()
        data["numpy"] = [WheelFixture("synthetic.whl", True, None, None)]
        self.rejected(data, "MISSING_METADATA_SIDECAR")

    def test_hash_mismatch(self):
        data = valid()
        wheel = data["numpy"][0]
        data["numpy"] = [WheelFixture(
            wheel.filename, True, wheel.sidecar, wheel.metadata + b"x"
        )]
        self.rejected(data, "METADATA_HASH_MISMATCH")

    def test_hash_does_not_establish_provenance(self):
        result = audit(valid())
        self.assertEqual(result["advertisement_provenance"], "UNVERIFIED")
        for record in result["metadata_evidence"]:
            self.assertEqual(
                record["hash_integrity"], "MATCHES_SUPPLIED_FIXTURE_HASH"
            )
            self.assertEqual(record["advertisement_provenance"], "UNVERIFIED")
        self.assertFalse(result["wheel_tags_verified"])

    def test_malformed_and_unsupported_metadata(self):
        original = fixture("numpy").metadata
        cases = [
            (b"Not-a-header\n\n", "MALFORMED_METADATA"),
            (original.replace(b"Name: numpy\n", b""), "INVALID_METADATA_HEADERS"),
            (original.replace(
                b"Name: numpy\n", b"Name: numpy\nName: numpy\n"
            ), "INVALID_METADATA_HEADERS"),
            (original.replace(
                b"Metadata-Version: 2.4", b"Metadata-Version: 9.0"
            ), "UNSUPPORTED_METADATA_VERSION"),
            (original + b"description", "UNSUPPORTED_METADATA_BODY"),
            (original.replace(
                b"\n\n", b"\nDynamic: Requires-Dist\n\n"
            ), "UNSUPPORTED_DYNAMIC_METADATA"),
            (original.replace(
                b"\n\n", b"\n Requires-Dist: six\n\n"
            ), "UNSUPPORTED_FOLDED_HEADER"),
        ]
        for body, code in cases:
            with self.subTest(code=code):
                data = valid()
                data["numpy"] = [from_body("numpy", body)]
                self.rejected(data, code)

    def test_invalid_metadata_name(self):
        body = fixture("numpy").metadata.replace(
            b"Name: numpy", b"Name: bad/name"
        )
        data = valid()
        data["numpy"] = [from_body("numpy", body)]
        self.rejected(data, "INVALID_PROJECT_NAME")

    def test_unapproved_metadata_name(self):
        body = fixture("numpy").metadata.replace(
            b"Name: numpy", b"Name: unapproved-package"
        )
        data = valid()
        data["numpy"] = [from_body("numpy", body)]
        self.rejected(data, "UNAPPROVED_METADATA_NAME")

    def test_candidate_validated_before_lookup(self):
        with self.assertRaisesRegex(Rejected, "^INVALID_PROJECT_NAME$"):
            parse_metadata("bad/name", fixture("numpy"))
        with self.assertRaisesRegex(Rejected, "^UNAPPROVED_CANDIDATE_NAME$"):
            parse_metadata("unapproved-package", fixture("numpy"))

    def test_invalid_fixture_key_structured_rejection(self):
        data = valid()
        data["bad/name"] = data.pop("numpy")
        self.rejected(data, "INVALID_PROJECT_NAME")

    def test_conflicting_wheel_variants(self):
        data = valid()
        data["numpy"] = [
            fixture("numpy", suffix="a"),
            fixture("numpy", ("six>=1",), suffix="b"),
        ]
        self.rejected(data, "CONFLICTING_WHEEL_METADATA")

    def test_source_only_and_missing_compatible_wheel(self):
        data = valid()
        data["numpy"] = [WheelFixture("synthetic.tar.gz", False, None, None)]
        self.rejected(data, "SOURCE_OR_NON_WHEEL_CANDIDATE")
        wheel = fixture("numpy")
        data["numpy"] = [WheelFixture(
            wheel.filename, False, wheel.sidecar, wheel.metadata
        )]
        self.rejected(data, "MISSING_COMPATIBLE_WHEEL")

    def test_missing_candidate_reported(self):
        data = valid()
        del data["numpy"]
        result = self.rejected(data, "CANDIDATE_FIXTURE_SET_MISMATCH")
        self.assertEqual(result["rejection"]["details"]["missing"], ["numpy"])

    def test_archive_denied_before_transport(self):
        class Spy(Transport):
            calls = 0

            def _fetch_permitted(self, request):
                self.calls += 1

        transport = Spy()
        with self.assertRaises(Rejected):
            transport.fetch("https://files.pythonhosted.org/package.whl")
        with self.assertRaises(Rejected):
            SidecarRequest(
                "https://files.pythonhosted.org/packages/package.whl", "0" * 64
            )
        self.assertEqual(transport.calls, 0)

    def test_invalid_urls(self):
        urls = [
            "http://files.pythonhosted.org/packages/a.whl.metadata",
            "https://example.org/packages/a.whl.metadata",
            "https://user@files.pythonhosted.org/packages/a.whl.metadata",
            "https://files.pythonhosted.org:444/packages/a.whl.metadata",
            "https://files.pythonhosted.org/packages/../a.whl.metadata",
            "https://files.pythonhosted.org/packages/%61.whl.metadata",
            "https://files.pythonhosted.org/packages/a.whl.metadata?x=1",
            "https://files.pythonhosted.org/packages/a.whl.metadata\n",
        ]
        for url in urls:
            with self.subTest(url=url), self.assertRaises(Rejected):
                SidecarRequest(url, "0" * 64)

    def test_invalid_hashes(self):
        for digest in ("", "0" * 63, "g" * 64, "A" * 64, None):
            with self.subTest(digest=digest), self.assertRaises(Rejected):
                SidecarRequest(
                    "https://files.pythonhosted.org/packages/a.whl.metadata",
                    digest,
                )

    def test_redirect_rejected(self):
        request = ProjectPageRequest("numpy")
        with self.assertRaises(Rejected):
            check_response(request, 302, request.url)
        with self.assertRaises(Rejected):
            check_response(request, 200, "https://example.org/simple/numpy/")

    def test_deterministic_output(self):
        data = valid()
        reordered = dict(reversed(list(data.items())))
        self.assertEqual(serialize(audit(data)), serialize(audit(reordered)))

    def test_duplicate_wheel_filenames_rejected_in_both_orders(self):
        first = fixture("numpy", ("six>=1", "joblib>=1"), suffix="same")
        second = fixture("numpy", ("joblib>=1", "six>=1"), suffix="same")
        for wheels in ([first, second], [second, first]):
            with self.subTest(order=[wheel.metadata for wheel in wheels]):
                data = valid()
                data["numpy"] = wheels
                self.rejected(data, "DUPLICATE_WHEEL_FILENAME")

    def test_nonduplicate_wheel_permutation_deterministic(self):
        data = valid()
        data["numpy"] = [fixture("numpy", suffix="b"), fixture("numpy", suffix="a")]
        reordered = {
            name: list(reversed(wheels))
            for name, wheels in reversed(list(data.items()))
        }
        original_result = audit(data)
        reordered_result = audit(reordered)
        self.assertEqual(original_result["status"], "synthetic-only")
        self.assertEqual(reordered_result["status"], "synthetic-only")
        self.assertEqual(serialize(original_result), serialize(reordered_result))

    def test_metadata_exact_size_limit_accepted(self):
        prefix = fixture("numpy").metadata[:-1] + b"X-Padding: "
        body = prefix + b"a" * (MAX_METADATA_BYTES - len(prefix) - 2) + b"\n\n"
        self.assertEqual(len(body), MAX_METADATA_BYTES)
        data = valid()
        data["numpy"] = [from_body("numpy", body)]
        self.assertEqual(audit(data)["status"], "synthetic-only")

    def test_metadata_one_byte_above_limit_rejected(self):
        prefix = fixture("numpy").metadata[:-1] + b"X-Padding: "
        body = prefix + b"a" * (MAX_METADATA_BYTES + 1 - len(prefix) - 2) + b"\n\n"
        self.assertEqual(len(body), MAX_METADATA_BYTES + 1)
        data = valid()
        data["numpy"] = [from_body("numpy", body)]
        self.rejected(data, "METADATA_SIZE_OR_TYPE")

    def test_unexpected_exception_propagates(self):
        with patch(
            "proposed.checked_audit",
            side_effect=RuntimeError("synthetic programming failure"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "^synthetic programming failure$"
            ):
                audit(valid())

    def test_core_io_regression_tripwire(self):
        # Not a sandbox; does not cover imports or test-runner behavior.
        def forbidden(*args, **kwargs):
            raise AssertionError("FORBIDDEN_IO")

        data = valid()
        with (
            patch.object(builtins, "open", forbidden),
            patch.object(io, "open", forbidden),
            patch.object(os, "open", forbidden),
            patch.object(pathlib.Path, "open", forbidden),
            patch.object(socket, "socket", forbidden),
            patch.object(socket, "create_connection", forbidden),
            patch.object(socket, "getaddrinfo", forbidden),
            patch.object(subprocess, "Popen", forbidden),
            patch.object(os, "system", forbidden),
        ):
            result = audit(data)
            self.assertEqual(result["status"], "synthetic-only")
            serialize(result)

    def test_unapproved_project_request_never_reaches_transport(self):
        class Spy(Transport):
            calls = 0

            def _fetch_permitted(self, request):
                self.calls += 1

        transport = Spy()
        with self.assertRaisesRegex(Rejected, "^UNAPPROVED_CANDIDATE_NAME$"):
            transport.fetch(ProjectPageRequest("unapproved-package"))
        self.assertEqual(transport.calls, 0)

        # Exercise defense-in-depth dispatch validation with a deliberately
        # malformed synthetic instance that bypasses normal construction.
        request = object.__new__(ProjectPageRequest)
        object.__setattr__(request, "project", "unapproved-package")
        with self.assertRaisesRegex(Rejected, "^UNAPPROVED_CANDIDATE_NAME$"):
            transport.fetch(request)
        self.assertEqual(transport.calls, 0)

    def test_project_name_length_limit(self):
        self.assertEqual(
            normalized("a" * MAX_PROJECT_NAME_CHARS),
            "a" * MAX_PROJECT_NAME_CHARS,
        )
        with self.assertRaisesRegex(Rejected, "^PROJECT_NAME_TOO_LARGE$"):
            normalized("a" * (MAX_PROJECT_NAME_CHARS + 1))

    def test_oversized_project_request_rejected_before_dispatch(self):
        class Spy(Transport):
            calls = 0

            def _fetch_permitted(self, request):
                self.calls += 1

        transport = Spy()
        with self.assertRaisesRegex(Rejected, "^PROJECT_NAME_TOO_LARGE$"):
            transport.fetch(ProjectPageRequest(
                "a" * (MAX_PROJECT_NAME_CHARS + 1)
            ))
        self.assertEqual(transport.calls, 0)

    def test_version_length_limit(self):
        # 64 characters: short segments avoid a large integer conversion.
        boundary = ".".join(["1"] * 31 + ["10"])
        self.assertEqual(len(boundary), MAX_VERSION_CHARS)
        version_key(boundary)
        with self.assertRaisesRegex(Rejected, "^VERSION_TOO_LARGE$"):
            version_key(boundary + "0")

    def test_specifier_bound_length_limit(self):
        boundary = ".".join(["1"] * 31 + ["10"])
        self.assertEqual(len(boundary), MAX_SPECIFIER_BOUND_CHARS)
        parse_specifiers(">=" + boundary)
        with self.assertRaisesRegex(Rejected, "^SPECIFIER_BOUND_TOO_LARGE$"):
            parse_specifiers(">=" + boundary + "0")

    def test_integer_conversion_failure_declared(self):
        with patch(
            "proposed.int",
            side_effect=ValueError("synthetic conversion limit"),
            create=True,
        ):
            with self.assertRaisesRegex(
                Rejected, "^VERSION_INTEGER_CONVERSION_REJECTED$"
            ):
                version_key("1.2")

    def test_specifier_text_and_clause_limits(self):
        with self.assertRaisesRegex(Rejected, "^SPECIFIER_TEXT_TOO_LARGE$"):
            parse_specifiers(" " * (MAX_SPECIFIER_TEXT_CHARS + 1))

        parse_specifiers(",".join([">=1"] * MAX_SPECIFIER_CLAUSES))
        with self.assertRaisesRegex(Rejected, "^TOO_MANY_SPECIFIER_CLAUSES$"):
            parse_specifiers(",".join(
                [">=1"] * (MAX_SPECIFIER_CLAUSES + 1)
            ))

    def test_oversized_metadata_version_structured_rejection(self):
        data = valid()
        data["numpy"] = [fixture(
            "numpy", version="1" * (MAX_VERSION_CHARS + 1)
        )]
        self.rejected(data, "VERSION_TOO_LARGE")

    def test_oversized_dependency_bound_structured_rejection(self):
        data = valid()
        data["scipy"] = [fixture(
            "scipy",
            ("numpy>=" + "1" * (MAX_SPECIFIER_BOUND_CHARS + 1),),
        )]
        self.rejected(data, "SPECIFIER_BOUND_TOO_LARGE")


def index_response(project, entries):
    url = ProjectPageRequest(project).url
    page = {"meta": {"api-version": "1.0"}, "name": project, "files": entries}
    return SyntheticResponse(200, url, json.dumps(page, sort_keys=True).encode("ascii"))


def index_entry(project, metadata, tag="cp312-cp312-win_amd64", build=""):
    filename = project.replace("-", "_") + "-" + CANDIDATES[project]
    filename += ("-" + build if build else "") + "-" + tag + ".whl"
    url = "https://files.pythonhosted.org/packages/synthetic/" + filename
    return {
        "filename": filename, "url": url, "requires-python": ">=3.12",
        "yanked": False, "core-metadata": {"sha256": hashlib.sha256(metadata).hexdigest()},
    }


def index_fixtures():
    responses = {}
    for project, wheels in valid().items():
        metadata = wheels[0].metadata
        entry = index_entry(project, metadata)
        page_url = ProjectPageRequest(project).url
        responses[page_url] = index_response(project, [entry])
        sidecar = entry["url"] + ".metadata"
        responses[sidecar] = SyntheticResponse(200, sidecar, metadata)
    return responses


def replace_index(responses, project, entries):
    responses[ProjectPageRequest(project).url] = index_response(project, entries)


def replace_metadata(responses, project, metadata):
    page = json.loads(responses[ProjectPageRequest(project).url].body)
    entry = page["files"][0]
    entry["core-metadata"] = {"sha256": hashlib.sha256(metadata).hexdigest()}
    replace_index(responses, project, [entry])
    url = entry["url"] + ".metadata"
    responses[url] = SyntheticResponse(200, url, metadata)


class SyntheticIndexProviderTests(unittest.TestCase):
    """Proposed acceptance definitions only. Never executed in this milestone."""

    def rejected(self, responses, code):
        result = audit_index(responses)
        self.assertEqual(result["status"], "incomplete/rejected")
        self.assertFalse(result["real_dependency_resolution"])
        self.assertEqual(result["rejection"]["code"], code)
        self.assertNotIn("binding_evidence", result)
        return result

    def entries(self, responses, project="numpy"):
        return json.loads(responses[ProjectPageRequest(project).url].body)["files"]

    def test_correct_binding_and_recursive_closure(self):
        result = audit_index(index_fixtures())
        self.assertEqual(result["status"], "synthetic-only")
        self.assertFalse(result["real_dependency_resolution"])
        self.assertEqual(result["recursive_closure"], sorted(CANDIDATES))
        graph = result["synthetic_dependency_graph"]
        self.assertEqual(graph["python-dateutil"], ["six"])
        self.assertIn("python-dateutil", graph["pandas"])
        self.assertEqual(graph["xgboost"], ["numpy", "scipy"])
        self.assertTrue(any(row[1] == "nvidia-nccl-cu12"
                            for row in result["excluded_requirements"]))
        for row in result["binding_evidence"]:
            self.assertEqual(row["version"], CANDIDATES[row["project"]])
            self.assertTrue(row["sidecar_url"].endswith(row["wheel"] + ".metadata"))
            self.assertEqual(row["binding"], "SYNTHETIC_INDEX_ADVERTISEMENT_ONLY")

    def test_mismatched_sidecar_bytes_and_identity(self):
        responses = index_fixtures()
        entry = self.entries(responses)[0]
        url = entry["url"] + ".metadata"
        responses[url] = SyntheticResponse(200, url, fixture("six").metadata)
        self.rejected(responses, "METADATA_HASH_MISMATCH")
        # Even a matching advertised digest cannot excuse wrong metadata identity.
        replace_metadata(responses, "numpy", fixture("six").metadata)
        self.rejected(responses, "METADATA_NAME_MISMATCH")

    def test_sidecar_for_wrong_wheel_cannot_replace_advertised_response(self):
        responses = index_fixtures()
        url = self.entries(responses)[0]["url"] + ".metadata"
        response = responses.pop(url)
        other = url.replace("cp312-cp312", "cp311-cp311")
        responses[other] = SyntheticResponse(200, other, response.body)
        self.rejected(responses, "MISSING_SYNTHETIC_RESPONSE")

    def test_unbound_sidecar_and_arbitrary_requests_denied(self):
        provider = SyntheticProvider(index_fixtures())
        entry = self.entries(index_fixtures())[0]
        sidecar = SidecarRequest(entry["url"] + ".metadata", "0" * 64)
        bound = BoundSidecarRequest("numpy", CANDIDATES["numpy"], entry["filename"],
                                    ProjectPageRequest("numpy").url, "0" * 64, sidecar)
        with self.assertRaisesRegex(Rejected, "^UNBOUND_SIDECAR_REQUEST$"):
            provider.fetch(bound)
        for request in (sidecar, entry["url"], "source.tar.gz", "build", "fallback", object()):
            with self.subTest(request=type(request).__name__):
                with self.assertRaisesRegex(Rejected, "REQUEST_TYPE_FORBIDDEN$"):
                    provider.fetch(request)

    def test_registered_binding_evidence_tampering_rejected(self):
        responses = index_fixtures()
        provider = SyntheticProvider(responses)
        page = provider.fetch(ProjectPageRequest("numpy"))
        binding, _, _ = parse_index("numpy", page)[0]
        # White-box registration follows closure()'s registry assignment exactly.
        provider._bound[binding.url] = binding
        self.assertEqual(provider.fetch(binding), responses[binding.url].body)
        changed_digest = "0" * 64 if binding.page_sha256 != "0" * 64 else "1" * 64
        provider._bound[binding.url] = replace(binding, page_sha256=changed_digest)
        with self.assertRaisesRegex(Rejected, "^UNBOUND_SIDECAR_REQUEST$"):
            provider.fetch(binding)

    def test_archive_and_source_responses_and_advertisements_denied(self):
        for suffix in ("a.whl", "a.tar.gz", "build", "fallback"):
            responses = index_fixtures()
            url = "https://files.pythonhosted.org/packages/" + suffix
            responses[url] = SyntheticResponse(200, url, b"archive forbidden")
            self.rejected(responses, "ARCHIVE_SOURCE_BUILD_FALLBACK_FORBIDDEN")
        responses = index_fixtures()
        entry = self.entries(responses)[0]
        entry["filename"] = "numpy-2.4.6.tar.gz"
        replace_index(responses, "numpy", [entry])
        self.rejected(responses, "ARCHIVE_SOURCE_BUILD_FALLBACK_FORBIDDEN")

    def test_target_tag_policy(self):
        for tag in ("cp312-cp312-win_amd64", "cp38-abi3-win_amd64",
                    "py3-none-any", "py310-none-win_amd64",
                    "py2.py3-none-any"):
            filename = "numpy-2.4.6-" + tag + ".whl"
            self.assertTrue(wheel_identity("numpy", filename)[1])
        for tag in ("cp311-cp311-win_amd64", "cp313-cp313-win_amd64",
                    "cp312-cp312-win32", "cp312-cp312-manylinux_2_17_x86_64",
                    "cp312-cp312-win_arm64", "py2-none-any"):
            filename = "numpy-2.4.6-" + tag + ".whl"
            self.assertFalse(wheel_identity("numpy", filename)[1])
            responses = index_fixtures()
            entry = index_entry("numpy", fixture("numpy").metadata, tag=tag)
            replace_index(responses, "numpy", [entry])
            self.rejected(responses, "MISSING_COMPATIBLE_WHEEL")

    def test_requires_python_index_and_metadata(self):
        self.assertEqual(audit_index(index_fixtures())["status"], "synthetic-only")
        responses = index_fixtures()
        entry = self.entries(responses)[0]
        entry["requires-python"] = ">=3.13"
        replace_index(responses, "numpy", [entry])
        self.rejected(responses, "INDEX_REQUIRES_PYTHON_REJECTED")
        responses = index_fixtures()
        replace_metadata(responses, "numpy", fixture("numpy", python=">=3.13").metadata)
        self.rejected(responses, "INCOMPATIBLE_REQUIRES_PYTHON")
        replace_metadata(responses, "numpy", fixture("numpy", python=">=3.11").metadata)
        self.rejected(responses, "INDEX_METADATA_REQUIRES_PYTHON_MISMATCH")

    def test_yanked_duplicate_and_conflicting_variants(self):
        for yanked in (True, "withdrawn", None, 0):
            responses = index_fixtures()
            entry = self.entries(responses)[0]
            entry["yanked"] = yanked
            replace_index(responses, "numpy", [entry])
            # JSON numbers reject before policy; booleans/strings/null reach policy.
            code = "UNSUPPORTED_INDEX_NUMBER" if type(yanked) is int else "YANKED_OR_INVALID_POLICY_VALUE"
            self.rejected(responses, code)
        responses = index_fixtures()
        entry = self.entries(responses)[0]
        replace_index(responses, "numpy", [entry, dict(entry)])
        self.rejected(responses, "AMBIGUOUS_WHEEL_ADVERTISEMENT")
        responses = index_fixtures()
        other_body = fixture("numpy", ("six>=1",)).metadata
        other = index_entry("numpy", other_body, build="1")
        replace_index(responses, "numpy", self.entries(responses) + [other])
        url = other["url"] + ".metadata"
        responses[url] = SyntheticResponse(200, url, other_body)
        self.rejected(responses, "CONFLICTING_WHEEL_METADATA")

    def test_missing_dependencies_and_conflicting_versions(self):
        responses = index_fixtures()
        del responses[ProjectPageRequest("six").url]
        self.rejected(responses, "MISSING_SYNTHETIC_RESPONSE")
        responses = index_fixtures()
        replace_metadata(responses, "python-dateutil", fixture("python-dateutil", ("unknown>=1",)).metadata)
        self.rejected(responses, "UNAPPROVED_DEPENDENCY")
        responses = index_fixtures()
        replace_metadata(responses, "python-dateutil", fixture("python-dateutil", ("six>=2",)).metadata)
        self.rejected(responses, "DEPENDENCY_VERSION_OUTSIDE_FIXED_MAP")

    def test_cycle_is_bounded_and_all_roots_checked(self):
        responses = index_fixtures()
        # A = python-dateutil, B = six, C = joblib: A -> B -> C -> A.
        replace_metadata(responses, "six", fixture("six", ("joblib>=1",)).metadata)
        replace_metadata(responses, "joblib", fixture("joblib", ("python-dateutil>=2",)).metadata)
        result = audit_index(responses)
        self.assertEqual(result["status"], "synthetic-only")
        graph = result["synthetic_dependency_graph"]
        self.assertEqual(graph["python-dateutil"], ["six"])
        self.assertEqual(graph["six"], ["joblib"])
        self.assertEqual(graph["joblib"], ["python-dateutil"])
        self.assertEqual(result["recursive_closure"], sorted(CANDIDATES))
        # Root-only traversal returns A; one-hop traversal returns A and B.
        # Recursive traversal must also reach C and stop when it revisits A.
        self.assertEqual(recursive_dependency_closure(graph, ["python-dateutil"]),
                         ["joblib", "python-dateutil", "six"])
        self.assertEqual(recursive_dependency_closure(graph, ["six"]),
                         ["joblib", "python-dateutil", "six"])
        self.assertEqual(recursive_dependency_closure(graph, ["joblib"]),
                         ["joblib", "python-dateutil", "six"])

    def test_markers_and_unsupported_syntax_fail_closed(self):
        cases = (
            ('unknown; sys_platform == "win32"', "UNAPPROVED_DEPENDENCY"),
            ('six; platform_release == "10"', "UNRESOLVED_MARKER"),
            ('six; sys_platform in "win32"', "MALFORMED_MARKER"),
            ('six~=1.17', "UNSUPPORTED_SPECIFIER"),
            ('six[extra]>=1', "UNSUPPORTED_REQUIREMENT"),
        )
        for requirement, code in cases:
            responses = index_fixtures()
            replace_metadata(responses, "python-dateutil",
                             fixture("python-dateutil", (requirement,)).metadata)
            self.rejected(responses, code)
        responses = index_fixtures()
        replace_metadata(responses, "six", fixture("six", (
            'unknown; sys_platform == "linux"',
            'joblib>=1; python_full_version >= "3.12.7" and os_name == "nt"',
        )).metadata)
        self.assertEqual(audit_index(responses)["synthetic_dependency_graph"]["six"], ["joblib"])

    def test_input_order_determinism(self):
        responses = index_fixtures()
        metadata = fixture("numpy").metadata
        other = index_entry("numpy", metadata, build="1")
        replace_index(responses, "numpy", self.entries(responses) + [other])
        url = other["url"] + ".metadata"
        responses[url] = SyntheticResponse(200, url, metadata)
        first = audit_index(responses)
        self.assertEqual(first["status"], "synthetic-only")
        reversed_responses = dict(reversed(list(responses.items())))
        entries = list(reversed(self.entries(responses)))
        replace_index(reversed_responses, "numpy", entries)
        second = audit_index(reversed_responses)
        self.assertEqual(second["status"], "synthetic-only")
        self.assertEqual(serialize(first), serialize(second))

    def test_duplicate_rejection_order_is_deterministic(self):
        for fault in ("yanked", "requires-python", "core-metadata", "url", "missing-url"):
            with self.subTest(fault=fault):
                responses = index_fixtures()
                good = self.entries(responses)[0]
                bad = dict(good)
                if fault == "missing-url":
                    del bad["url"]
                else:
                    bad[fault] = {
                        "yanked": True, "requires-python": None,
                        "core-metadata": True, "url": "https://example.org/a.whl",
                    }[fault]
                results = []
                for entries in ([good, bad], [bad, good]):
                    replace_index(responses, "numpy", entries)
                    result = self.rejected(responses, "AMBIGUOUS_WHEEL_ADVERTISEMENT")
                    self.assertEqual(result["rejection"]["details"],
                                     {"filename": good["filename"]})
                    results.append(serialize(result))
                self.assertEqual(results[0], results[1])

    def test_missing_evidence_unadvertised_response_and_hosts(self):
        responses = index_fixtures()
        entry = self.entries(responses)[0]
        entry["core-metadata"] = True
        replace_index(responses, "numpy", [entry])
        self.rejected(responses, "MISSING_ADVERTISED_METADATA_HASH")
        responses = index_fixtures()
        entry = self.entries(responses)[0]
        entry["url"] = entry["url"].replace("files.pythonhosted.org", "example.org")
        replace_index(responses, "numpy", [entry])
        self.rejected(responses, "UNAPPROVED_URL")
        responses = index_fixtures()
        url = "https://files.pythonhosted.org/packages/unadvertised.whl.metadata"
        responses[url] = SyntheticResponse(200, url, b"unused")
        self.rejected(responses, "UNUSED_OR_UNADVERTISED_RESPONSE")
        responses = index_fixtures()
        url = self.entries(responses)[0]["url"] + ".metadata"
        responses[url] = SyntheticResponse(302, url, b"")
        self.rejected(responses, "REDIRECT_OR_RESPONSE_REJECTED")

    def test_identity_url_and_required_python_evidence(self):
        for field, value, code in (
            ("filename", "six-1.17.0-cp312-cp312-win_amd64.whl", "WHEEL_PROJECT_MISMATCH"),
            ("filename", "numpy-2.4.5-cp312-cp312-win_amd64.whl", "WHEEL_VERSION_MISMATCH"),
            ("requires-python", None, "MISSING_INDEX_REQUIRES_PYTHON"),
            ("url", "https://files.pythonhosted.org/packages/other.whl", "ADVERTISED_WHEEL_URL_MISMATCH"),
            ("url", "https://files.pythonhosted.org/packages/a.whl?archive=1", "UNAPPROVED_URL"),
        ):
            responses = index_fixtures()
            entry = self.entries(responses)[0]
            entry[field] = value
            replace_index(responses, "numpy", [entry])
            self.rejected(responses, code)
        responses = index_fixtures()
        body = fixture("numpy").metadata.replace(b"Requires-Python: >=3.12\n", b"")
        replace_metadata(responses, "numpy", body)
        self.rejected(responses, "MISSING_METADATA_REQUIRES_PYTHON")

    def test_index_bounds_and_malformed_json(self):
        responses = index_fixtures()
        url = ProjectPageRequest("numpy").url
        original = responses[url].body
        padded = original + b" " * (MAX_INDEX_BYTES - len(original))
        responses[url] = SyntheticResponse(200, url, padded)
        self.assertEqual(audit_index(responses)["status"], "synthetic-only")
        responses[url] = SyntheticResponse(200, url, padded + b" ")
        self.rejected(responses, "RESPONSE_BODY_SIZE_OR_TYPE")
        for body, code in ((b"{", "MALFORMED_INDEX"),
                           (b'{"name":"numpy","name":"numpy"}', "AMBIGUOUS_INDEX_JSON_KEY"),
                           (b"[" * 9, "INDEX_NESTING_LIMIT")):
            responses[url] = SyntheticResponse(200, url, body)
            self.rejected(responses, code)
        entry = self.entries(index_fixtures())[0]
        replace_index(responses, "numpy", [entry] * (MAX_INDEX_FILES + 1))
        self.rejected(responses, "INDEX_FILE_LIMIT_OR_TYPE")
        with self.assertRaisesRegex(Rejected, "^RESPONSE_MAP_LIMIT_OR_TYPE$"):
            SyntheticProvider(dict.fromkeys(range(MAX_FIXTURE_RESPONSES + 1)))

    def test_metadata_bounds_and_malformed_headers(self):
        responses = index_fixtures()
        prefix = fixture("numpy").metadata[:-1] + b"X-Padding: "
        body = prefix + b"a" * (MAX_METADATA_BYTES - len(prefix) - 2) + b"\n\n"
        replace_metadata(responses, "numpy", body)
        self.assertEqual(audit_index(responses)["status"], "synthetic-only")
        replace_metadata(responses, "numpy", body + b"x")
        self.rejected(responses, "METADATA_SIZE_OR_TYPE")
        for body, code in ((b"broken\n\n", "MALFORMED_METADATA"),
                           (fixture("numpy").metadata + b"description", "UNSUPPORTED_METADATA_BODY")):
            responses = index_fixtures()
            replace_metadata(responses, "numpy", body)
            self.rejected(responses, code)

    def test_exact_entry_limit_with_distinct_equivalent_variants(self):
        responses = index_fixtures()
        body = fixture("numpy").metadata
        entries = []
        old_url = self.entries(responses)[0]["url"] + ".metadata"
        del responses[old_url]
        for number in range(MAX_INDEX_FILES):
            entry = index_entry("numpy", body, build=str(number))
            entries.append(entry)
            url = entry["url"] + ".metadata"
            responses[url] = SyntheticResponse(200, url, body)
        replace_index(responses, "numpy", entries)
        result = audit_index(responses)
        self.assertEqual(result["status"], "synthetic-only")
        rows = [row for row in result["binding_evidence"] if row["project"] == "numpy"]
        self.assertEqual(len(rows), MAX_INDEX_FILES)

    def test_provider_io_regression_tripwire(self):
        # Only a regression definition, not an OS sandbox or an executed proof.
        responses = index_fixtures()
        def forbidden(*args, **kwargs):
            raise AssertionError("FORBIDDEN_IO")
        with (
            patch.object(builtins, "open", forbidden),
            patch.object(io, "open", forbidden),
            patch.object(os, "open", forbidden),
            patch.object(pathlib.Path, "open", forbidden),
            patch.object(socket, "socket", forbidden),
            patch.object(socket, "create_connection", forbidden),
            patch.object(socket, "getaddrinfo", forbidden),
            patch.object(subprocess, "Popen", forbidden),
            patch.object(os, "system", forbidden),
        ):
            self.assertEqual(audit_index(responses)["status"], "synthetic-only")

    def test_programming_failure_is_not_success_or_declared_rejection(self):
        with patch("proposed.parse_index", side_effect=RuntimeError("fixture bug")):
            with self.assertRaisesRegex(RuntimeError, "^fixture bug$"):
                audit_index(index_fixtures())


if __name__ == "__main__":
    unittest.main()
