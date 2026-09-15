"""Thin command-line wrapper around strictroute.core.

This is deliberately a translation layer, not a place to add logic: parse
argv, call the library, print the result. Anything smarter than that
belongs in core.py where it can be tested and reused without a subprocess.
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from .core import PathValidationError, Router, RouteSyntaxError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="strictroute",
        description="Match a URL path against one or more route patterns.",
    )
    parser.add_argument("path", help="the path to match, e.g. /users/42")
    parser.add_argument(
        "-p", "--pattern",
        dest="patterns",
        action="append",
        required=True,
        metavar="PATTERN",
        help="a route pattern, e.g. /users/{id:int}; repeatable, checked in order given",
    )
    parser.add_argument(
        "--lenient",
        action="store_true",
        help="normalize slashes and structure instead of rejecting an ambiguous path",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    router = Router()
    try:
        for pattern in args.patterns:
            router.add(pattern)
    except RouteSyntaxError as exc:
        print(f"strictroute: bad pattern: {exc}", file=sys.stderr)
        return 2

    try:
        result = router.match(args.path, lenient=args.lenient)
    except PathValidationError as exc:
        print(f"strictroute: rejected: {exc}", file=sys.stderr)
        if not args.lenient:
            print("strictroute: pass --lenient to normalize instead of rejecting", file=sys.stderr)
        return 1

    if result is None:
        print("no match")
        return 1

    print(f"matched: {result.route.pattern}")
    for key, value in result.params.items():
        print(f"  {key} = {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
