# strictroute

A URL path router that refuses to guess.

Most routers treat `/users/42`, `/users/42/`, and `/users//42` as
equivalent, and match path segments case-insensitively. That leniency is
convenient right up until two systems in the same request path disagree
about what a URL means - a reverse proxy normalizes `//` and the app
behind it doesn't, or a WAF matches case-insensitively and the app
doesn't, and suddenly there's a gap between what was checked and what was
served. This library takes the opposite default: a path either matches a
route exactly as written, or matching fails with a specific reason. If you
actually want normalization, you ask for it with `lenient=True`.

## Install

No dependencies, standard library only. Drop `src/strictroute` on your
path, or install locally in editable mode once you have a virtualenv:

```
pip install -e .
```

## Library usage

```python
from strictroute import Router, PathValidationError

router = Router()
router.add("/users/{id:int}")
router.add("/users/{id:int}/posts/{slug:slug}")
router.add("/static/{path:path}")

match = router.match("/users/42")
print(match.route.pattern, match.params)
# /users/{id:int} {'id': '42'}

router.match("/users/42/")
# raises PathValidationError: path has a trailing slash: '/users/42/'

router.match("/users/42/", lenient=True)
# matches /users/{id:int} the same as above - trailing slash is stripped
```

`PathValidationError` is only raised for structural ambiguity (missing
leading slash, doubled slashes, a trailing slash). Control characters and
malformed percent-encoding are rejected even in lenient mode, since those
indicate broken input rather than a stylistic difference in the path.

A path that's well-formed but simply doesn't match any registered route
returns `None` rather than raising - that's an ordinary routing miss, not
a validation failure.

### Pattern syntax

- `{name}` - matches one non-empty segment, any characters except `/`.
- `{name:int}` - digits only.
- `{name:slug}` - lowercase letters, digits, and single hyphens between them.
- `{name:path}` - matches the rest of the path, including slashes. Only
  valid as the final segment.

## CLI usage

```
$ strictroute /users/42 -p "/users/{id:int}" -p "/users/{id:int}/posts/{slug:slug}"
matched: /users/{id:int}
  id = 42

$ strictroute /users/42/ -p "/users/{id:int}"
strictroute: rejected: path has a trailing slash: '/users/42/'
strictroute: pass --lenient to normalize instead of rejecting

$ strictroute /users/42/ -p "/users/{id:int}" --lenient
matched: /users/{id:int}
  id = 42
```

Exit codes: `0` on match, `1` on no match or a rejected path, `2` on a
malformed `--pattern`.

## Status

Early skeleton. Route registration, matching, and the strict/lenient path
validation are in place and usable. Not yet covered: an installable
console script has been declared but not exercised end to end, and there's
no test suite yet.

## License

MIT, see LICENSE.
