import unittest

from strictroute import (
    PathValidationError,
    Route,
    RouteSyntaxError,
    Router,
    validate_path,
)


class RouteTests(unittest.TestCase):
    def test_default_converter_matches_one_segment(self) -> None:
        route = Route("/items/{name}")
        self.assertEqual(route.match("/items/widget"), {"name": "widget"})
        self.assertIsNone(route.match("/items/a/b"))

    def test_int_converter(self) -> None:
        route = Route("/users/{id:int}")
        self.assertEqual(route.match("/users/42"), {"id": "42"})
        self.assertIsNone(route.match("/users/abc"))
        self.assertIsNone(route.match("/users/4a"))

    def test_slug_converter(self) -> None:
        route = Route("/posts/{slug:slug}")
        self.assertEqual(route.match("/posts/hello-world"), {"slug": "hello-world"})
        self.assertIsNone(route.match("/posts/Hello-World"))
        self.assertIsNone(route.match("/posts/-leading"))

    def test_path_converter_matches_rest_including_slashes(self) -> None:
        route = Route("/static/{tail:path}")
        self.assertEqual(route.match("/static/js/app.js"), {"tail": "js/app.js"})

    def test_name_defaults_to_none(self) -> None:
        self.assertIsNone(Route("/x").name)
        self.assertEqual(Route("/x", name="foo").name, "foo")

    def test_pattern_must_start_with_slash(self) -> None:
        with self.assertRaises(RouteSyntaxError):
            Route("users/{id}")

    def test_pattern_rejects_empty_segment(self) -> None:
        with self.assertRaises(RouteSyntaxError):
            Route("/users//{id}")

    def test_pattern_rejects_duplicate_param_names(self) -> None:
        with self.assertRaises(RouteSyntaxError):
            Route("/a/{id}/{id}")

    def test_pattern_rejects_unknown_converter(self) -> None:
        with self.assertRaises(RouteSyntaxError):
            Route("/a/{id:uuid}")

    def test_path_converter_must_be_final_segment(self) -> None:
        with self.assertRaises(RouteSyntaxError):
            Route("/files/{tail:path}/extra")


class RouterTests(unittest.TestCase):
    def test_add_returns_the_route_and_match_reports_it(self) -> None:
        router = Router()
        route = router.add("/users/{id:int}")
        result = router.match("/users/42")
        self.assertIsNotNone(result)
        self.assertIs(result.route, route)
        self.assertEqual(result.params, {"id": "42"})

    def test_no_match_returns_none(self) -> None:
        router = Router()
        router.add("/users/{id:int}")
        self.assertIsNone(router.match("/items/1"))

    def test_first_registered_match_wins(self) -> None:
        router = Router()
        general = router.add("/users/{id}")
        router.add("/users/me")
        result = router.match("/users/me")
        self.assertIs(result.route, general)
        self.assertEqual(result.params, {"id": "me"})

    def test_add_propagates_route_syntax_error(self) -> None:
        router = Router()
        with self.assertRaises(RouteSyntaxError):
            router.add("not-a-path")

    def test_match_rejects_ambiguous_path_by_default(self) -> None:
        router = Router()
        router.add("/users/{id:int}")
        with self.assertRaises(PathValidationError):
            router.match("/users/42/")

    def test_match_normalizes_when_lenient(self) -> None:
        router = Router()
        route = router.add("/users/{id:int}")
        result = router.match("/users/42/", lenient=True)
        self.assertIs(result.route, route)
        self.assertEqual(result.params, {"id": "42"})


class ValidatePathTests(unittest.TestCase):
    def test_well_formed_path_passes_through_unchanged(self) -> None:
        self.assertEqual(validate_path("/users/42"), "/users/42")

    def test_root_path_has_no_trailing_slash_issue(self) -> None:
        self.assertEqual(validate_path("/"), "/")

    def test_control_characters_always_rejected(self) -> None:
        with self.assertRaises(PathValidationError):
            validate_path("/a\x00b")
        with self.assertRaises(PathValidationError):
            validate_path("/a\x00b", lenient=True)

    def test_malformed_percent_encoding_always_rejected(self) -> None:
        with self.assertRaises(PathValidationError):
            validate_path("/a%2zz")
        with self.assertRaises(PathValidationError):
            validate_path("/a%2zz", lenient=True)
        self.assertEqual(validate_path("/a%20b"), "/a%20b")

    def test_backslash_strict_vs_lenient(self) -> None:
        with self.assertRaises(PathValidationError):
            validate_path("/a\\b")
        self.assertEqual(validate_path("/a\\b", lenient=True), "/a/b")

    def test_missing_leading_slash_strict_vs_lenient(self) -> None:
        with self.assertRaises(PathValidationError):
            validate_path("users/42")
        self.assertEqual(validate_path("users/42", lenient=True), "/users/42")

    def test_empty_segment_strict_vs_lenient(self) -> None:
        with self.assertRaises(PathValidationError):
            validate_path("/users//42")
        self.assertEqual(validate_path("/users//42", lenient=True), "/users/42")

    def test_trailing_slash_strict_vs_lenient(self) -> None:
        with self.assertRaises(PathValidationError):
            validate_path("/users/42/")
        self.assertEqual(validate_path("/users/42/", lenient=True), "/users/42")

    def test_lenient_normalizes_several_issues_at_once(self) -> None:
        self.assertEqual(validate_path("users//42/", lenient=True), "/users/42")

    def test_percent_encoded_control_char_always_rejected(self) -> None:
        with self.assertRaises(PathValidationError):
            validate_path("/a%00b")
        with self.assertRaises(PathValidationError):
            validate_path("/a%00b", lenient=True)
        with self.assertRaises(PathValidationError):
            validate_path("/a%7Fb", lenient=True)

    def test_percent_encoded_unreserved_char_untouched_when_strict(self) -> None:
        self.assertEqual(validate_path("/a%2Eb"), "/a%2Eb")

    def test_percent_encoded_unreserved_char_decoded_when_lenient(self) -> None:
        self.assertEqual(validate_path("/a%2Eb", lenient=True), "/a.b")
        self.assertEqual(validate_path("/a%7Eb", lenient=True), "/a~b")

    def test_percent_encoded_slash_kept_encoded_when_lenient(self) -> None:
        # %2F decodes to '/', which would change how the path splits into
        # segments rather than just its spelling, so it stays encoded.
        self.assertEqual(validate_path("/a%2Fb", lenient=True), "/a%2Fb")

    def test_percent_encoding_hex_case_normalized_when_lenient(self) -> None:
        self.assertEqual(validate_path("/a%2fb", lenient=True), "/a%2Fb")
        self.assertEqual(validate_path("/a%2fb"), "/a%2fb")


if __name__ == "__main__":
    unittest.main()
