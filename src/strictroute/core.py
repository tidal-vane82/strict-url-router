"""Route pattern matching for URL paths, strict by default.

Most routers treat "/users/42", "/users/42/", and "/users//42" as the same
thing, and match segments case-insensitively. That leniency is where a lot
of real routing bugs live: two layers of a system (a proxy and an app, say)
disagreeing about what a path means is a classic way to smuggle a request
past an access check. This module refuses to guess. A path either matches a
route exactly as written, or validation fails loudly, unless the caller
opts into normalization with lenient=True.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional

_TOKEN_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)(?::([a-zA-Z_]+))?\}")
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_BAD_PERCENT = re.compile(r"%(?![0-9A-Fa-f]{2})")
_PERCENT_TRIPLET = re.compile(r"%([0-9A-Fa-f]{2})")

# RFC 3986 unreserved characters: encoding these adds no meaning, so lenient
# mode decodes them back to their literal form. Everything else percent-
# encoded (notably %2F for '/') stays encoded, since decoding it would
# change how the path splits into segments rather than just its spelling.
_UNRESERVED = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
)


def _normalize_percent_triplet(match: "re.Match[str]") -> str:
    hex_digits = match.group(1)
    char = chr(int(hex_digits, 16))
    if char in _UNRESERVED:
        return char
    return "%" + hex_digits.upper()


class RouteSyntaxError(ValueError):
    """A route pattern itself is malformed (not a path-matching failure)."""


class PathValidationError(ValueError):
    """A candidate path fails strict validation."""


# Segment converters available inside a `{name:converter}` token. "str" is
# the default when no converter is given. "path" greedily matches the rest
# of the string including slashes, so it only makes sense as the last token.
CONVERTERS: Dict[str, str] = {
    "str": r"[^/]+",
    "int": r"[0-9]+",
    "slug": r"[a-z0-9]+(?:-[a-z0-9]+)*",
    "path": r".+",
}


@dataclass(frozen=True)
class Match:
    route: "Route"
    params: Mapping[str, str]


@dataclass(frozen=True)
class Route:
    pattern: str
    name: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.pattern.startswith("/"):
            raise RouteSyntaxError(f"pattern must start with '/': {self.pattern!r}")
        if "//" in self.pattern:
            raise RouteSyntaxError(f"pattern has an empty segment: {self.pattern!r}")

        regex_parts: List[str] = []
        param_names: List[str] = []
        pos = 0
        path_converter_used = False

        for token in _TOKEN_RE.finditer(self.pattern):
            if path_converter_used:
                raise RouteSyntaxError(
                    f"the 'path' converter must be the final segment: {self.pattern!r}"
                )
            regex_parts.append(re.escape(self.pattern[pos:token.start()]))
            name, converter = token.group(1), token.group(2) or "str"
            if converter not in CONVERTERS:
                raise RouteSyntaxError(f"unknown converter {converter!r} for {{{name}}}")
            if name in param_names:
                raise RouteSyntaxError(f"duplicate parameter name {{{name}}}")
            regex_parts.append(f"(?P<{name}>{CONVERTERS[converter]})")
            param_names.append(name)
            path_converter_used = converter == "path"
            pos = token.end()

        regex_parts.append(re.escape(self.pattern[pos:]))
        object.__setattr__(self, "_regex", re.compile("^" + "".join(regex_parts) + "$"))
        object.__setattr__(self, "_param_names", tuple(param_names))

    def match(self, path: str) -> Optional[Dict[str, str]]:
        found = self._regex.match(path)  # type: ignore[attr-defined]
        if found is None:
            return None
        return found.groupdict()


def validate_path(path: str, *, lenient: bool = False) -> str:
    """Return a path safe to match against routes, or raise.

    Structural issues (missing leading slash, doubled slashes, a trailing
    slash) are normalized away when lenient=True. Safety issues (control
    characters, malformed percent-encoding, percent-encoded control
    characters) are rejected either way - leniency is about routing
    ambiguity, not about accepting broken input. When lenient=True,
    percent-encoded unreserved characters (letters, digits, "-", ".", "_",
    "~") are also decoded, and the hex digits of any percent-encoding left
    in place are uppercased, since neither spelling changes what the path
    means.
    """
    if _CONTROL_CHARS.search(path):
        raise PathValidationError(f"path contains control characters: {path!r}")
    if _BAD_PERCENT.search(path):
        raise PathValidationError(f"path has malformed percent-encoding: {path!r}")
    for triplet in _PERCENT_TRIPLET.finditer(path):
        if _CONTROL_CHARS.match(chr(int(triplet.group(1), 16))):
            raise PathValidationError(
                f"path has a percent-encoded control character: {path!r}"
            )

    if "\\" in path:
        if not lenient:
            raise PathValidationError(f"path contains a backslash: {path!r}")
        path = path.replace("\\", "/")

    if lenient:
        path = _PERCENT_TRIPLET.sub(_normalize_percent_triplet, path)

    if not path.startswith("/"):
        if not lenient:
            raise PathValidationError(f"path must start with '/': {path!r}")
        path = "/" + path

    if "//" in path:
        if not lenient:
            raise PathValidationError(f"path contains an empty segment: {path!r}")
        while "//" in path:
            path = path.replace("//", "/")

    if len(path) > 1 and path.endswith("/"):
        if not lenient:
            raise PathValidationError(f"path has a trailing slash: {path!r}")
        path = path.rstrip("/") or "/"

    return path


class Router:
    """Collects routes in registration order and matches paths against them."""

    def __init__(self) -> None:
        self._routes: List[Route] = []

    def add(self, pattern: str, name: Optional[str] = None) -> Route:
        route = Route(pattern, name=name)
        self._routes.append(route)
        return route

    def match(self, path: str, *, lenient: bool = False) -> Optional[Match]:
        normalized = validate_path(path, lenient=lenient)
        for route in self._routes:
            params = route.match(normalized)
            if params is not None:
                return Match(route=route, params=params)
        return None
