"""Review-only synthetic metadata checker. Standard library only.

Restricted grammar:
- Names: ASCII distribution names, normalized per PEP 503.
- Versions: canonical decimal release segments, optionally ".postN".
  No epochs, prereleases, dev/local versions, implicit post syntax,
  leading-zero segments, prefixes, or wildcards.
- Specifiers: comma-separated ==, !=, >=, <=, >, < with supported versions.
  No ~=, ===, wildcard equality, or arbitrary equality.
- Requirements: name, optional supported specifiers, optional "; marker".
  One enclosing specifier-parenthesis pair is permitted.
  No extras, URLs, VCS forms, or comments.
- Markers: variable-on-left comparisons against quoted ASCII strings,
  combined with and/or and parentheses.
  == and != are supported for string variables.
  Version variables additionally support <, <=, >, >=.
  No membership operators, ~=, ===, reversed comparisons, escapes,
  adjacent literals, or chained comparisons.
- Metadata: ASCII header-only core metadata, versions 2.1 through 2.4.
  Descriptions, folded headers and Dynamic metadata are rejected.
  Duplicate Metadata-Version, Name, Version and Requires-Python headers reject;
  other repeated headers are not subject to a general singleton check.

Unsupported forms reject. This is not a complete PEP 440/508 implementation.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

CLIENT = "ayursage-metadata-audit 0.2.0-proposed"
INDEX = "https://pypi.org/simple"
MAX_METADATA_BYTES = 256 * 1024
MAX_MARKER_TOKENS = 128
MAX_MARKER_NESTING = 16
MAX_PROJECT_NAME_CHARS = 128
MAX_VERSION_CHARS = 64
MAX_SPECIFIER_BOUND_CHARS = 64
MAX_SPECIFIER_TEXT_CHARS = 4096
MAX_SPECIFIER_CLAUSES = 32
SUPPORTED_MARKER_OPERATORS = frozenset({"==", "!=", "<", "<=", ">", ">="})

CANDIDATES = {
    "scikit-learn": "1.9.0",
    "numpy": "2.4.6",
    "pandas": "3.0.3",
    "scipy": "1.18.0",
    "joblib": "1.5.3",
    "xgboost": "3.3.0",
    "threadpoolctl": "3.6.0",
    "narwhals": "2.24.0",
    "python-dateutil": "2.9.0.post0",
    "six": "1.17.0",
    "tzdata": "2026.3",
}

TARGET = {
    "implementation_name": "cpython",
    "implementation_version": "3.12.7",
    "python_version": "3.12",
    "python_full_version": "3.12.7",
    "platform_python_implementation": "CPython",
    "os_name": "nt",
    "sys_platform": "win32",
    "platform_system": "Windows",
    "platform_machine": "AMD64",
    "extra": "",
}

VERSION_MARKERS = {
    "python_version", "python_full_version", "implementation_version"
}
UNRESOLVED_MARKERS = {"platform_release", "platform_version"}

SEGMENT = r"(?:0|[1-9][0-9]*)"
VERSION_PATTERN = SEGMENT + r"(?:\." + SEGMENT + r")*(?:\.post" + SEGMENT + r")?"
NAME_PATTERN = r"[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+)*"

MARKER_TOKEN = re.compile(
    r"""(?P<word>[A-Za-z_][A-Za-z0-9_]*)"""
    r"""|(?P<string>'[^'\\\r\n]*'|"[^"\\\r\n]*")"""
    r"""|(?P<operator>===|~=|==|!=|<=|>=|<|>)"""
    r"""|(?P<paren>[()])"""
)


class Rejected(ValueError):
    def __init__(self, code, **details):
        self.code = code
        self.details = details
        super().__init__(code)


def reject(code, **details):
    raise Rejected(code, **details)


def normalized(name):
    if type(name) is not str:
        reject("INVALID_PROJECT_NAME")
    if len(name) > MAX_PROJECT_NAME_CHARS:
        reject("PROJECT_NAME_TOO_LARGE")
    if not re.fullmatch(NAME_PATTERN, name):
        reject("INVALID_PROJECT_NAME")
    return re.sub(r"[-_.]+", "-", name).lower()


def approved_candidate(name):
    canonical = normalized(name)
    if canonical not in CANDIDATES:
        reject("UNAPPROVED_CANDIDATE_NAME", name=canonical)
    return canonical, CANDIDATES[canonical]


def version_key(value):
    """Restricted final/post-release subset, not full PEP 440."""
    if type(value) is not str:
        reject("UNSUPPORTED_VERSION_SYNTAX")
    if len(value) > MAX_VERSION_CHARS:
        reject("VERSION_TOO_LARGE")
    if not re.fullmatch(VERSION_PATTERN, value):
        reject("UNSUPPORTED_VERSION_SYNTAX")

    release_text, separator, post_text = value.partition(".post")
    try:
        release = tuple(int(part) for part in release_text.split("."))
        post = int(post_text) if separator else -1
    except ValueError:
        reject("VERSION_INTEGER_CONVERSION_REJECTED")
    return release, post


def compare_versions(left, right):
    a, apost = version_key(left)
    b, bpost = version_key(right)
    width = max(len(a), len(b))
    a += (0,) * (width - len(a))
    b += (0,) * (width - len(b))
    return ((a, apost) > (b, bpost)) - ((a, apost) < (b, bpost))


def parse_specifiers(text):
    if type(text) is not str:
        reject("UNSUPPORTED_SPECIFIER")
    if len(text) > MAX_SPECIFIER_TEXT_CHARS:
        reject("SPECIFIER_TEXT_TOO_LARGE")
    if not text:
        return ()

    parts = text.split(",")
    if len(parts) > MAX_SPECIFIER_CLAUSES:
        reject("TOO_MANY_SPECIFIER_CLAUSES")

    clauses = []
    for clause in parts:
        match = re.fullmatch(r"\s*(==|!=|>=|<=|>|<)\s*(\S+)\s*", clause)
        if not match:
            reject("UNSUPPORTED_SPECIFIER")
        operator, bound = match.groups()
        if len(bound) > MAX_SPECIFIER_BOUND_CHARS:
            reject("SPECIFIER_BOUND_TOO_LARGE")
        version_key(bound)
        clauses.append((operator, bound))
    return tuple(clauses)


def satisfies(version, clauses):
    version_key(version)
    results = []
    for operator, bound in clauses:
        comparison = compare_versions(version, bound)
        results.append({
            "==": comparison == 0,
            "!=": comparison != 0,
            ">=": comparison >= 0,
            "<=": comparison <= 0,
            ">": comparison > 0,
            "<": comparison < 0,
        }[operator])
    return all(results)


def marker_tokens(expression):
    if type(expression) is not str:
        reject("UNSUPPORTED_MARKER_SYNTAX")
    if len(expression) > 4096:
        reject("MARKER_TOO_LARGE")
    if not expression.isascii():
        reject("UNSUPPORTED_MARKER_SYNTAX")
    if any(ord(c) < 32 and c != "\t" for c in expression):
        reject("UNSUPPORTED_MARKER_SYNTAX")
    if "\x7f" in expression:
        reject("UNSUPPORTED_MARKER_SYNTAX")

    tokens = []
    position = 0
    nesting = 0
    while position < len(expression):
        if expression[position] in " \t":
            position += 1
            continue
        match = MARKER_TOKEN.match(expression, position)
        if not match:
            reject("UNSUPPORTED_MARKER_SYNTAX")
        kind, value = match.lastgroup, match.group()
        if kind == "string" and tokens and tokens[-1][0] == "string":
            reject("ADJACENT_MARKER_LITERALS")
        if value == "(":
            nesting += 1
            if nesting > MAX_MARKER_NESTING:
                reject("MARKER_NESTING_LIMIT")
        elif value == ")":
            nesting -= 1
            if nesting < 0:
                reject("MALFORMED_MARKER")
        tokens.append((kind, value))
        if len(tokens) > MAX_MARKER_TOKENS:
            reject("MARKER_TOO_COMPLEX")
        position = match.end()

    if not tokens:
        reject("EMPTY_MARKER")
    if nesting:
        reject("MALFORMED_MARKER")
    return tokens


def marker_applies(expression):
    tokens = marker_tokens(expression)
    position = 0

    def peek(value):
        return position < len(tokens) and tokens[position][1] == value

    def comparison():
        nonlocal position
        if position >= len(tokens):
            reject("MALFORMED_MARKER")
        kind, variable = tokens[position]
        if kind != "word" or variable in {"and", "or", "not", "in"}:
            reject("UNSUPPORTED_MARKER_FORM")
        position += 1

        if variable in UNRESOLVED_MARKERS:
            reject("UNRESOLVED_MARKER", marker=variable)
        if variable not in TARGET:
            reject("UNKNOWN_MARKER", marker=variable)
        if position >= len(tokens):
            reject("MALFORMED_MARKER")

        kind, operator = tokens[position]
        if kind != "operator":
            reject("MALFORMED_MARKER")
        if operator not in SUPPORTED_MARKER_OPERATORS:
            reject("UNSUPPORTED_MARKER_OPERATOR")
        position += 1

        if position >= len(tokens):
            reject("MALFORMED_MARKER")
        kind, literal = tokens[position]
        if kind != "string":
            reject("UNSUPPORTED_MARKER_FORM")
        position += 1

        actual = TARGET[variable]
        expected = literal[1:-1]
        if variable in VERSION_MARKERS:
            result = compare_versions(actual, expected)
        else:
            if operator not in {"==", "!="}:
                reject("UNSUPPORTED_MARKER_OPERATOR")
            result = (actual > expected) - (actual < expected)

        if operator == "==":
            return result == 0
        if operator == "!=":
            return result != 0
        if operator == "<":
            return result < 0
        if operator == "<=":
            return result <= 0
        if operator == ">":
            return result > 0
        if operator == ">=":
            return result >= 0
        reject("UNSUPPORTED_MARKER_OPERATOR")

    def atom():
        nonlocal position
        if peek("("):
            position += 1
            result = disjunction()
            if not peek(")"):
                reject("MALFORMED_MARKER")
            position += 1
            return result
        return comparison()

    def conjunction():
        nonlocal position
        values = [atom()]
        while peek("and"):
            position += 1
            values.append(atom())
        # Validate every branch before combining.
        return all(values)

    def disjunction():
        nonlocal position
        values = [conjunction()]
        while peek("or"):
            position += 1
            values.append(conjunction())
        return any(values)

    result = disjunction()
    if position != len(tokens):
        reject("MALFORMED_MARKER")
    return result


def parse_requirement(text):
    if type(text) is not str or not text.isascii() or len(text) > 4096:
        reject("UNSUPPORTED_REQUIREMENT")
    if "@" in text or "://" in text:
        reject("DIRECT_URL_OR_VCS")
    if any(character in text for character in "\r\n#[]"):
        reject("UNSUPPORTED_REQUIREMENT")

    requirement, separator, marker = text.partition(";")
    match = re.fullmatch(
        "(" + NAME_PATTERN + r")(.*)", requirement.strip()
    )
    if not match:
        reject("UNSUPPORTED_REQUIREMENT")
    name, specifier = match.groups()
    specifier = specifier.strip()
    if specifier.startswith("("):
        if not specifier.endswith(")"):
            reject("UNSUPPORTED_REQUIREMENT")
        specifier = specifier[1:-1].strip()
        if not specifier:
            reject("UNSUPPORTED_REQUIREMENT")
    if "(" in specifier or ")" in specifier:
        reject("UNSUPPORTED_REQUIREMENT")

    clauses = parse_specifiers(specifier)
    active = marker_applies(marker.strip()) if separator else True
    return normalized(name), clauses, active


def checked_url(url, host):
    if type(url) is not str or not url.isascii():
        reject("INVALID_URL")
    if any(ord(character) <= 32 or ord(character) == 127 for character in url):
        reject("INVALID_URL")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        reject("INVALID_URL")
    if (
        parts.scheme != "https"
        or parts.netloc not in {host, host + ":443"}
        or parts.hostname != host
        or port not in {None, 443}
        or parts.username is not None
        or parts.password is not None
        or parts.query
        or parts.fragment
        or "%" in parts.path
        or "\\" in parts.path
        or "//" in parts.path
        or any(segment in {".", ".."} for segment in parts.path.split("/"))
    ):
        reject("UNAPPROVED_URL")
    return parts


@dataclass(frozen=True)
class ProjectPageRequest:
    project: str

    def __post_init__(self):
        approved_candidate(self.project)

    @property
    def url(self):
        canonical, _ = approved_candidate(self.project)
        return INDEX + "/" + canonical + "/"


@dataclass(frozen=True)
class SidecarRequest:
    url: str
    advertised_sha256: str

    def __post_init__(self):
        parts = checked_url(self.url, "files.pythonhosted.org")
        if not re.fullmatch(
            r"/packages/[A-Za-z0-9_./+-]+\.whl\.metadata", parts.path
        ):
            reject("INVALID_SIDECAR_PATH")
        if (
            type(self.advertised_sha256) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", self.advertised_sha256)
        ):
            reject("INVALID_METADATA_HASH")


class Transport:
    """Typed interface only; no HTTP implementation."""

    def fetch(self, request):
        if type(request) is ProjectPageRequest:
            # Defense-in-depth validation before transport dispatch.
            approved_candidate(request.project)
        elif type(request) is not SidecarRequest:
            reject("REQUEST_TYPE_FORBIDDEN")
        return self._fetch_permitted(request)

    def _fetch_permitted(self, request):
        raise NotImplementedError("NO_NETWORK_ADAPTER")


def check_response(request, status, final_url):
    if type(request) not in {ProjectPageRequest, SidecarRequest}:
        reject("REQUEST_TYPE_FORBIDDEN")
    if status != 200 or final_url != request.url:
        reject("REDIRECT_OR_RESPONSE_REJECTED")


@dataclass(frozen=True)
class WheelFixture:
    """Entirely synthetic input.

    compatible is an untrusted test flag, NOT a tag-verification result.
    sidecar/hash fields do NOT establish index-advertisement provenance.
    """
    filename: str
    compatible: bool
    sidecar: SidecarRequest | None
    metadata: bytes | None


def parse_metadata(name, wheel):
    name, candidate_version = approved_candidate(name)
    if type(wheel.sidecar) is not SidecarRequest or wheel.metadata is None:
        reject("MISSING_METADATA_SIDECAR", project=name)
    body = wheel.metadata
    if type(body) is not bytes or len(body) > MAX_METADATA_BYTES:
        reject("METADATA_SIZE_OR_TYPE", project=name)
    digest = hashlib.sha256(body).hexdigest()
    if digest != wheel.sidecar.advertised_sha256:
        reject("METADATA_HASH_MISMATCH", project=name)

    try:
        text = body.decode("ascii")
    except UnicodeDecodeError:
        reject("UNSUPPORTED_METADATA_ENCODING", project=name)
    if "\r" in text.replace("\r\n", ""):
        reject("MALFORMED_METADATA", project=name)
    text = text.replace("\r\n", "\n")
    if "\n\n" not in text:
        reject("MALFORMED_METADATA", project=name)
    headers_text, payload = text.split("\n\n", 1)
    if payload:
        reject("UNSUPPORTED_METADATA_BODY", project=name)

    headers = {}
    for line in headers_text.split("\n"):
        if line.startswith((" ", "\t")):
            reject("UNSUPPORTED_FOLDED_HEADER", project=name)
        match = re.fullmatch(r"([A-Za-z][A-Za-z0-9-]*):[ \t]*(.*)", line)
        if not match or any(ord(c) < 32 and c != "\t" for c in line):
            reject("MALFORMED_METADATA", project=name)
        key, value = match.groups()
        headers.setdefault(key.lower(), []).append(value.strip())

    for key in ("metadata-version", "name", "version"):
        if len(headers.get(key, [])) != 1:
            reject("INVALID_METADATA_HEADERS", project=name)
    if headers["metadata-version"][0] not in {"2.1", "2.2", "2.3", "2.4"}:
        reject("UNSUPPORTED_METADATA_VERSION", project=name)
    if "dynamic" in headers:
        reject("UNSUPPORTED_DYNAMIC_METADATA", project=name)

    recorded_name = normalized(headers["name"][0])
    if recorded_name not in CANDIDATES:
        reject("UNAPPROVED_METADATA_NAME", name=recorded_name)
    if recorded_name != name:
        reject("METADATA_NAME_MISMATCH", project=name, recorded=recorded_name)

    recorded_version = headers["version"][0]
    version_key(recorded_version)
    if recorded_version != candidate_version:
        reject(
            "UNAPPROVED_VERSION", project=name,
            expected=candidate_version, recorded=recorded_version,
        )

    python_headers = headers.get("requires-python", [])
    if len(python_headers) > 1:
        reject("INVALID_METADATA_HEADERS", project=name)
    python_clauses = parse_specifiers(python_headers[0]) if python_headers else ()
    if not satisfies(TARGET["python_full_version"], python_clauses):
        reject("INCOMPATIBLE_REQUIRES_PYTHON", project=name)

    requirements = tuple(sorted(
        parse_requirement(value)
        for value in headers.get("requires-dist", [])
    ))
    return python_clauses, requirements, digest


def checked_audit(fixtures):
    if type(fixtures) is not dict:
        reject("INVALID_FIXTURE_MAP")
    for name in fixtures:
        canonical = normalized(name)
        if canonical != name:
            reject("NONCANONICAL_FIXTURE_NAME", name=name)

    supplied = set(fixtures)
    expected = set(CANDIDATES)
    if supplied != expected:
        reject(
            "CANDIDATE_FIXTURE_SET_MISMATCH",
            missing=sorted(expected - supplied),
            unapproved=sorted(supplied - expected),
        )

    graph = {}
    evidence = []
    for name in sorted(CANDIDATES):
        wheels = fixtures[name]
        if type(wheels) is not list or not wheels:
            reject("MISSING_COMPATIBLE_WHEEL", project=name)
        filenames = set()
        for wheel in wheels:
            if type(wheel) is not WheelFixture:
                reject("INVALID_WHEEL_FIXTURE", project=name)
            if type(wheel.compatible) is not bool:
                reject("INVALID_SYNTHETIC_COMPATIBILITY_FLAG", project=name)
            if (
                type(wheel.filename) is not str
                or not re.fullmatch(r"[A-Za-z0-9_.+-]+\.whl", wheel.filename)
            ):
                reject("SOURCE_OR_NON_WHEEL_CANDIDATE", project=name)
            if wheel.filename in filenames:
                reject("DUPLICATE_WHEEL_FILENAME", project=name)
            filenames.add(wheel.filename)

        compatible = [wheel for wheel in wheels if wheel.compatible]
        if not compatible:
            reject("MISSING_COMPATIBLE_WHEEL", project=name)

        signatures = set()
        edges = set()
        for wheel in sorted(compatible, key=lambda item: item.filename):
            python_clauses, requirements, digest = parse_metadata(name, wheel)
            signatures.add((python_clauses, requirements))
            for dependency, clauses, active in requirements:
                if not active:
                    continue
                if dependency not in CANDIDATES:
                    reject(
                        "UNAPPROVED_DEPENDENCY",
                        parent=name, dependency=dependency,
                    )
                if not satisfies(CANDIDATES[dependency], clauses):
                    reject(
                        "DEPENDENCY_VERSION_OUTSIDE_FIXED_MAP",
                        parent=name, dependency=dependency,
                        candidate=CANDIDATES[dependency],
                        required=[list(clause) for clause in clauses],
                    )
                edges.add(dependency)
            evidence.append({
                "project": name,
                "candidate_version": CANDIDATES[name],
                "synthetic_filename": wheel.filename,
                "compatibility": "UNTRUSTED_SYNTHETIC_FLAG",
                "sidecar_url": wheel.sidecar.url,
                "metadata_sha256": digest,
                "hash_integrity": "MATCHES_SUPPLIED_FIXTURE_HASH",
                "advertisement_provenance": "UNVERIFIED",
            })
        if len(signatures) != 1:
            reject("CONFLICTING_WHEEL_METADATA", project=name)
        graph[name] = sorted(edges)

    return graph, evidence


def audit(fixtures):
    """Declared validation failures are structured; programming errors propagate."""
    base = {
        "client": CLIENT,
        "scope": "SYNTHETIC_FIXTURES_ONLY",
        "candidates": dict(CANDIDATES),
        "candidate_pins_approved": False,
        "target": dict(TARGET),
        "windows_release_build": "UNRESOLVED",
        "index_policy": INDEX,
        "advertisement_provenance": "UNVERIFIED",
        "wheel_tags_verified": False,
        "real_dependency_resolution": False,
        "native_compatibility": "NOT_TESTED",
        "model_compatibility": "NOT_TESTED",
        "independent_verification": "NOT_PERFORMED",
    }
    try:
        graph, evidence = checked_audit(fixtures)
    except Rejected as error:
        return {
            **base,
            "status": "incomplete/rejected",
            "rejection": {"code": error.code, "details": error.details},
        }
    return {
        **base,
        "status": "synthetic-only",
        "synthetic_dependency_graph": graph,
        "metadata_evidence": evidence,
    }


def serialize(evidence):
    return json.dumps(
        evidence, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    )


# Synthetic-only provider. No network, filesystem, pip, packaging or resolvelib.
MAX_INDEX_BYTES = 2 * 1024 * 1024
MAX_INDEX_FILES = 8
MAX_FIXTURE_RESPONSES = len(CANDIDATES) * (MAX_INDEX_FILES + 1)
MAX_URL_CHARS = 2048
MAX_FILENAME_CHARS = 256


@dataclass(frozen=True)
class SyntheticResponse:
    status: int
    final_url: str
    body: bytes


@dataclass(frozen=True)
class BoundSidecarRequest:
    project: str
    version: str
    filename: str
    page_url: str
    page_sha256: str
    sidecar: SidecarRequest

    @property
    def url(self):
        return self.sidecar.url


def bounded_url(url, host):
    if type(url) is not str or len(url) > MAX_URL_CHARS:
        reject("URL_SIZE_OR_TYPE")
    return checked_url(url, host)


def target_tags():
    """Explicit standard CPython 3.12 Windows AMD64 tag policy; not host discovery."""
    tags = {("cp312", "cp312", "win_amd64"), ("cp312", "none", "win_amd64")}
    for minor in range(2, 13):
        tags.add(("cp3" + str(minor), "abi3", "win_amd64"))
    for interpreter in ["py3"] + ["py3" + str(minor) for minor in range(13)]:
        for platform in ("any", "win_amd64"):
            tags.add((interpreter, "none", platform))
    return frozenset(tags)


def wheel_identity(project, filename):
    """Restricted wheel filename grammar; compressed tag products are bounded."""
    if type(filename) is not str or len(filename) > MAX_FILENAME_CHARS:
        reject("WHEEL_FILENAME_SIZE_OR_TYPE")
    if not filename.endswith(".whl"):
        reject("ARCHIVE_SOURCE_BUILD_FALLBACK_FORBIDDEN")
    parts = filename[:-4].split("-")
    if len(parts) not in {5, 6}:
        reject("UNSUPPORTED_WHEEL_FILENAME")
    name, version = parts[:2]
    if normalized(name) != project:
        reject("WHEEL_PROJECT_MISMATCH", project=project)
    version_key(version)
    if version != CANDIDATES[project]:
        reject("WHEEL_VERSION_MISMATCH", project=project)
    if len(parts) == 6 and not re.fullmatch(r"[0-9][A-Za-z0-9_]*", parts[2]):
        reject("UNSUPPORTED_WHEEL_BUILD_TAG")
    groups = []
    for field in parts[-3:]:
        tokens = field.split(".")
        if len(tokens) > 8 or len(set(tokens)) != len(tokens):
            reject("UNSUPPORTED_WHEEL_TAGS")
        if any(not re.fullmatch(r"[a-z0-9_]+", token) for token in tokens):
            reject("UNSUPPORTED_WHEEL_TAGS")
        groups.append(tokens)
    tags = {(i, a, p) for i in groups[0] for a in groups[1] for p in groups[2]}
    return version, sorted(tags.intersection(target_tags()))


def unique_json_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            reject("AMBIGUOUS_INDEX_JSON_KEY")
        result[key] = value
    return result


def parse_index(project, body):
    """Strict synthetic PEP 691-shaped JSON subset; no HTML/general index parser."""
    approved_candidate(project)
    if type(body) is not bytes or len(body) > MAX_INDEX_BYTES:
        reject("INDEX_SIZE_OR_TYPE")
    # Bound nesting before json.loads, including malformed input; ignore braces in strings.
    depth, quoted, escaped = 0, False, False
    for byte in body:
        if quoted:
            if escaped:
                escaped = False
            elif byte == 92:
                escaped = True
            elif byte == 34:
                quoted = False
        elif byte == 34:
            quoted = True
        elif byte in (91, 123):
            depth += 1
            if depth > 8:
                reject("INDEX_NESTING_LIMIT")
        elif byte in (93, 125):
            depth -= 1
            if depth < 0:
                reject("MALFORMED_INDEX")
    def forbidden_number(value):
        reject("UNSUPPORTED_INDEX_NUMBER")
    try:
        page = json.loads(
            body.decode("ascii"), object_pairs_hook=unique_json_pairs,
            parse_int=forbidden_number, parse_float=forbidden_number,
            parse_constant=forbidden_number,
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        reject("MALFORMED_INDEX")
    if type(page) is not dict or set(page) != {"meta", "name", "files"}:
        reject("UNSUPPORTED_INDEX_SCHEMA")
    if page["meta"] != {"api-version": "1.0"}:
        reject("UNSUPPORTED_INDEX_API")
    if normalized(page["name"]) != project:
        reject("INDEX_PROJECT_MISMATCH")
    files = page["files"]
    if type(files) is not list or not 1 <= len(files) <= MAX_INDEX_FILES:
        reject("INDEX_FILE_LIMIT_OR_TYPE")
    # Validate only bounded filename keys first; duplicates precede entry validation.
    if any(type(entry) is not dict or "filename" not in entry for entry in files):
        reject("UNSUPPORTED_INDEX_FILE_SCHEMA")
    if any(type(entry["filename"]) is not str
           or len(entry["filename"]) > MAX_FILENAME_CHARS for entry in files):
        reject("WHEEL_FILENAME_SIZE_OR_TYPE")
    filenames = sorted(entry["filename"] for entry in files)
    for previous, filename in zip(filenames, filenames[1:]):
        if previous == filename:
            reject("AMBIGUOUS_WHEEL_ADVERTISEMENT", filename=filename)
    bindings = []
    page_url = ProjectPageRequest(project).url
    page_digest = hashlib.sha256(body).hexdigest()
    for entry in sorted(files, key=lambda item: item["filename"]):
        if set(entry) != {
            "filename", "url", "requires-python", "yanked", "core-metadata"
        }:
            reject("UNSUPPORTED_INDEX_FILE_SCHEMA")
        filename = entry["filename"]
        version, matched_tags = wheel_identity(project, filename)
        archive = bounded_url(entry["url"], "files.pythonhosted.org")
        if not re.fullmatch(r"/packages/[A-Za-z0-9_./+-]+\.whl", archive.path):
            reject("UNSUPPORTED_ADVERTISED_WHEEL_URL")
        if archive.path.rsplit("/", 1)[-1] != filename:
            reject("ADVERTISED_WHEEL_URL_MISMATCH")
        # Reject all yanked advertisements; no exact-pin override.
        if entry["yanked"] is not False:
            reject("YANKED_OR_INVALID_POLICY_VALUE")
        requires_python = entry["requires-python"]
        if type(requires_python) is not str or not requires_python:
            reject("MISSING_INDEX_REQUIRES_PYTHON")
        clauses = parse_specifiers(requires_python)
        if not satisfies(TARGET["python_full_version"], clauses):
            reject("INDEX_REQUIRES_PYTHON_REJECTED")
        advertised = entry["core-metadata"]
        if type(advertised) is not dict or set(advertised) != {"sha256"}:
            reject("MISSING_ADVERTISED_METADATA_HASH")
        # Derive, never accept an arbitrary caller-selected sidecar URL.
        sidecar = SidecarRequest(entry["url"] + ".metadata", advertised["sha256"])
        bounded_url(sidecar.url, "files.pythonhosted.org")
        if matched_tags:
            binding = BoundSidecarRequest(
                project, version, filename, page_url, page_digest, sidecar
            )
            bindings.append((binding, matched_tags, clauses))
    if not bindings:
        reject("MISSING_COMPATIBLE_WHEEL", project=project)
    return bindings


def recursive_dependency_closure(graph, roots):
    """Traverse the validated fixed graph; a visited set bounds dependency cycles."""
    visited = set()
    def visit(project):
        if project in visited:
            return
        visited.add(project)
        for dependency in graph[project]:
            visit(dependency)
    for root in sorted(roots):
        visit(root)
    return sorted(visited)


class SyntheticProvider:
    """In-memory response lookup only. Bound requests cannot trigger acquisition."""

    def __init__(self, responses):
        if type(responses) is not dict or len(responses) > MAX_FIXTURE_RESPONSES:
            reject("RESPONSE_MAP_LIMIT_OR_TYPE")
        if any(type(url) is not str or len(url) > MAX_URL_CHARS for url in responses):
            reject("URL_SIZE_OR_TYPE")
        for url in sorted(responses):
            response = responses[url]
            if type(url) is not str or len(url) > MAX_URL_CHARS:
                reject("URL_SIZE_OR_TYPE")
            if type(response) is not SyntheticResponse:
                reject("INVALID_SYNTHETIC_RESPONSE")
            if type(response.body) is not bytes or len(response.body) > MAX_INDEX_BYTES:
                reject("RESPONSE_BODY_SIZE_OR_TYPE")
            if type(response.status) is not int or type(response.final_url) is not str:
                reject("INVALID_SYNTHETIC_RESPONSE")
            if response.final_url != url or response.status != 200:
                reject("REDIRECT_OR_RESPONSE_REJECTED")
            if url.startswith(INDEX + "/"):
                project = url[len(INDEX) + 1:-1]
                if ProjectPageRequest(project).url != url:
                    reject("UNAPPROVED_PROJECT_URL")
            else:
                bounded_url(url, "files.pythonhosted.org")
                if not re.fullmatch(r"/packages/[A-Za-z0-9_./+-]+\.whl\.metadata",
                                    urlsplit(url).path):
                    reject("ARCHIVE_SOURCE_BUILD_FALLBACK_FORBIDDEN")
                if len(response.body) > MAX_METADATA_BYTES:
                    reject("METADATA_SIZE_OR_TYPE")
        self._responses = dict(responses)
        self._bound = {}
        self._used = set()

    def fetch(self, request):
        if type(request) is ProjectPageRequest:
            approved_candidate(request.project)
            limit = MAX_INDEX_BYTES
        elif type(request) is BoundSidecarRequest:
            if self._bound.get(request.url) != request:
                reject("UNBOUND_SIDECAR_REQUEST")
            # Revalidate even frozen request fields before fixture lookup.
            SidecarRequest(request.url, request.sidecar.advertised_sha256)
            limit = MAX_METADATA_BYTES
        else:
            reject("ARCHIVE_SOURCE_BUILD_FALLBACK_OR_REQUEST_TYPE_FORBIDDEN")
        response = self._responses.get(request.url)
        if response is None:
            reject("MISSING_SYNTHETIC_RESPONSE", url=request.url)
        if len(response.body) > limit:
            reject("RESPONSE_BODY_SIZE_OR_TYPE")
        self._used.add(request.url)
        return response.body

    def closure(self):
        self._bound.clear()
        self._used.clear()
        fixtures, binding_evidence, excluded = {}, [], []
        for project in sorted(CANDIDATES):
            body = self.fetch(ProjectPageRequest(project))
            fixtures[project] = []
            for binding, tags, index_python in parse_index(project, body):
                if binding.url in self._bound:
                    reject("AMBIGUOUS_SIDECAR_ADVERTISEMENT")
                self._bound[binding.url] = binding
                metadata = self.fetch(binding)
                wheel = WheelFixture(binding.filename, True, binding.sidecar, metadata)
                python_clauses, requirements, digest = parse_metadata(project, wheel)
                if not python_clauses:
                    reject("MISSING_METADATA_REQUIRES_PYTHON")
                if python_clauses != index_python:
                    reject("INDEX_METADATA_REQUIRES_PYTHON_MISMATCH")
                fixtures[project].append(wheel)
                for dependency, clauses, active in requirements:
                    if not active:
                        excluded.append((project, dependency, clauses, "TARGET_MARKER_FALSE"))
                binding_evidence.append({
                    "project": project, "version": binding.version,
                    "wheel": binding.filename, "matched_target_tags": tags,
                    "page_url": binding.page_url,
                    "sidecar_url": binding.url, "sidecar_sha256": digest,
                    "binding": "SYNTHETIC_INDEX_ADVERTISEMENT_ONLY",
                })
        if self._used != set(self._responses):
            reject("UNUSED_OR_UNADVERTISED_RESPONSE")
        graph, _ = checked_audit(fixtures)
        # Production retains all fixed candidates as roots; tests can isolate one root.
        dependency_closure = recursive_dependency_closure(graph, CANDIDATES)
        return {
            "client": CLIENT, "status": "synthetic-only",
            "scope": "SYNTHETIC_INDEX_AND_SIDECARS_ONLY",
            "target": dict(TARGET), "candidates": dict(CANDIDATES),
            "candidate_pins_approved": False,
            "real_dependency_resolution": False,
            "native_compatibility": "NOT_TESTED", "model_compatibility": "NOT_TESTED",
            "advertisement_provenance": "SYNTHETIC_FIXTURE_ONLY",
            "target_tag_policy": "EXPLICIT_STANDARD_CP312_WINDOWS_AMD64",
            "synthetic_dependency_graph": graph,
            "recursive_closure": dependency_closure,
            "excluded_requirements": sorted(set(excluded)),
            "binding_evidence": binding_evidence,
        }


def audit_index(responses):
    """Fail closed for declared fixture errors; unexpected programming errors propagate."""
    try:
        return SyntheticProvider(responses).closure()
    except Rejected as error:
        return {
            "client": CLIENT, "status": "incomplete/rejected",
            "scope": "SYNTHETIC_INDEX_AND_SIDECARS_ONLY",
            "real_dependency_resolution": False,
            "rejection": {"code": error.code, "details": error.details},
        }
